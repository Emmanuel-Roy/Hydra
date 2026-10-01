# Scripts

## `pipeline.py` -- build, test for accuracy, report on performance

Long, unattended runs: kick them off and read the report when they finish.

```sh
python scripts/pipeline.py check        # tools, part, DoomV, suites: ready or not, and why
python scripts/pipeline.py run          # every component, every stage, every suite
python scripts/pipeline.py run --components smoke --stages hls,csim,cosim,impl
python scripts/pipeline.py selftest     # the accuracy harness, with DoomV as the device under test
```

**Stages**, per HLS component (listed in `pipeline.toml`):

| stage | runs | reports |
|---|---|---|
| `hls` | `v++ -c --mode hls` | estimated LUT, FF, DSP, BRAM, URAM; estimated clock; latency and interval |
| `csim` | `vitis-run --mode hls --csim` | pass or fail |
| `cosim` | `vitis-run --mode hls --cosim` | pass or fail of the generated RTL against the C++ |
| `impl` | `vitis-run --mode hls --impl` | post-route resources, achieved clock, Fmax, timing met |
| `accuracy` | each test ELF on the device under test, then DoomV `-lockstep-strict` on its trace | matched / mismatched / errors per suite, instructions, simulation speed, the first divergence of each failure |

A component's `hls_config.cfg` never names a part or a clock: the pipeline
adds the target's into a generated config under `build/`, so the same
component builds for any target.

**Reports**: every run writes `Performance/runs/<id>/report.json` and
`report.md`, appends a line to `Performance/RUNS.md`, and compares itself
with the last run of the same kind (same components, target, stages and
suites). More than 2% more of any resource, a 2% slower clock, fewer tests
matching, or a 10% slower simulation is a regression. The exit status is
non-zero if anything failed or regressed, so a scheduler can act on it.

**Configuration**: `pipeline.toml`. Machine-specific paths come from the
environment: `OUROBOROS_AMD_ROOT` (the pinned AMD install) and
`OUROBOROS_DOOMV_ROOT` (a built DoomV checkout with its suites fetched).

**The self-test** runs DoomV in place of the core, so the accuracy stage is
proven end to end before the core exists; when a core component exists, its
`dut` command replaces DoomV's. It was also checked the other way: a device
that flips one bit of one register write is reported as a mismatch at that
instruction.

**The smoke component** (`Tools/Verification/smoke/`) is a trivial HLS kernel,
test infrastructure only, for proving the Vitis stages and their report
parsers against the pinned release.
