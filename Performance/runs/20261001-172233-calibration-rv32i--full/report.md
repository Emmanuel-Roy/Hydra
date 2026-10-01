# calibration rv32i: full

Run `20261001-172233-calibration-rv32i--full`, commit `1f594c2+`, target `kv260_som`, tools 2026.1.

## Builds

| component | stage | result | time | LUT | FF | DSP | BRAM (18K / 36K) | URAM | clock (ns) | Fmax |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| calibration-rv32i | hls | ok | 30.3 s | 4,230 | 1,708 | 0 | 0 x18K | 0 | 6.58 | -- |
| calibration-rv32i | csim | ok | 5.6 s | -- | -- | -- | -- | -- | -- | -- |
| calibration-rv32i | cosim | ok | 31 s | -- | -- | -- | -- | -- | -- | -- |
| calibration-rv32i | impl | ok | 288 s | 2,310 | 1,573 | 0 | 0 x36K | 0 | 6.51 | 153.6 MHz |

## Against the previous comparable run

None: this is the first run of its kind.
