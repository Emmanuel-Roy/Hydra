# selftest: DoomV as the device under test

Run `20261001-011053-selftest--doomv-as-the-device-under-test`, commit `8a90047`, target `doomv-stub`, tools 2026.1.

Notes:

- DoomV stands in for the core: this proves the harness, not a design

## Accuracy (strict lock-step against DoomV)

| suite | tests | match | mismatch | error | skip | test passed | instructions | instructions/s | time |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| riscv-tests | 173 | 173 | 0 | 0 | 0 | 173 | 71,202 | 8,648 | 2.1 s |
| riscv-tests-priv | 24 | 24 | 0 | 0 | 0 | 24 | 4,083 | 3,900 | 0.3 s |

## Against the previous comparable run

None: this is the first run of its kind.
