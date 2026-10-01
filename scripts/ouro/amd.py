"""The pinned AMD tools: finding them, checking the version, running them.

Every call goes through `run`, which logs the tool's whole output to a file
and returns its exit status, so a multi-hour build always leaves a log behind
whatever happens to the console.
"""
from __future__ import annotations

import os
import re
import subprocess
import time
from pathlib import Path

WINDOWS = os.name == "nt"


class AmdTools:
    def __init__(self, root: Path, version: str):
        self.root = root
        self.version = version

    def path(self, tool: str) -> Path:
        """v++ and vitis-run live in Vitis/bin, vivado in Vivado/bin."""
        sub = "Vivado" if tool == "vivado" else "Vitis"
        return self.root / sub / "bin" / (tool + (".bat" if WINDOWS else ""))

    def argv(self, tool: str, args: list[str]) -> list[str]:
        exe = str(self.path(tool))
        return (["cmd", "/c", exe] if WINDOWS else [exe]) + [str(a) for a in args]

    def check(self) -> dict:
        """Each tool's reported version, or why it could not be run. A
        mismatch with the pinned release is an error the caller reports."""
        found = {}
        for tool, flag in (("v++", "--version"), ("vitis-run", "--version"), ("vivado", "-version")):
            p = self.path(tool)
            if not p.exists():
                found[tool] = {"ok": False, "why": f"not found at {p}"}
                continue
            try:
                r = subprocess.run(self.argv(tool, [flag]), capture_output=True, text=True, timeout=900)
            except subprocess.TimeoutExpired:
                found[tool] = {"ok": False, "why": "timed out reporting its version"}
                continue
            m = re.search(r"v(\d{4}\.\d)", r.stdout + r.stderr)
            got = m.group(1) if m else "unknown"
            found[tool] = {"ok": got == self.version, "version": got,
                           "why": "" if got == self.version else f"is {got}, pinned {self.version}"}
        return found

    def run(self, tool: str, args: list[str], log: Path, cwd: Path, timeout: float,
            echo=None) -> tuple[int, float]:
        """Run a tool to completion, its output to `log` (and each line to
        `echo`, if given). Returns (exit status, seconds). A timeout kills it
        and returns status -1."""
        log.parent.mkdir(parents=True, exist_ok=True)
        started = time.monotonic()
        with log.open("w", encoding="utf-8", errors="replace") as f:
            f.write("$ " + " ".join(self.argv(tool, args)) + "\n")
            f.flush()
            proc = subprocess.Popen(self.argv(tool, args), cwd=cwd, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, text=True, errors="replace")
            try:
                for line in proc.stdout:
                    f.write(line)
                    if echo:
                        echo(line.rstrip())
                    if time.monotonic() - started > timeout:
                        proc.kill()
                        f.write(f"\n*** killed after {timeout:.0f} s\n")
                        return -1, time.monotonic() - started
                status = proc.wait()
            finally:
                if proc.poll() is None:
                    proc.kill()
        return status, time.monotonic() - started
