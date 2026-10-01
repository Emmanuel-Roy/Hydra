# selftest: DoomV as the device under test

Run `20261001-010948-selftest--doomv-as-the-device-under-test`, commit `8a90047`, target `doomv-stub`, tools 2026.1.

Notes:

- DoomV stands in for the core: this proves the harness, not a design

## Accuracy (strict lock-step against DoomV)

| suite | tests | match | mismatch | error | skip | test passed | instructions | instructions/s | time |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| riscv-tests | 5 | 5 | 0 | 0 | 0 | 5 | 546 | 832 | 0.3 s |
| riscv-tests-priv | 5 | 5 | 0 | 0 | 0 | 5 | 1,098 | 7,038 | 0.1 s |

## Against the previous comparable run

None: this is the first run of its kind.
