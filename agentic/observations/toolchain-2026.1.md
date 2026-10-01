# Observed: AMD 2026.1 toolchain behaviour on this host

Observed 2026-09/10 while bringing up `scripts/pipeline.py` against Z:\FPGA\2026.1.

## Licence tier
- The licence file held both `Vivado_Basic_Package` and `Vivado_Alveo_Package`. With both present, Vivado selected the ALVEO tier, which exposes 17 parts and not the K26. `create_project` on xck26 then failed with "part not found".
- `LICENSE_TIER_DIAGNOSTICS=1` prints the tier selection.
- A copy of the licence with only the Basic feature, at `%APPDATA%\XilinxLicenseBasic\Xilinx.lic`, set in `HKCU\Software\FLEXlm License Manager\XILINXD_LICENSE_FILE`, gave the BASIC tier and 1,958 visible parts, including the K26.
- Setting the `XILINXD_LICENSE_FILE` environment variable when launching Vivado *appends* that path to the registry value.

## Tool locations and commands
- `v++` and `vitis-run` are in `Vitis\bin`. `vivado` and `vlm.bat` are in `Vivado\bin`.
- `v++ -c --mode hls --config <cfg> --work_dir <dir>` synthesises. `vitis-run --mode hls --csim | --cosim | --impl` runs the rest.
- `flow_target` in hls_config is deprecated.
- `Vitis\data\installed.devices` (JSON) lists 59 families and 302 devices.
- The board store under `data\xhub\boards\XilinxBoardStore\boards` holds 45 boards (kv260_som 2.0, kv260_carrier).

## Report formats
- `csynth.xml`: `AreaEstimates/Resources` uses keys BRAM_18K, DSP, FF, LUT, URAM.
- `impl/report/verilog/export_impl.xml`: `AreaReport/Resources` uses BRAM (36K units), CLB, DSP, FF, LATCH, LUT, SRL, URAM. `TimingReport` has TargetClockPeriod and AchievedClockPeriod, but no TimingMet field.

## Smoke kernel (a MAC; `Tools/Verification/smoke/`) on kv260_som
| stage | time | result |
|---|---:|---|
| hls | 30 s | 265 LUT, 168 FF, 1 DSP, 2.44 ns est. |
| csim | 12 s | pass |
| cosim | 39 s | pass |
| impl | 260 s | 212 LUT, 266 FF, 1 DSP, 31 CLB, 2.5 ns achieved (400 MHz) |

The fixed overhead per component is about 30 s for HLS, about 30-40 s for cosim and 4-5 min for implementation, even for trivial kernels.
