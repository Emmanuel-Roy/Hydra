"""The Vitis stages for one HLS component: synthesis, C simulation,
co-simulation and out-of-context implementation, and what their reports say.

A component's own hls_config.cfg names its sources and top, never a part or a
clock; `write_config` adds the target's, and makes source paths absolute, into
a generated config in the build directory. The component is therefore the same
for every target.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from .amd import AmdTools

# Config keys whose values are paths relative to the component directory.
PATH_KEYS = ("syn.file", "tb.file", "syn.cflags_file")
# Removed or deprecated in the pinned release; dropped with a note.
DEPRECATED = {"flow_target": "deprecated in 2026.1; 'vivado' is the default"}


def write_config(comp_dir: Path, target: dict, out: Path) -> list[str]:
    """Write the generated config; return notes about anything dropped."""
    notes = []
    lines = [f"part={target['part']}", ""]
    for raw in (comp_dir / "hls_config.cfg").read_text().splitlines():
        line = raw.strip()
        key = line.split("=", 1)[0].strip() if "=" in line else ""
        if key in ("part", "clock"):
            notes.append(f"{comp_dir.name}: its config sets '{key}', which belongs to the target; ignored")
            continue
        if key in DEPRECATED:
            notes.append(f"{comp_dir.name}: '{key}' {DEPRECATED[key]}; dropped")
            continue
        if key in PATH_KEYS:
            val = line.split("=", 1)[1].strip()
            line = f"{key}={(comp_dir / val).resolve()}"
        lines.append(line)
    lines.append(f"clock={1000.0 / target['clock_mhz']:.3f}ns")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n")
    return notes


def _num(text):
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def parse_csynth(work: Path) -> dict | None:
    """The synthesis estimate: clock, latency, interval, resources."""
    found = sorted(work.rglob("csynth.xml"))
    if not found:
        return None
    root = ET.parse(found[0]).getroot()
    g = lambda path: root.findtext(path)
    res = root.find("AreaEstimates/Resources")
    avail = root.find("AreaEstimates/AvailableResources")
    out = {
        "report": str(found[0]),
        "target_clock_ns": _num(g("UserAssignments/TargetClockPeriod")),
        "estimated_clock_ns": _num(g("PerformanceEstimates/SummaryOfTimingAnalysis/EstimatedClockPeriod")),
        "latency_best": _num(g("PerformanceEstimates/SummaryOfOverallLatency/Best-caseLatency")),
        "latency_worst": _num(g("PerformanceEstimates/SummaryOfOverallLatency/Worst-caseLatency")),
        "interval_min": _num(g("PerformanceEstimates/SummaryOfOverallLatency/Interval-min")),
        "interval_max": _num(g("PerformanceEstimates/SummaryOfOverallLatency/Interval-max")),
        "resources": {c.tag: _num(c.text) for c in res} if res is not None else {},
        "available": {c.tag: _num(c.text) for c in avail} if avail is not None else {},
    }
    return out


def parse_impl(work: Path) -> dict | None:
    """Post-route resources and achieved clock from the out-of-context
    implementation. The export report's location has moved between releases,
    so any XML under impl/ that carries the two sections is accepted."""
    for p in sorted(work.rglob("*.xml")):
        if "impl" not in p.parts:
            continue
        try:
            root = ET.parse(p).getroot()
        except ET.ParseError:
            continue
        res = root.find(".//AreaReport/Resources")
        timing = root.find(".//TimingReport")
        if res is None or timing is None:
            continue
        achieved = _num(timing.findtext("AchievedClockPeriod"))
        return {
            "report": str(p),
            "resources": {c.tag: _num(c.text) for c in res},
            "target_clock_ns": _num(timing.findtext("TargetClockPeriod")),
            "achieved_clock_ns": achieved,
            "fmax_mhz": round(1000.0 / achieved, 1) if achieved else None,
            # 2026.1's export report has no TimingMet; the achieved period
            # against the target says the same thing.
            "timing_met": (achieved <= _num(timing.findtext("TargetClockPeriod")))
                          if achieved and _num(timing.findtext("TargetClockPeriod")) else None,
        }
    return None


def parse_cosim(work: Path) -> dict | None:
    """Co-simulation's verdict and measured latency, from its report."""
    for p in sorted(work.rglob("*cosim.rpt")):
        text = p.read_text(errors="replace")
        verdict = "pass" if "Pass" in text else "fail" if "Fail" in text else "unknown"
        return {"report": str(p), "verdict": verdict}
    return None


STAGES = {
    # stage: (tool, extra args)
    "hls": ("v++", ["-c", "--mode", "hls"]),
    "csim": ("vitis-run", ["--mode", "hls", "--csim"]),
    "cosim": ("vitis-run", ["--mode", "hls", "--cosim"]),
    "impl": ("vitis-run", ["--mode", "hls", "--impl"]),
}


def run_stage(tools: AmdTools, stage: str, cfg: Path, work: Path, logs: Path, timeout: float) -> dict:
    tool, args = STAGES[stage]
    status, seconds = tools.run(tool, args + ["--config", str(cfg), "--work_dir", str(work)],
                                log=logs / f"{stage}.log", cwd=cfg.parent, timeout=timeout)
    result = {"stage": stage, "status": status, "seconds": round(seconds, 1),
              "log": str(logs / f"{stage}.log"), "ok": status == 0}
    log_text = (logs / f"{stage}.log").read_text(errors="replace")
    errors = [l for l in log_text.splitlines() if l.startswith("ERROR")]
    if errors:
        result["ok"] = False
        result["errors"] = errors[:10]
    if stage == "hls":
        result["csynth"] = parse_csynth(work)
        if result["ok"] and not result["csynth"]:
            result["ok"] = False
            result.setdefault("errors", []).append("synthesis wrote no csynth.xml")
    elif stage == "impl":
        result["impl"] = parse_impl(work)
    elif stage == "cosim":
        result["cosim"] = parse_cosim(work)
        if result["cosim"] and result["cosim"]["verdict"] == "fail":
            result["ok"] = False
    return result
