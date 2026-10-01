"""The accuracy stage: every test, run on the device under test, checked
against DoomV in strict lock-step (docs/lockstep.md).

For each test ELF:
  1. the device under test runs it and writes a Sail-format trace;
  2. DoomV runs it with -lockstep=<trace> -lockstep-strict, and stops at the
     first record that differs;
  3. the verdict, the number of records matched, the test's own result
     (tohost) and the device's speed are kept.

The device under test is a command template: the core's simulation once it
exists, DoomV itself in the self-test (scripts/pipeline.toml, [selftest]).
"""
from __future__ import annotations

import concurrent.futures as cf
import re
import shutil
import subprocess
import time
from pathlib import Path

from . import elf

# "lockstep: N records matched ..." on a pass; "... after N matching records"
# on a mismatch.
MATCHED = re.compile(r"lockstep: (\d+) records|after (\d+) matching records")


def fill(template: list[str], values: dict) -> list[str]:
    return [part.format(**values) for part in template]


def run_test(test: Path, suite: dict, dut: list[str], doomv: Path, wad: Path, work: Path,
             timeout: float) -> dict:
    name = test.name
    out = {"test": name, "verdict": "error", "records": 0}
    shutil.rmtree(work, ignore_errors=True)
    (work / "dut").mkdir(parents=True)
    (work / "ref").mkdir(parents=True)
    try:
        tohost = elf.symbols(test).get("tohost")
    except (OSError, ValueError) as e:
        out["detail"] = f"cannot read ELF: {e}"
        return out
    if tohost is None:
        out["verdict"] = "skip"
        out["detail"] = "no tohost symbol"
        return out
    trace = work / "dut.trace"
    values = {"doomv": str(doomv), "wad": str(wad), "elf": str(test), "march": suite["march"],
              "tohost": f"{tohost:x}", "trace": str(trace), "steps": str(suite["max_steps"])}

    # 1. the device under test
    t0 = time.monotonic()
    try:
        r = subprocess.run(fill(dut, values), cwd=work / "dut", capture_output=True, text=True,
                           errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired:
        out["detail"] = "device under test timed out"
        return out
    out["dut_seconds"] = round(time.monotonic() - t0, 3)
    if not trace.exists() or trace.stat().st_size == 0:
        out["detail"] = f"device under test wrote no trace (exit {r.returncode})"
        return out
    tohost_log = work / "dut" / "tohost.log"
    out["test_result"] = tohost_log.read_text().strip() if tohost_log.exists() else None

    # 2. DoomV, strictly, against that trace
    ref = [str(doomv), "-ng", str(wad), str(test), f"-march={suite['march']}", f"-tohost={tohost:x}",
           f"-lockstep={trace}", "-lockstep-strict", f"-stopat={suite['max_steps']}"]
    try:
        r = subprocess.run(ref, cwd=work / "ref", capture_output=True, text=True, errors="replace",
                           timeout=timeout)
    except subprocess.TimeoutExpired:
        out["detail"] = "DoomV timed out"
        return out
    text = r.stdout + r.stderr
    m = MATCHED.search(text)
    out["records"] = int(m.group(1) or m.group(2)) if m else 0
    if "MISMATCH" in text:
        out["verdict"] = "mismatch"
        at = text.index("lockstep: MISMATCH")
        out["detail"] = text[at:at + 1500].strip()
    elif m:
        out["verdict"] = "match"
        shutil.rmtree(work, ignore_errors=True)   # keep only what failed
    else:
        out["detail"] = f"no lock-step summary (exit {r.returncode}): {text[-500:].strip()}"
    if out["records"] and out.get("dut_seconds"):
        out["dut_ips"] = round(out["records"] / out["dut_seconds"])
    return out


def run_suites(suites: dict, names: list[str], doomv_root: Path, doomv_exe: Path, dut: list[str],
               work: Path, jobs: int, timeout: float, limit: int | None, progress=None) -> dict:
    wad = doomv_root / "tools" / "doom" / "doombuild" / "DOOM1.WAD"
    results = {}
    for name in names:
        suite = suites[name]
        tests = sorted(p for p in doomv_root.glob(suite["glob"]) if p.is_file() and not p.suffix)
        if limit:
            tests = tests[:limit]
        t0 = time.monotonic()
        rows = []
        with cf.ThreadPoolExecutor(jobs) as pool:
            futures = [pool.submit(run_test, t, suite, dut, doomv_exe, wad, work / name / t.name, timeout)
                       for t in tests]
            for i, f in enumerate(cf.as_completed(futures), 1):
                rows.append(f.result())
                if progress:
                    progress(name, i, len(tests), rows[-1])
        rows.sort(key=lambda r: r["test"])
        count = lambda v: sum(1 for r in rows if r["verdict"] == v)
        records = sum(r["records"] for r in rows)
        dut_seconds = sum(r.get("dut_seconds", 0) for r in rows)
        results[name] = {
            "tests": len(rows), "match": count("match"), "mismatch": count("mismatch"),
            "error": count("error"), "skip": count("skip"),
            "test_passed": sum(1 for r in rows if r.get("test_result") == "1"),
            "records": records, "seconds": round(time.monotonic() - t0, 1),
            "dut_ips": round(records / dut_seconds) if dut_seconds else None,
            "failures": [r for r in rows if r["verdict"] in ("mismatch", "error")],
        }
    return results
