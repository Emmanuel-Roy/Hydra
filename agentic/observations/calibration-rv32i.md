# Observed: the RV32I calibration core on kv260_som (2026.1)

Measured 2026-10-01. Test: `Tools/Verification/calibration/rv32i/` (a
five-stage RV32I in the style of `docs/hls-coding-standard.md`; test
infrastructure, not Ouroboros hardware). Run report:
`Performance/runs/20261001-172233-calibration-rv32i--full/`.
Target part xck26-sfvc784-2LV-c, clock request 100 MHz (10 ns).

| measure | value |
|---|---|
| pipelined loop | Target II = 1, **Final II = 1**, depth 3 (`HLS 200-1470`) |
| HLS estimate | 4,230 LUT, 1,708 FF, 0 DSP, 0 BRAM, 6.58 ns |
| after implementation | **2,310 LUT, 1,573 FF**, 0 DSP, 0 BRAM, 0 URAM |
| achieved clock | 6.51 ns → **153.6 MHz** (requested 10 ns, so this is not a ceiling) |
| C simulation | pass, 5.6 s |
| C/RTL co-simulation | pass, 31 s; same result as C simulation |
| implementation | 288 s |
| test program | 339 instructions in 466 cycles, **CPI 1.375** (fill, load-use stalls, 2-cycle taken-branch flush) |

What the numbers do and don't cover:

- The HLS estimate overstates LUTs by about 1.8x against implementation (4,230 vs 2,310).
- Instruction and data memories are top-level array ports, so their storage is not in these counts. Only the core is.
- Back-to-back `sb` / `lb` / `lbu` / `sh` / `lh` to the same word passed in co-simulation with `DEPENDENCE inter false` on the four byte lanes. The store in MEM and a later load reach MEM in different cycles. This is one program, not a proof.
- Fmax was measured against a 10 ns request. A tighter request has not been tried.

First attempt failed in the syntax check:
`HLS 207-3134 non-integral type 'ap_uint<4>' is an invalid underlying type`.
An `enum` cannot use `ap_uint<N>` as its underlying type. A plain `enum` fixed it.
