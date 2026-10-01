# Ouroboros configurator: CPU-core and software-stack levers (single-hart RVA23S64-capable HLS core + Ubuntu riscv64)

Scope: the CPU and software choices for Ouroboros, an FPGA laptop: a single-hart RISC-V core in Vitis HLS C++ with a simple stalling pipeline, V at VLEN=128 with a configurable datapath, and H. It boots Ubuntu riscv64. First board is the KV260 (XCK26: 117K LUT, 1248 DSP, 144 BRAM36, 64 URAM), and it shares the FPGA with an LLM systolic-array accelerator.

Labels used below:
- **[est]** marks an estimate that is not taken from a source.
- **T1/T2/T3** proposes a tier: always asked / expanded / full.

As of 2026-10-01.

---

## 1. ISA scope levers: profile ladder, optional extensions, dependencies, and distro requirements

### Takeaway
RVA23S64 has a large mandatory set, including V, H (through Sha), Sstc, Sscofpmf, Svnapot, Ssnpm/Supm, Zicond, Zimop/Zcmop, Zcb, Zfa, Zawrs, Zvbb, Zvkt and Zvfhmin. On top of that it allows a short list of real options: Sv48, Sv57, Zkr, Svadu, Sdtrig, Ssstrict, Svvptc and Sspm (privileged), plus Zfh, Zbc, Zicfilp, Zicfiss, Zvfh, Zfbfmin, Zvfbfmin, Zvfbfwma, Zabha, Zacas, Ziccamoc, Zvbc, Zama16b, Zvkng and Zvksg (unprivileged).

Dropping any mandatory piece leaves the profile, which means leaving Ubuntu 25.10/26.04+. Ubuntu 24.04 LTS (RVA20/RV64GC), Debian 13 and Fedora still accept a plain RV64GC core.

### Cited Findings

**RVA23U64 mandatory set**
- Inherited from RVA22U64: RV64I plus M, A, F, D, C, B, Zicsr, Zicntr, Zihpm, Ziccif, Ziccrse, Ziccamoa, Zicclsm, Za64rs, Zihintpause, Zic64b, Zicbom, Zicbop, Zicboz, Zfhmin and Zkt — [RVA23 profile spec](https://github.com/riscv/riscv-profiles/blob/main/src/rva23-profile.adoc)
- New in RVA23U64: V (optional in RVA22U64), Zvfhmin, Zvbb, Zvkt, Zihintntl, Zicond, Zimop, Zcmop, Zcb, Zfa, Zawrs and Supm — [RVA23 profile spec](https://github.com/riscv/riscv-profiles/blob/main/src/rva23-profile.adoc)

**RVA23U64 options**
- Localized options: Zvkng and Zvksg. The scalar crypto extensions Zkn/Zks, which were RVA22 options, are not RVA23 options — [RVA23 profile spec](https://github.com/riscv/riscv-profiles/blob/main/src/rva23-profile.adoc)
- Development options, expected to become mandatory later: Zabha, Zacas, Ziccamoc, Zvbc and Zama16b — [RVA23 profile spec](https://github.com/riscv/riscv-profiles/blob/main/src/rva23-profile.adoc)
- Expansion options: Zfh (carried over from RVA22), plus new Zbc, Zicfilp, Zicfiss, Zvfh, Zfbfmin, Zvfbfmin and Zvfbfwma — [RVA23 profile spec](https://github.com/riscv/riscv-profiles/blob/main/src/rva23-profile.adoc)

**RVA23S64 mandatory set**
- Everything in RVA23U64, plus Zifencei. Zifencei is kept because it is the "only standard way to support instruction-cache coherence" — [RVA23 profile spec](https://github.com/riscv/riscv-profiles/blob/main/src/rva23-profile.adoc)
- Privileged: Ss1p13, Svbare, Sv39, Svade, Ssccptr, Sstvecd, Sstvala, Sscounterenw, Svpbmt and Svinval — [RVA23 profile spec](https://github.com/riscv/riscv-profiles/blob/main/src/rva23-profile.adoc)
- New privileged mandatory pieces: Svnapot, Sstc, Sscofpmf, Ssnpm and Ssu64xl — [RVA23 profile spec](https://github.com/riscv/riscv-profiles/blob/main/src/rva23-profile.adoc)
- Sha (Augmented Hypervisor) is mandatory. It is H + Ssstateen + Shcounterenw + Shvstvala + Shtvala + Shvstvecd + Shvsatpa + Shgatpa — [RVA23 profile spec](https://github.com/riscv/riscv-profiles/blob/main/src/rva23-profile.adoc)

**RVA23S64 privileged options**
- Expansion options only: Sv48, Sv57 and Zkr (from RVA22), plus new Svadu, Sdtrig, Ssstrict, Svvptc and Sspm. There are no localized, development or transitory privileged options — [RVA23 profile spec](https://github.com/riscv/riscv-profiles/blob/main/src/rva23-profile.adoc)

**Extension dependencies**
- V requires Zvl128b (VLEN ≥ 128) and scalar F and D. It must implement vector FP for EEW=32 and EEW=64, including widening and FP32↔FP64 conversions — [LLVM RISC-V usage / V spec text](https://rocm.docs.amd.com/projects/llvm-project/en/latest/LLVM/llvm/html/RISCVUsage.html), [FPRox taxonomy](https://fprox.substack.com/p/taxonomy-of-risc-v-vector-extensions)
- Zve32f and Zve64f require scalar F (or Zfinx). Zve64d requires D and Zve64f — [LLVM RISC-V usage](https://rocm.docs.amd.com/projects/llvm-project/en/latest/LLVM/llvm/html/RISCVUsage.html), [Linux DT extensions.yaml](https://www.kernel.org/doc/Documentation/devicetree/bindings/riscv/extensions.yaml)
- The Linux DT schema encodes these rules:
  - D ⇒ F
  - B ⇔ Zba + Zbb + Zbs
  - Supm ⇒ Smnpm or Ssnpm
  - Za64rs and Ziccrse ⇒ A or Zalrsc
  - Zcb ⇒ Zca; Zcd ⇒ Zca + D
  - Zcf is forbidden on RV64
  - Zve32f ⇒ F + Zve32x; Zve64d ⇒ D + Zve64f
  - Vector crypto (Zvbb, Zvkt and the rest) ⇒ V or Zve32x/Zve64x

  Source: [Linux DT extensions.yaml](https://www.kernel.org/doc/Documentation/devicetree/bindings/riscv/extensions.yaml)
- Whether Zvfh implies Zve32f and Zfhmin was a spec-clarification topic — [riscv-v-spec issue #844](https://github.com/riscvarchive/riscv-v-spec/issues/844)
- H requires an RV32I/RV64I base (not RV32E). It adds G-stage translation through hgatp. With HSXLEN=64, hgatp supports Bare, Sv39x4, Sv48x4 and Sv57x4, so Sv48x4/Sv57x4 only come along when Sv48/Sv57 are implemented — [Priv spec, Hypervisor chapter](https://five-embeddev.github.io/riscv-docs-html/riscv-priv-isa-manual/latest-adoc/hypervisor.html)

**Distro baselines**
- Ubuntu 25.10 made RVA23 the minimum baseline. The linux-riscv kernel only supports RVA23S64 hardware. Older hardware stays on 24.04 LTS or 25.04 — [Phoronix](https://www.phoronix.com/news/Ubuntu-25.10-To-Require-RVA23), [Ubuntu 25.10 release notes](https://documentation.ubuntu.com/release-notes/25.10/)
- Ubuntu 26.04 LTS ships with RVA23 as its "unified, long-term supported baseline" — [Canonical blog](https://ubuntu.com/blog/canonical-and-ubuntu-risc-v-a-2025-retro-and-looking-forward-to-2026)
- RVA20 users can get up to 15 years of support on 24.04 LTS with Ubuntu Pro — [Canonical blog](https://ubuntu.com/blog/canonical-and-ubuntu-risc-v-a-2025-retro-and-looking-forward-to-2026)
- At the 25.10 release, QEMU virtualization was the only supported RISC-V platform — [Phoronix](https://www.phoronix.com/news/Ubuntu-25.10-RISC-V-QEMU)
- Debian 13 "Trixie" (Aug 2025) builds for RV64GC with the lp64d ABI. Debian 14 "Forky" (expected mid-2027) is expected to move "at most to RVA20U64" — [RISCstar](https://riscstar.com/blog/rva23-from-ratification-to-real-world-readiness/)
- Fedora stays on RV64GC. RHEL 10 riscv64 is a Developer Preview on RV64GC. SLES 16 has no RISC-V SKU. As of July 2026, none of Debian, Fedora, RHEL or SUSE had adopted RVA23 — [RISCstar](https://riscstar.com/blog/rva23-from-ratification-to-real-world-readiness/), [Fedora wiki](https://fedoraproject.org/wiki/Architectures/RISC-V)
- The first RVA23 SoC is the SpacemiT K3. K3 single-board computers went on retail sale in May 2026 — [RISCstar](https://riscstar.com/blog/rva23-from-ratification-to-real-world-readiness/)

### Inferences

**ISA ladder for a configurator (T1 "ISA profile" question)**

| Rung | Contents | What it boots |
|---|---|---|
| RV64IMAC | No FPU | Buildroot/custom images only; no stock distro |
| RV64GC / RVA20 | IMAFDC + Zicsr + Zifencei + Zicntr; Sv39 | Ubuntu 24.04 LTS, Debian 13/14, Fedora, Buildroot |
| RVA22S64 | Adds B, Zicbo*, Zfhmin, Zkt, Zihpm, Svpbmt, Svinval, etc. | Same distros, more optimized code paths; no distro requires it |
| RVA23S64 | Adds V, Sha/H, Sstc, Sscofpmf, Svnapot, Zicond, Zfa, Zcb, Zimop, Zawrs, Supm/Ssnpm, Zvbb, Zvkt, Zvfhmin | Ubuntu 25.10, 26.04 LTS and later |

**Per-option rows to expose (T2/T3), with resource cost [est]**
- **Sv48 / Sv57.** One or two extra page-walk levels and wider TLB tags. Small cost; only worth it with more than 39 bits of VA. T3.
- **Zicfilp / Zicfiss (CFI).**
  - Zicfilp needs a landing-pad state machine.
  - Zicfiss needs shadow-stack loads/stores, PTE encoding and an `ssp` CSR.
  - Moderate decode/LSU work. The kernel and glibc need CFI support turned on.
  - T2, default off.
- **Zacas / Zabha.** CAS (incl. 128-bit amocas.q on RV64) and byte/halfword AMOs. In a single-hart, stalling design these are a few microcoded LSU sequences. Small cost. T2, default on if cheap.
- **Zfh / Zvfh.**
  - Full FP16 arithmetic in the FPU and vector FPU.
  - Zfhmin and Zvfhmin (conversions only) are mandatory anyway.
  - Moderate DSP/LUT cost, but useful for an LLM laptop.
  - T2.
- **Zfbfmin / Zvfbfmin / Zvfbfwma.** BF16 conversions and widening MAC. Relevant to LLM work. T2.
- **Zbc, Zvbc.** Carry-less multiply, about one 64×64 GF(2) multiplier [est]. T3.
- **Zvkng / Zvksg (vector crypto).** Large LUT cost (AES/SHA tables). T3, default off.
- **Zkr.** Entropy source. It needs a hardware TRNG on the FPGA (ring oscillators), which affects portability. T3.
- **Sdtrig.** Debug triggers. T3.
- **Svadu.** Hardware A/D-bit update, so the PTW must write. T3.
- **Ssstrict, Svvptc, Sspm.** Mostly behavioral. T3.

**Hard dependency rules for the validator**
- V ⇒ F + D + Zvl128b.
- Profile RVA23 ⇒ V + H(Sha) + Sstc + Sscofpmf + Zicboz/m/p + B + Zfa + Zcb + Zicond + Zimop + Zcmop + Zawrs + Supm/Ssnpm + Zvbb + Zvkt + Zvfhmin + Zfhmin.
- H ⇒ S-mode + Sv39 (+ Sv39x4). Sv48 ⇒ Sv48x4 when H is present.
- Zvfh ⇒ Zvfhmin + Zfhmin.
- Zicfiss ⇒ A + Zimop/Zcmop. Zimop is what keeps CFI binaries backward-compatible on hardware without CFI.
- A V subset (Zve64d, Zve32x) excludes the RVA23 profile and Ubuntu 25.10+.

**Distro row in the configurator**
- Ubuntu 26.04 LTS (and 25.10+) requires RVA23S64.
- Ubuntu 24.04 LTS, Debian 13, Fedora and Buildroot accept RV64GC.
- If any RVA23 mandatory item is unchecked, the UI should grey out Ubuntu ≥25.10.

**Trapping and emulating instead of implementing in hardware [est]**
- Some mandatory items could in principle be trapped and emulated in M-mode (OpenSBI), for example misaligned access (Zicclsm) or rarely used vector-crypto ops.
- This is legal only where the spec allows it. Zicclsm explicitly allows slow misaligned access.
- Emulating V or H in firmware is impractical.
- A T3 "emulate in M-mode" toggle per extension is possible but it is a performance cliff.

### Gaps
- I did not fetch the full RVA20/RVA22 profile texts. RVA22 contents above are inferred from RVA23's "from RVA22" lists.
- I found no primary source stating which `-march` Ubuntu 25.10/26.04 userspace is compiled with (e.g. `rva23u64` vs `rv64gcv`). Secondary reports say "RVA23 required" without naming the flag.
- I could not confirm whether Ubuntu's 26.04 kernel refuses to boot when an RVA23 extension is missing, or only that userspace may fault with SIGILL.

---

## 2. Microarchitecture levers (vector width, FPU, mul/div, branch prediction, caches, TLB, PMP, counters, clock, pipeline, PA width)

### Takeaway
Every open generator exposes the same core set of microarchitecture parameters:
- cache sets/ways/line size
- BTB, BHT and RAS sizes
- PMP count
- performance counter count
- TLB entries
- FPU present/absent and div/sqrt on/off
- mul/div speed
- vector VLEN/DLEN (and lanes)

They differ in how they constrain combinations. Ara enforces VLEN ≥ 64·NrLanes. Rocket requires a BTB for any predictor. VexiiRiscv requires the BTB for gshare and RAS.

For Ouroboros, the largest resource lever is the vector datapath width (DLEN at 32/64/128 bits with VLEN fixed at 128). Next come the FPU (FMA, FP16/BF16) and the L1/L2 sizes, which compete with the accelerator for BRAM and URAM.

### Cited Findings

**Saturn (UCB vector unit)**
- Supports full V, Zve64d, Zvfh and Zvbb. VLEN can be 64–1024 (Zvl64b to Zvl1024b). The SIMD datapath is configurable at 64/128/256/512+ bits. It has full chaining and precise traps with virtual memory — [saturn-vectors GitHub](https://github.com/ucb-bar/saturn-vectors)
- The recommended config is `GENV256D128ShuttleConfig`: VLEN 256, DLEN 128, dual-issue Shuttle core, with separate FP and integer vector issue units. Another example is `REFV512D256RocketConfig`. Configs live in `generators/chipyard/src/main/scala/config/SaturnConfigs.scala` — [Chipyard Saturn docs](https://chipyard.readthedocs.io/en/1.12.3/Generators/Saturn.html)
- Chime length = VLEN/DLEN. This is the key lever for "datapath narrower than VLEN" designs — [Saturn scheduling paper](https://arxiv.org/html/2412.00997)

**Ara (PULP vector unit)**
- Parametrized by NrLanes and VLEN. The lane datapath is 64 bits, so NrLanes is effectively DLEN/64. The RTL supports VLEN 128/256/512 — [Ara2 paper](https://arxiv.org/pdf/2311.07493), [Ara PR #484](https://github.com/pulp-platform/ara/pull/484)
- Ara requires VLEN ≥ 64·NrLanes. VLEN=128 with 4 lanes silently aliases all vector registers, and PR #484 adds a check for it — [Ara PR #484](https://github.com/pulp-platform/ara/pull/484)
- The tapeout config was VLEN 512 with 4 lanes, because area "increases significantly with the number of lanes" — [Ara PR #484 / search summary](https://github.com/pulp-platform/ara/pull/484)

**CVA6 (`cv64a6_imafdch_sv39`, the H-enabled config)**
- ISA switches:
  - XLEN=64, RVF=1, RVD=1
  - F16En=0, F16AltEn=0, F8En=0, FVecEn=0
  - CExt=1, ZcbExt=1, ZcmpExt=0, AExt=1, HExt=1, BExt=1, VExt=0, ZiCond=1
  - CvxifEn=1 (the CV-X-IF coprocessor interface)
- Caches:
  - I$ 16 KiB, 4-way, 128-bit line
  - D$ 32 KiB, 8-way, 128-bit line, write-through, write buffer depth 8
- Pipeline: NrScoreboardEntries=8, NrLoadPipeRegs=1, NrStorePipeRegs=0, NrLoadBufEntries=2
- Branch prediction: RASDepth=2, BTBEntries=32, BHTEntries=128
- Protection and debug: NrPMPEntries=8, PerfCounterEn=1, MmuPresent=1, TvalEn=1, RvfiTrace=1
- AXI: addr 64, data 64, ID 4

  Source: [CVA6 config pkg](https://github.com/openhwgroup/cva6/blob/master/core/include/cv64a6_imafdch_sv39_config_pkg.sv)

**Rocket Chip config fragments**
- Core presets:
  - `WithNHugeCores`: FP16, Zba/Zbb/Zbs, 64-set/8-way caches
  - `WithNBigCores`
  - `WithNMedCores`: no FPU, 1-way caches
  - `WithNSmallCores`: no FPU, no VM, 1-way caches
  - `With1TinyCore`: RV32 with a 16 KB scratchpad
- Cache and TLB fragments:
  - `WithL1ICacheSets/Ways/ECC/RowBits`
  - `WithL1ICacheTLBSets/Ways/BasePageSectors/Superpages`
  - `WithL1DCacheSets/Ways/RowBits/ECC`
  - `WithL1DCacheNonblocking(nMSHRs)`
  - `WithL1DCacheDTIMAddress`
- ISA and feature fragments:
  - `WithRV32`, `WithoutVM`, `WithZba/Zbb/Zbs/WithB`
  - `WithSV39/SV48`
  - `WithoutFPU`, `WithFP16`
  - `WithFastMulDiv`, `WithoutMulDiv`
- Clock fragments: `WithSynchronousCDCs`, `WithAsynchronousCDCs`

  Source: [rocket-chip Configs.scala](https://github.com/chipsalliance/rocket-chip/blob/master/src/main/scala/rocket/Configs.scala)

**VexiiRiscv (LiteX-integrated)**
- ISA and privilege flags: `--xlen=32/64`, `--with-rvm`, `--with-rvc`, `--with-rva`, `--with-rvf`, `--with-rvd`, `--with-supervisor`, `--with-mmu`, `--pmp-size`
- Branch prediction: `--with-btb`, `--with-gshare` and `--with-ras` (the last two "Require the BTB to be enabled")
- Pipeline and timing: `--regfile-async` ("shaving one stage"), `--allow-bypass-from=N`, `--with-late-alu`, `--relaxed-branch/shift/src`, `--decoders`, `--lanes`
- Caches: `--fetch-l1[-ways]` and `--lsu-l1[-ways|-sets]` (4 KB per way by default), plus `--lsu-l1-refill-count`, `--lsu-l1-writeback-count` and `--lsu-l1-store-buffer-ops/slots`
- Other: `--performance-counters N`, `--with-jtag-tap`
- LiteX passes these through `--vexii-args="..."`.

  Sources: [VexiiRiscv How To Use](https://spinalhdl.github.io/VexiiRiscv-RTD/master/VexiiRiscv/HowToUse/index.html), [VexiiRiscv LiteX](https://spinalhdl.github.io/VexiiRiscv-RTD/master/VexiiRiscv/Soc/litex.html)

**NaxRiscv**
- Built from an "empty toplevel parameterized with plugins".
- Supports RV32/RV64 IMAFDCSU, configurable decode and execution width (e.g. 2 decode, 3 execution units, 2 retire), BTB/GSHARE/RAS, Sv32/Sv39 with hardware refill, and a non-blocking D$ with configurable refill/writeback slots.
- Boots Linux/Buildroot via LiteX.
- It targets "low area usage and high fmax (not the best IPC)".

  Source: [NaxRiscv GitHub](https://github.com/SpinalHDL/NaxRiscv)

**SiFive commercial reference points**
- U74 branch unit: 16-entry BTB, 3.6 KiB BHT, 6-entry RAS, 8-entry indirect-jump predictor, 16-entry return predictor. PMP has 8 regions with 4 KiB granularity — [SiFive U74 manual](https://www.scs.stanford.edu/~zyedidia/docs/sifive/sifive-u74.pdf)
- E76 PMP has 8 regions with 64 B granularity — [E76-MC manual](https://starfivetech.com/uploads/e76mc_core_complex_manual_21G1.pdf)

**XiangShan**
- `MinimalConfig`: RobSize 48, 32 KB L1D, 128 KB L2. `DefaultConfig` has a 2 MB L2. Both are in `top/Configs.scala` — [XiangShan tutorial](https://tutorial.xiangshan.cc/hpca26/hands_on/tutorial-en/) (via search summary; secondary)

### Inferences

All resource numbers below are **[est]** for an in-order HLS core on UltraScale+, unless a source is given.

**Vector datapath width DLEN (T1)**

| Option | Throughput | Cost [est] |
|---|---|---|
| 32-bit | 4 beats per LMUL=1 op | ~4 DSP per 32-bit MAC slice; cheapest; FP64 lanes go iterative |
| 64-bit | 2 beats | ~2× the 32-bit cost |
| 128-bit | 1 beat (full) | ~4× the 32-bit cost; at VLEN=128, 1 element-group per cycle |

- Dependency: DLEN ≤ VLEN. VLEN ≥ 128 is required for V.
- VLEN choices: 128 (fixed by the owner's design), 256 or 512 (T3).
  - VRF = 32×VLEN bits: 4 Kbit at VLEN=128, about 1–2 BRAM36 or LUTRAM depending on read ports.
  - Software impact: none if the code is VLEN-agnostic. Debian/Ubuntu binaries are VLA. The kernel saves 32×VLEN/8 bytes of vector context per task.

**Vector "lanes" vs SIMD width**
- With a single-hart stalling pipeline, Ara-style lanes and Saturn-style DLEN are the same lever. Expose it as "vector datapath width" plus an advanced option "number of 64-bit lanes = DLEN/64".

**Which vector ops can be slow sequencers (T2 checklist)** [est]
- vdiv/vrem, vfdiv/vfsqrt (iterative)
- vrgather/vcompress and slides (permute network vs element-serial)
- indexed and segmented loads/stores (element-serial)
- reductions (log-tree vs serial)
- vector crypto Zvbb/Zvkt clz/ctz/brev (cheap); Zvbc clmul (iterative option)
- widening FP (2× beats)

Each one is a "fast / serial" toggle that trades LUTs for cycles. Saturn and Ara both keep divide and permute ops iterative or serial.

**Scalar FPU (T1/T2)**
- Options: FMA-pipelined (2–5 stage) / shared with the vector FPU / iterative non-FMA. Div/sqrt: iterative radix-2 or radix-4, or omitted and trapped (Rocket has a `WithFPUWithoutDivSqrt`-style option).
- Sharing the scalar FPU with vector lane 0 saves about 1 FMA-equivalent of DSP. In-order cores tolerate this because scalar FP and vector FP rarely overlap [est].
- Zfh/Zfa raise LUT cost modestly.
- Dependency: V requires D. "No FPU" forces leaving RVA23 (and Ubuntu, which needs lp64d).

**Mul/div (T2)**
- Multiplier: 1-cycle DSP (≈4–16 DSP48E2 for 64×64 [est]) / pipelined 2–4 cycle / iterative (Rocket `WithFastMulDiv` vs default).
- Divider: radix-2 iterative (~64 cycles) / radix-4 / with early-out.
- No software change.

**Branch prediction (T1 summary, T2 sizes)**

| Preset | Contents |
|---|---|
| none | Predict not-taken |
| static | BTFN |
| BHT | 2-bit counters, 64–4K entries |
| BTB | 8–64 entries |
| RAS | 2–16 deep |
| gshare | Requires the BTB |

- Reference points: CVA6 default is 128 BHT / 32 BTB / RAS 2; U74 is 16 BTB / 3.6 KiB BHT / RAS 6.
- Rule: RAS and gshare require the BTB (VexiiRiscv).
- Cost: mostly LUTRAM/BRAM, small.
- With a simple stalling pipeline (short taken-branch penalty), the IPC gain is small [est].

**L1 I$/D$ (T1 size, T2 ways and line)**
- Size 4–64 KiB, ways 1–8, line 32–128 B. Reference: CVA6 uses 16 KiB 4-way I$ and 32 KiB 8-way D$ with 128-bit lines.
- Each 4 KiB is about 1 BRAM36, plus tags [est].
- Write-through vs write-back is T3. CVA6 exposes both (`DcacheType` WT/WB).

**L2 (T1 yes/no, T2 size)**
- Options: none / 64–512 KiB in URAM (each URAM288 = 36 KB; 64 URAM ≈ 2.25 MB total on the XCK26 [est from 288 Kbit/URAM]).
- Shares URAM with the accelerator's weight and activation buffers. This is the main contention point.

**TLB (T2)**
- ITLB/DTLB 4–64 entries (fully associative or set-associative). Optional shared L2 TLB of 64–1024 entries. Superpage entries (Rocket exposes TLB sets/ways/superpages).
- Svnapot (RVA23-mandatory) adds 64 KiB NAPOT matching.
- H adds VS-stage + G-stage two-stage walks. That calls for a G-stage TLB or a combined-entry TLB, and the page walk becomes up to about 15 memory accesses on a miss with Sv39x4 [est].

**PMP entries (T2)**
- Range 0/8/16/64. OpenSBI needs several entries (≥ about 2–4) to protect itself.
- CVA6 and SiFive default to 8. Granularity is 4 KiB (U74) or 64 B.

**Performance counters (T2)**
- mhpmcounter3..31 (0–29 counters).
- Sscofpmf (RVA23-mandatory) requires overflow interrupts and mode filtering on implemented counters.
- Sscounterenw requires that any implemented counter be writable-enableable by S-mode.
- Linux perf needs Sscofpmf for sampling.

**Clock target (T1)**
- Shown as a target, e.g. 100–300 MHz on Zynq UltraScale+ [est for an HLS in-order core].
- Drives HLS pipeline II and depth. Software impact: `timebase-frequency` in the DT (the mtime/Sstc clock can be fixed, e.g. 10 MHz, independent of the core clock).

**Pipeline depth (T2)**
- HLS lets you choose 3–7 stages. More stages raise fmax but lengthen stalls.
- The VexiiRiscv `--regfile-async` and `--allow-bypass-from` options show this lever exposed directly.

**Physical address width (T2)**
- 32–56 bits. Sv39 PTEs carry a 44-bit PPN, so PA ≤ 56.
- The KV260 DDR (4 GB) needs ≥ 33 bits, plus room for the accelerator MMIO.
- Software impact: DT memory and reg nodes; no recompile.

**Other T3 rows**
- Misaligned access in hardware vs trap-to-SBI (Zicclsm allows either; trapping is very slow).
- Cache ECC.
- Debug module (JTAG/Sdtrig).
- CV-X-IF-like coprocessor port, which is a natural attach point for the LLM accelerator. CVA6 exposes `CvxifEn`.

### Gaps
- I found no published FPGA LUT/DSP/BRAM numbers per configuration for Saturn or Ara on UltraScale+ that I could verify. All resource numbers above are estimates.
- I could not fetch the SiFive Core Designer option screens. The public blog only lists series selection (2/3/5/7), RV32E, F/D, SCIE custom instructions, optional L2, μI-cache/ITIM/DLS, up to 8 cores and a "Fast IO" option ([SiFive blog](https://www.sifive.com/blog/sifive-core-designer-adds-three-new-core-series)).
- I found no public detail on Andes AndesCore or Codasip Studio configurators within the search budget.
- I did not obtain the exact Rocket defaults for BTB/BHT/RAS and PMP count (`nPMPs`=8 and `nPerfCounters` are commonly cited, but I did not verify them here).

---

## 3. Software and platform levers that follow from hardware choices

### Takeaway
Linux detects most extensions at runtime from the device tree (`riscv,isa-extensions`) and patches itself through `RISCV_ALTERNATIVE`. As a result, toggling an optional extension usually needs only a DT edit, not a kernel rebuild.

A rebuild or reconfiguration becomes mandatory when:
- the profile drops below what the distro was compiled for (userspace breaks, not just the kernel)
- the memory map changes (OpenSBI FW_JUMP/FW_PAYLOAD addresses, kernel PHYS_RAM_BASE if fixed)
- the custom M-mode emulation or platform code changes

With OpenSBI's generic platform and FW_DYNAMIC, firmware can be reused across hardware variants because everything is driven by the DT.

### Cited Findings

**Kernel Kconfig**
- `RISCV_ISA_V` adds vector support "when detected at boot". It depends on toolchain support and FPU.
- `RISCV_ISA_V_DEFAULT_ENABLE` turns V on for userspace by default; otherwise processes must enable it with prctl().
- `RISCV_ISA_V_PREEMPTIVE` allows kernel-mode V with preemption, at a per-task memory cost.

  Source: [Linux arch/riscv/Kconfig](https://github.com/torvalds/linux/blob/master/arch/riscv/Kconfig)
- These are all detected at boot and patched through `RISCV_ALTERNATIVE`: `RISCV_ISA_ZBA/ZBB/ZBKB`, `ZACAS`, `ZABHA`, `ZAWRS`, `ZICBOM` (non-coherent DMA), `ZICBOZ`, `ZICBOP`, `SVNAPOT`, `SVPBMT` and `SUPM` (pointer masking via prctl) — [Linux arch/riscv/Kconfig](https://github.com/torvalds/linux/blob/master/arch/riscv/Kconfig)
- `RISCV_ISA_C=n` produces a non-portable kernel. `PHYS_RAM_BASE` is fixed only under `NONPORTABLE` + `PHYS_RAM_BASE_FIXED`. `CMODEL_MEDANY` applies to RV64. `RISCV_SBI_V01` is legacy — [Linux arch/riscv/Kconfig](https://github.com/torvalds/linux/blob/master/arch/riscv/Kconfig)
- In the DT, `riscv,isa` is deprecated in favour of `riscv,isa-base` plus the `riscv,isa-extensions` string array. The schema validates extension dependencies — [extensions.yaml](https://www.kernel.org/doc/Documentation/devicetree/bindings/riscv/extensions.yaml)

**OpenSBI**
- Firmware types:
  - FW_PAYLOAD embeds the next stage.
  - FW_JUMP jumps to a static address.
  - FW_DYNAMIC receives next-stage info from the previous loader.
- The generic platform is FDT-driven, so custom platforms need no platform.c when they use generic + FDT.

  Sources: [OpenSBI docs](https://github.com/riscv/opensbi/blob/master/docs/platform/sifive_fu540.md), [OpenSBI build/config (DeepWiki)](https://deepwiki.com/riscv-software-src/opensbi/9-building-and-configuration), [OpenSBI Deep Dive](https://riscv.org/wp-content/uploads/2024/12/13.30-RISCV_OpenSBI_Deep_Dive_v5.pdf)
- Linux can be a direct payload of OpenSBI, skipping U-Boot (the "LinuxBoot / direct payload" approach) — [RVspace forum](https://forum.rvspace.org/t/osf-linuxboot-linux-as-a-direct-payload-to-opensbi/3345)

### Inferences

**Rebuild matrix**

| Change | OpenSBI | Kernel | DT | Userspace / distro |
|---|---|---|---|---|
| Toggle optional extension (Zacas, Zabha, Zicfi*, Zfh, Sv48/57, Svadu) | no (unless emulating it) | no, if the CONFIG is built in and the extension is runtime-detected | **yes** (`riscv,isa-extensions`, `mmu-type`) | no |
| Cache/BP/TLB/pipeline size | no | no | optional (cache size nodes are informational) | no |
| PMP count / counters | no (OpenSBI probes PMP; counters via the `riscv,pmu` DT node) | no | yes for the PMU event map | no |
| VLEN change | no | no (`vlenb` is read from a CSR) | no | no (VLA code) |
| Drop V/H/etc. below RVA23 | no | Ubuntu's linux-riscv may refuse or degrade; custom kernel fine | yes | **switch distro** to 24.04/Debian/Fedora |
| Drop D/F (no FPU) | no | yes (`FPU=n`, lp64 ABI) | yes | **custom Buildroot only** (all distros are lp64d) |
| Memory map / DDR base / accelerator carve-out | **yes** for FW_JUMP/PAYLOAD addresses (FW_DYNAMIC avoids it) | no (unless PHYS_RAM_BASE_FIXED) | **yes** (`memory`, `reserved-memory`) | no |
| Add M-mode emulation of missing extensions | **yes** (custom OpenSBI) | no | maybe | no |
| Timer (Sstc) / CLINT / PLIC vs AIA | no for generic | no | yes | no |

**Prebuilt vs custom images**
- Ubuntu publishes generic riscv64 images (the "QEMU-only" supported platform). Ouroboros can reuse the Ubuntu rootfs and kernel and supply only its own OpenSBI + DT (+ optional U-Boot).
- This works when the core is truly RVA23S64 and uses standard interrupt controllers: CLINT/ACLINT + PLIC, or AIA.

**Bootloader lever (T2)**
- OpenSBI FW_PAYLOAD → U-Boot → extlinux/GRUB: distro-friendly, kernel upgrades through apt work.
- OpenSBI FW_PAYLOAD → Linux directly: faster and smaller, but kernel updates require reflashing.
- The KV260's PS (Cortex-A53) could also act as the loader that places images in DDR, which favours FW_DYNAMIC [est].

**Kernel command line and memory levers (T2)**
- Use `mem=` or DT `reserved-memory` (no-map) for the accelerator's DDR carve-out (e.g. 512 MB–2 GB of the KV260's 4 GB [est]).
- Use a CMA region if accelerator buffers are shared through dma-buf.
- Set `console=` to the UART chosen.
- `riscv_isa_fallback` exists for old `riscv,isa` strings.

**Coherence and Zicbom**
- If the accelerator does DMA into DDR without coherence, Zicbom (RVA23-mandatory) plus the DT `dma-noncoherent` property let Linux manage cache maintenance.
- This makes Zicbom important for Ouroboros, not just a profile checkbox [inference from the `RISCV_ISA_ZICBOM` help text].

**H extension software**
- Enable KVM (`CONFIG_KVM`). OpenSBI must delegate VS-level traps.
- H is only useful if the user wants VMs, but RVA23 and Ubuntu 25.10+ require it to be present regardless.

### Gaps
- I found no authoritative statement on exactly which RVA23 extensions Ubuntu's 26.04 generic kernel *requires at boot* versus merely uses when present. This is worth a direct test in QEMU with extensions masked (e.g. `-cpu rva23s64,v=false`).
- I did not verify the exact OpenSBI version needed for full RVA23 support (Sstc, Ssnpm, Sscofpmf PMU SBI extension, Zicfiss SSE).

---

## 4. How existing generators expose and validate levers (tiering patterns)

### Takeaway
Generators use one of three styles:
1. Presets plus composable overrides: Rocket's `WithNBigCores` + `WithL1DCacheSets`, Chipyard's `GENV256D128ShuttleConfig`.
2. Flat named parameter packages: CVA6's `cv64a6_imafdch_sv39_config_pkg`.
3. CLI flags with dependency checks: VexiiRiscv `--with-*`, LiteX `--cpu-variant`.

Commercial tools such as SiFive Core Designer start from a fixed core "Series" template and expose only bounded options within it. Validation is mostly ad hoc in all of them: asserts in Chisel/SystemVerilog and "requires" notes in CLI help.

Proposed tiering for Ouroboros:
- **T1:** preset (Tiny/Linux-RV64GC/RVA23-min/RVA23-LLM), distro, VLEN/DLEN, L1 sizes, L2 yes/no, clock.
- **T2:** per-optional-extension toggles, FPU style, BP sizes, TLB, PMP and counters, boot flow, memory carve-out.
- **T3:** slow/fast per vector-op class, cache line and policy, PA width, debug and trace, M-mode emulation toggles.

### Cited Findings
- **Rocket/Chipyard.** Core presets (Huge/Big/Med/Small/Tiny) combined with fine-grained fragments: L1 I/D sets/ways/ECC/row bits, TLB sets/ways/superpages, nonblocking MSHRs, `WithoutFPU`, `WithFP16`, `WithoutVM`, `WithSV48`, `WithB`, `WithFastMulDiv`, `WithoutMulDiv`, CDC types — [rocket-chip Configs.scala](https://github.com/chipsalliance/rocket-chip/blob/master/src/main/scala/rocket/Configs.scala)
- **Saturn.** Configs are named by VLEN/DLEN and host core (`GENV256D128ShuttleConfig`, `REFV512D256RocketConfig`) in `SaturnConfigs.scala` — [Chipyard Saturn docs](https://chipyard.readthedocs.io/en/1.12.3/Generators/Saturn.html)
- **CVA6.** One SystemVerilog package per named config (e.g. `cv64a6_imafdch_sv39`) with flat `CVA6Config*` parameters: ISA toggles, caches, BP, PMP, perf counters, MMU, CV-X-IF — [CVA6 config pkg](https://github.com/openhwgroup/cva6/blob/master/core/include/cv64a6_imafdch_sv39_config_pkg.sv)
- **VexiiRiscv/LiteX.** Flat CLI flags with documented requirements (gshare/RAS "Require the BTB"), passed from LiteX through `--vexii-args` — [VexiiRiscv docs](https://spinalhdl.github.io/VexiiRiscv-RTD/master/VexiiRiscv/HowToUse/index.html)
- **NaxRiscv.** Plugin-composed toplevel, integrated into LiteX — [NaxRiscv GitHub](https://github.com/SpinalHDL/NaxRiscv)
- **Ara.** NrLanes/VLEN parameters, with a newly added explicit illegal-combination check (VLEN ≥ 64·NrLanes) — [Ara PR #484](https://github.com/pulp-platform/ara/pull/484)
- **SiFive Core Designer.** Template per Core Series (2/3/5/7, later others). Options include RV32E, F/D, SCIE custom instructions, optional L2, μI-cache/ITIM/DLS, up to 8 cores and Fast IO. Positioned as letting users "explore the architectural design space" from a browser — [SiFive blog](https://www.sifive.com/blog/sifive-core-designer-adds-three-new-core-series)
- **XiangShan.** Named Scala configs (`MinimalConfig` vs `DefaultConfig`) differing in ROB and L2/LLC sizes — [XiangShan tutorial](https://tutorial.xiangshan.cc/hpca26/hands_on/tutorial-en/)

### Inferences

**Validator design for Ouroboros**
- Encode the rules as data, mirroring the Linux DT `extensions.yaml` dependency schema:
  - extension → requires/excludes
  - profile → mandatory set
  - distro → minimum profile
  - generator rules (DLEN ≤ VLEN; RAS/gshare ⇒ BTB; H ⇒ S + Sv39; FPU off ⇒ no V, no Ubuntu)
- From one source of truth, emit four outputs:
  - the HLS `config.h`
  - the DT `riscv,isa-extensions` list
  - the OpenSBI and kernel defconfig fragments
  - the distro compatibility badge

  This mirrors how Linux, LLVM and the profile spec share extension names.

**Presets (T1)**
- **"Minimal Linux"**: RV64GC, Sv39, no V/H, small caches. Boots Ubuntu 24.04 and Debian.
- **"RVA23 minimum"**: all mandatory pieces, DLEN=32, iterative FPU div/sqrt, no L2. Boots Ubuntu 26.04 at the smallest area.
- **"RVA23 balanced"**: DLEN=64, FMA FPU, 16/16 KiB L1, BHT+BTB.
- **"RVA23 LLM"**: DLEN=128, Zvfh + Zvfbfwma + Zfh, L2 in URAM. Leaves the fewest resources for the systolic array.

**Resource-budget feedback**
- Each lever should report its LUT/DSP/BRAM/URAM delta against the XCK26 totals and the accelerator's reserved share. That way the "shares the FPGA" constraint is visible in the configurator, similar to SiFive Core Designer's PPA estimates [est — I could not verify that SCD shows PPA].

### Gaps
- I could not access the LiteX wiki's `--cpu-variant` list for VexRiscv (minimal/lite/standard/full/linux/linux+…) in this session.
- OpenHW CV-X-IF specification details (issue/commit/result interfaces) were not fetched.
- I found no public material on Andes or Codasip configurator UX.
