# regression check after targets

Run `20261001-011428-regression-check-after-targets`, commit `c0933b0+`, target `doomv-stub`, tools 2026.1.

Notes:

- DoomV stands in for the core: this proves the harness, not a design

## Accuracy (strict lock-step against DoomV)

| suite | tests | match | mismatch | error | skip | test passed | instructions | instructions/s | time |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| riscv-tests | 3 | 3 | 0 | 0 | 0 | 3 | 330 | 7,333 | 0.1 s |
| riscv-tests-priv | 3 | 3 | 0 | 0 | 0 | 3 | 756 | 5,362 | 0.1 s |

## Against the previous comparable run

None: this is the first run of its kind.
