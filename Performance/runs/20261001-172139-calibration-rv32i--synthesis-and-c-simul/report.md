# calibration rv32i: synthesis and C simulation

Run `20261001-172139-calibration-rv32i--synthesis-and-c-simul`, commit `1f594c2+`, target `kv260_som`, tools 2026.1.

## Builds

| component | stage | result | time | LUT | FF | DSP | BRAM (18K / 36K) | URAM | clock (ns) | Fmax |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| calibration-rv32i | hls | ok | 30.4 s | 4,230 | 1,708 | 0 | 0 x18K | 0 | 6.58 | -- |
| calibration-rv32i | csim | ok | 9.1 s | -- | -- | -- | -- | -- | -- | -- |

## Against the previous comparable run

Previous: `20261001-171953-calibration-rv32i--synthesis-and-c-simul`.

No regressions.
