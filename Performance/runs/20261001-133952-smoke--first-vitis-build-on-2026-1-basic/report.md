# smoke: first Vitis build on 2026.1 Basic

Run `20261001-133952-smoke--first-vitis-build-on-2026-1-basic`, commit `a50c402`, target `kv260_som`, tools 2026.1.

## Builds

| component | stage | result | time | LUT | FF | DSP | BRAM | URAM | clock (ns) | Fmax |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| smoke | hls | ok | 30.0 s | 265.0 | 168.0 | 1.0 | 0.0 | 0.0 | 2.44 | -- |
| smoke | csim | ok | 11.8 s | -- | -- | -- | -- | -- | -- | -- |
| smoke | cosim | ok | 39.1 s | -- | -- | -- | -- | -- | -- | -- |
| smoke | impl | ok | 259.9 s | 212.0 | 266.0 | 1.0 | -- | 0.0 | 2.5 | 400.0 MHz |

## Against the previous comparable run

None: this is the first run of its kind.
