"""Reports: one JSON and one Markdown file per run under Performance/runs/,
a line per run in Performance/RUNS.md, and the comparison with the last
comparable run -- what got bigger, slower or less accurate.

Two runs are comparable when they built the same components for the same
target and ran the same suites (the run's `key`).
"""
from __future__ import annotations

import json
from pathlib import Path

# A change beyond these is called out as a regression.
RESOURCE_TOLERANCE = 0.02     # 2% more of any resource
CLOCK_TOLERANCE = 0.02        # 2% slower achieved or estimated clock


def previous(runs_dir: Path, key: str, current: str) -> dict | None:
    if not runs_dir.exists():
        return None
    for d in sorted(runs_dir.iterdir(), reverse=True):
        f = d / "report.json"
        if d.name == current or not f.exists():
            continue
        try:
            r = json.loads(f.read_text())
        except ValueError:
            continue
        if r.get("key") == key:
            return r
    return None


def compare(cur: dict, prev: dict | None) -> list[str]:
    """Regressions against the previous comparable run, in words."""
    if not prev:
        return []
    out = []
    for name, comp in cur.get("components", {}).items():
        old = prev.get("components", {}).get(name)
        if not old:
            continue
        for stage, kind in (("hls", "csynth"), ("impl", "impl")):
            a = (old.get(stage) or {}).get(kind) or {}
            b = (comp.get(stage) or {}).get(kind) or {}
            for res, v in (b.get("resources") or {}).items():
                w = (a.get("resources") or {}).get(res)
                if v and w and v > w * (1 + RESOURCE_TOLERANCE):
                    out.append(f"{name}: {res} {stage} {w:g} -> {v:g} (+{100 * (v / w - 1):.1f}%)")
            for clk in ("estimated_clock_ns", "achieved_clock_ns"):
                v, w = b.get(clk), a.get(clk)
                if v and w and v > w * (1 + CLOCK_TOLERANCE):
                    out.append(f"{name}: {clk} {w:g} -> {v:g} ns")
        for stage in ("hls", "csim", "cosim", "impl"):
            if (old.get(stage) or {}).get("ok") and comp.get(stage) and not comp[stage].get("ok"):
                out.append(f"{name}: {stage} passed last time and fails now")
    for name, s in cur.get("accuracy", {}).items():
        o = prev.get("accuracy", {}).get(name)
        if o and s["match"] < o["match"]:
            out.append(f"{name}: {o['match']} tests matched DoomV last time, {s['match']} now")
        if o and o.get("dut_ips") and s.get("dut_ips") and s["dut_ips"] < o["dut_ips"] * 0.9:
            out.append(f"{name}: simulation speed {o['dut_ips']:,} -> {s['dut_ips']:,} instructions/s")
    return out


def fmt(v, unit=""):
    if v is None:
        return "--"
    if isinstance(v, float):
        v = int(v) if v.is_integer() else round(v, 2)
    return f"{v:,}{unit}" if isinstance(v, (int, float)) else f"{v}{unit}"


def markdown(r: dict) -> str:
    lines = [f"# {r['label'] or r['id']}", "",
             f"Run `{r['id']}`, commit `{r['commit']}`, target `{r['target']}`, tools {r['tools']}.", ""]
    if r.get("notes"):
        lines += ["Notes:", ""] + [f"- {n}" for n in r["notes"]] + [""]
    if r.get("components"):
        lines += ["## Builds", "",
                  "| component | stage | result | time | LUT | FF | DSP | BRAM (18K / 36K) | URAM | clock (ns) | Fmax |",
                  "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
        for name, comp in r["components"].items():
            for stage in ("hls", "csim", "cosim", "impl"):
                s = comp.get(stage)
                if not s:
                    continue
                rep = s.get("csynth") or s.get("impl") or {}
                res = rep.get("resources") or {}
                clk = rep.get("achieved_clock_ns") or rep.get("estimated_clock_ns")
                # Synthesis counts 18K halves, implementation whole 36K blocks.
                bram = (f"{fmt(res['BRAM_18K'])} x18K" if "BRAM_18K" in res
                        else f"{fmt(res['BRAM'])} x36K" if "BRAM" in res else "--")
                lines.append(f"| {name} | {stage} | {'ok' if s['ok'] else 'FAILED'} | {fmt(s['seconds'], ' s')} | "
                             f"{fmt(res.get('LUT'))} | {fmt(res.get('FF'))} | {fmt(res.get('DSP'))} | "
                             f"{bram} | {fmt(res.get('URAM'))} | {fmt(clk)} | "
                             f"{fmt(rep.get('fmax_mhz'), ' MHz')} |")
        lines.append("")
    if r.get("accuracy"):
        lines += ["## Accuracy (strict lock-step against DoomV)", "",
                  "| suite | tests | match | mismatch | error | skip | test passed | instructions | instructions/s | time |",
                  "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
        for name, s in r["accuracy"].items():
            lines.append(f"| {name} | {s['tests']} | {s['match']} | {s['mismatch']} | {s['error']} | {s['skip']} | "
                         f"{s['test_passed']} | {fmt(s['records'])} | {fmt(s['dut_ips'])} | {fmt(s['seconds'], ' s')} |")
        lines.append("")
        for name, s in r["accuracy"].items():
            for f in s["failures"][:10]:
                lines += [f"**{name} / {f['test']}: {f['verdict']}**", "", "```", f.get("detail", ""), "```", ""]
    lines += ["## Against the previous comparable run", ""]
    if r.get("previous"):
        lines.append(f"Previous: `{r['previous']}`.")
        lines += [""] + ([f"- **{x}**" for x in r["regressions"]] or ["No regressions."])
    else:
        lines.append("None: this is the first run of its kind.")
    return "\n".join(lines) + "\n"


def index_line(r: dict) -> str:
    acc = r.get("accuracy", {})
    tests = sum(s["tests"] for s in acc.values())
    match = sum(s["match"] for s in acc.values())
    built = [n for n, c in r.get("components", {}).items() if all(s.get("ok") for s in c.values() if isinstance(s, dict))]
    status = "PASS" if r["ok"] else "FAIL"
    return (f"| {r['id']} | {r['label']} | {r['commit']} | {r['target']} | {status} | "
            f"{', '.join(built) or '--'} | {f'{match}/{tests}' if tests else '--'} | "
            f"{len(r['regressions'])} | [report](runs/{r['id']}/report.md) |\n")


def write(r: dict, perf_dir: Path):
    runs = perf_dir / "runs"
    d = runs / r["id"]
    d.mkdir(parents=True, exist_ok=True)
    prev = previous(runs, r["key"], r["id"])
    r["previous"] = prev["id"] if prev else None
    r["regressions"] = compare(r, prev)
    (d / "report.json").write_text(json.dumps(r, indent=2) + "\n")
    (d / "report.md").write_text(markdown(r))
    table = perf_dir / "RUNS.md"
    if not table.exists():
        table.write_text("# Pipeline runs\n\nWritten by `scripts/pipeline.py`, newest last.\n\n"
                         "| run | label | commit | target | result | built | lock-step matched | regressions | report |\n"
                         "|---|---|---|---|---|---|---:|---:|---|\n")
    with table.open("a") as f:
        f.write(index_line(r))
    return d
