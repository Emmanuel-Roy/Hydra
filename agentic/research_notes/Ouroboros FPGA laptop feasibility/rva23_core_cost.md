# RVA23S64 single-hart core on Kria K26: scope, FPGA cost, and prior art

Target device (for reference): K26 SOM / XCK26-SFVC784-2LV: 117,120 CLB LUTs, 234,240 CLB FFs, 1,248 DSP slices, 144 BRAM36 (5.1 Mb), 64 URAM (288 Kb each), 3.5 Mb distributed RAM. Source: [Kria K26 SOM data sheet DS987](https://www.mouser.com/datasheet/2/903/ds987_k26_som-2329045.pdf) (as summarized by search). Zynq UltraScale+ fabric, -2LV speed grade.

Note on measured vs estimated: every figure below is labeled. "Measured" means a post-synthesis or post-implementation number from the cited source. "Estimate" means my reasoning, flagged in the Inferences sections.

## Q1. RVA23S64 mandatory extensions; mandatory vs optional; cheap vs expensive

### Takeaway
RVA23 was ratified 22 Oct 2024. RVA23S64 makes V, H (via Sha), Sv39, Sstc, Svnapot, Svpbmt, Svinval, Sscofpmf, Ssnpm/Supm, and a long tail of small Z* extensions mandatory. Zicfilp/Zicfiss (CFI), Sv48 and Sv57 are only optional. Most of the tail costs little more than decode or CSR work. V (which includes vector FP32/FP64), H with two-stage translation, and the scalar F/D FPU dominate the cost.

### Cited Findings
- RVA23 was ratified on October 22, 2024. Its headline components are the vector extension and the hypervisor extension. — [HPCwire / RISC-V Intl press release](https://www.hpcwire.com/off-the-wire/risc-v-announces-ratification-of-the-rva23-profile-standard/); [RISC-V blog](https://riscv.org/blog/risc-v-rva23-a-major-milestone/)
- **RVA23U64 mandatory:** RV64I base plus M, A, F, D, C, B (= Zba+Zbb+Zbs), Zicsr, Zicntr, Zihpm, Ziccif, Ziccrse, Ziccamoa, Zicclsm, Za64rs, Zihintpause, Zic64b, Zicbom, Zicbop, Zicboz, Zfhmin, Zkt, V, Zvfhmin, Zvbb, Zvkt, Zihintntl, Zicond, Zimop, Zcmop, Zcb, Zfa, Zawrs, Supm. — [riscv-profiles rva23-profile.adoc](https://github.com/riscv/riscv-profiles/blob/main/src/rva23-profile.adoc)
- **RVA23U64 optional:** localized Zvkng and Zvksg; development Zabha, Zacas, Ziccamoc, Zvbc, Zama16b; expansion Zfh, Zbc, **Zicfilp, Zicfiss**, Zvfh, Zfbfmin, Zvfbfmin, Zvfbfwma. — [riscv-profiles](https://github.com/riscv/riscv-profiles/blob/main/src/rva23-profile.adoc)
- **RVA23S64 mandatory:** all RVA23U64 mandatory plus Zifencei, Ss1p13, Svbare, **Sv39**, Svade, Ssccptr, Sstvecd, Sstvala, Sscounterenw, Svpbmt, Svinval, Svnapot, Sstc, Sscofpmf, Ssnpm, Ssu64xl, **Sha** (the augmented hypervisor extension, i.e. H plus related Sh* and Ss* items). — [riscv-profiles](https://github.com/riscv/riscv-profiles/blob/main/src/rva23-profile.adoc)
- **RVA23S64 optional (expansion):** **Sv48, Sv57**, Zkr, Svadu, Sdtrig, Ssstrict, Svvptc, Sspm. — [riscv-profiles](https://github.com/riscv/riscv-profiles/blob/main/src/rva23-profile.adoc)
- The riscv-profiles GitHub repo shows as archived (July 24, 2026). The ratified document is the reference. — [riscv-profiles](https://github.com/riscv/riscv-profiles/blob/main/src/rva23-profile.adoc)
- CVA6's H-extension work found that Sstc (supervisor timer compare) "has negligible impact on the area". — [Sá et al., CVA6 RISC-V Virtualization, arXiv 2302.02969](https://ar5iv.labs.arxiv.org/html/2302.02969)
- On CVA6, Bitmanip (Zba/Zbb/Zbc/Zbs) cost +4% LUTs on Kintex-7: 73,726 to 77,113 LUTs for the whole RV64 SoC. The ALU grew from 81 to 547 LUTs. **Measured.** — [Trovato et al., CF'23, Bitmanip on CVA6](https://10xengineers.ai/wp-content/uploads/Implementation-and-Performance-Evaluation-of-Bit-Manipulation_Extension-on-CVA6-RISC-V.pdf)

### Inferences
- Sv39 is the only mandatory paging mode. A minimal-cost design can implement Sv39 only (plus Sv39x4 G-stage for H) and skip Sv48/Sv57.
- The CFI extensions Zicfilp/Zicfiss are optional (expansion), so they can be omitted.
- **Cheap (decode, CSRs, or a few hundred LUTs each):**
  - Zimop/Zcmop: may-be-ops that execute as writes of zero.
  - Zihintpause, Zihintntl, Zicbop: hints, so they can be no-ops.
  - Zawrs: can be a NOP or stall.
  - Zicond: two muxes.
  - Zcb: extra compressed decode.
  - Zkt: a constant-time requirement that a simple in-order core gets largely for free if mul/div latency does not depend on data, or if Zkt-listed ops are constant-time.
  - Zic64b, Za64rs, Ziccif and similar: statements about cache-block and reservation-set properties.
  - Zicboz/Zicbom: cache-block zero and clean/flush operations in the D-cache controller.
  - Svinval: TLB flush split.
  - Svade, Ssccptr, Sstvecd, Sstvala, Sscounterenw, Ssu64xl: mostly CSR behavior.
  - Sstc: one 64-bit comparator per mode.
  - Sscofpmf: counter overflow interrupt plus mode filtering.
  - Svpbmt: two PTE bits that route to the memory-type path.
  - Svnapot: TLB match masking for 64 KiB NAPOT pages.
  - Supm/Ssnpm: pointer masking of high address bits on loads and stores.
- **Moderate:**
  - B extension: about 4% of a CVA6 SoC, measured above.
  - Zfa plus Zfhmin: extra FP instructions such as fli, fminm, fround and fleq, plus FP16 to FP32/FP64 conversions inside the existing FPU.
  - Zvbb/Zvkt: vector bit manipulation (vandn, vbrev, vclz, vctz, vcpop, vrol, vror, vwsll), which replicates bit-manip logic across the vector datapath.
- **Expensive:**
  - Full V (RVA23 requires the full "V" extension, which by spec implies ELEN=64 and vector FP32/FP64 arithmetic, i.e. Zve64d).
  - H/Sha: virtualized CSR set, two-stage Sv39 plus Sv39x4 translation, a larger PTW and TLB, and VS/VU modes.
  - Scalar F/D FPU with FMA, plus Zfhmin conversions.

### Gaps
- I did not fetch the ratified PDF itself, only the adoc source. The extension list above comes from that adoc.
- I found no per-extension FPGA LUT breakdown for the "cheap" RVA23 additions (Svnapot, Svpbmt, Ssnpm, Zawrs and so on). The "cheap" classification is an engineering inference.

## Q2. Ubuntu riscv64 ISA baseline and non-ISA platform requirements

### Takeaway
Ubuntu 24.04 LTS targets RVA20 (RV64GC). Starting with Ubuntu 25.10, released October 2025 and announced by Canonical in June 2025, the baseline is RVA23, and 26.04 LTS keeps RVA23 as its long-term baseline. So a core that only boots stock Ubuntu 24.04 needs RV64GC plus an Sv39 MMU. Stock 25.10/26.04 userspace needs the full RVA23 (V, H, B and the rest). Canonical's profile posts do not specify the platform pieces (SBI, interrupt controller, boot flow).

### Cited Findings
- Canonical announced in June 2025 that Ubuntu 25.10 would raise the riscv64 baseline from RVA20 to RVA23. — [Phoronix](https://www.phoronix.com/news/Ubuntu-25.10-To-Require-RVA23); [OMG! Ubuntu, June 2025](https://www.omgubuntu.co.uk/2025/06/ubuntu-riscv-rva23-support); [CNX Software, 2025-07-08](https://www.cnx-software.com/2025/07/08/ubuntu-25-10-release-to-mandate-rva23-profile-obsoleting-most-risc-v-hardware/)
- At release, Ubuntu 25.10 riscv64's only supported platform was QEMU virtualization, because almost no RVA23 hardware existed. — [Phoronix](https://www.phoronix.com/news/Ubuntu-25.10-RISC-V-QEMU)
- Canonical: "Starting with Ubuntu 25.10, RVA23 became the minimum supported baseline". It is delivering "Ubuntu 26.04 LTS with RVA23 as our unified, long-term supported baseline". "RVA20 users can still get up to 15 years of support, provided they are using Ubuntu 24.04 LTS with Ubuntu Pro." — [Ubuntu blog: 2025 retro / 2026 outlook](https://ubuntu.com/blog/canonical-and-ubuntu-risc-v-a-2025-retro-and-looking-forward-to-2026)
- Ubuntu 24.04 LTS requires the RVA20 profile (RV64GC). — [Ubuntu blog: RISC-V profiles, why RVA23 is significant](https://ubuntu.com/blog/risc-v-profiles-why-is-rva23-significant); [Ubuntu blog retro (search summary)](https://ubuntu.com/blog/canonical-and-ubuntu-risc-v-a-2025-retro-and-looking-forward-to-2026)
- Canonical acknowledges that profiles "guarantee a level of binary compatibility" but do not cover "initial boot, device discovery and peripheral drivers". It points to RISC-V International work such as the Server Platform Specification for "interrupt controllers and secure boot". — [Ubuntu blog: RISC-V profiles](https://ubuntu.com/blog/risc-v-profiles-why-is-rva23-significant)
- At Hot Chips 2026, Canonical said that "RVA23 is the standardized application baseline Canonical is targeting for 64-bit application processors". It expects server-class RVA23 hardware "from multiple vendors in 2026 and 2027", and its native build farm uses Alibaba and SpacemiT hardware at Scaleway. — [ServeTheHome, Hot Chips 2026](https://www.servethehome.com/canonical-evolution-of-enterprise-open-source-risc-v-at-hot-chips-2026/)
- Existing FPGA Debian flows use OpenSBI, U-Boot, the Linux kernel and a Debian root filesystem on an SD card. — [eugene-tarassov/vivado-risc-v](https://github.com/eugene-tarassov/vivado-risc-v)
- The CVA6 port to the Agilex 7 board needed "custom OpenSBI and U-Boot platforms", UART driver changes, and an MMC workaround. — [PlanV, Jan 2026](https://planv.tech/2026/01/17/linux-on-cva6-on-agilex7-development-kit/)

### Inferences
- Minimal platform for an Ubuntu boot on a custom soft SoC, based on standard RISC-V Linux practice (not taken from a Canonical document):
  - M-mode firmware (OpenSBI, implementing SBI TIME/IPI/RFENCE/HSM; with Sstc, timer interrupts no longer need to trap to M-mode).
  - CLINT/ACLINT (mtime/msip).
  - PLIC, or APLIC (wired interrupts). IMSIC is only needed for MSI-based PCIe or virtualization interrupts. A single hart with PLIC is enough for Linux.
  - A 16550-class UART.
  - A block device: SD/MMC, or virtio over a PS bridge.
  - A device tree passed by OpenSBI or U-Boot.
  - DRAM. On K26 this would come through the PS DDR controller via an HP/HPC AXI port.
- Ubuntu's generic riscv64 kernel and boot media target generic RVA23 platforms (QEMU virt today). A custom FPGA SoC would most likely need its own DT, U-Boot/OpenSBI platform and possibly kernel config, as PlanV needed for CVA6.
- A practical fallback is to boot Ubuntu 24.04 (RVA20) on an RV64GC+Sv39 core first, then grow toward RVA23 for 25.10/26.04 userspace. Whether 26.04 userspace traps on V or H instructions in practice (as opposed to official support) is a separate question; see Gaps.

### Gaps
- I could not fetch the original Canonical Discourse post. The June 2025 date comes from Phoronix, OMG! Ubuntu and CNX coverage. Phoronix returned 403 to direct fetch.
- I found no Canonical statement listing required platform devices (UEFI vs U-Boot, AIA vs PLIC, BRS compliance) for 26.04 riscv64.
- Unknown: which RVA23 extensions the 25.10/26.04 binaries actually emit (for example whether the toolchain default `-march` includes `v`, so glibc or other packages would fault without V). The profile requirement is official, but per-package evidence was not gathered.

## Q3. Measured FPGA resources of existing Linux-capable open cores and vector units

### Takeaway
Measured single-core RV64GC Linux-class cores cost about 23–30K LUTs for in-order Rocket and about 74K LUTs for a whole CVA6 RV64GC SoC on Kintex-7. Superscalar OoO cores (BOOM 2–3 wide) cost 150–250K LUTs and do not fit a K26. XiangShan does not fit any ZCU10x-class part. Vector-unit FPGA data is sparse and unreliable: Ara has only been put on VCU118/VCU128 (about 1.3M-LUT parts), and only with 2 lanes.

### Cited Findings
**Rocket (in-order 5-stage, RV64GC)**
- vivado-risc-v (Debian on FPGA): 64-bit Rocket costs "10,800 + 27,500 per core" LUTs. 32-bit costs "10,800 + 6,100 per core". **Measured**, Xilinx 7-series boards (VC707, KC705, Genesys 2, Nexys Video, Arty A7-100T). Clock is up to 100 MHz on VC707 and up to 50 MHz on Nexys Video. It runs a Debian root FS with about 90% of Debian packages available. — [eugene-tarassov/vivado-risc-v](https://github.com/eugene-tarassov/vivado-risc-v)
- Rocket with H extension (v0.6.1 draft) on **Zynq UltraScale+ ZCU104** (**measured**):
  - 2-core: 50,922 LUTs (+11%) and 25,086 registers (+30%).
  - 4-core: 101,744 LUTs (+12%).
  - 6-core: 152,957 LUTs (+12%).
  - The authors attribute the cost mainly to CSR and TLB expansion: "an extra 11% LUTs, and 27-29% registers".
  - Source: [Sá, Martins, Pinto, "A First Look at RISC-V Virtualization from an Embedded Systems Perspective", arXiv 2103.14951](https://ar5iv.labs.arxiv.org/html/2103.14951)

**BOOM (OoO)**
- Medium BOOM (2-wide) uses 148,500 LUTs and Large BOOM (3-wide) uses 252,700 LUTs. **Measured** (Xilinx 7-series flow). — [vivado-risc-v](https://github.com/eugene-tarassov/vivado-risc-v)

**CVA6 (Ariane; 6-stage in-order, RV64GC, Sv39)**
- Whole Genesys 2 (Kintex-7) SoC with cv64a6_imafdc_sv39, Vivado 2018.1, **measured**:
  - 73,726 LUTs total; the scoreboard alone is 5,874 LUTs.
  - With Bitmanip: 77,113 LUTs.
  - RV32IMAFC: 54,629 LUTs.
  - Linux booted on the same board.
  - Source: [Trovato et al., CF'23](https://10xengineers.ai/wp-content/uploads/Implementation-and-Performance-Evaluation-of-Bit-Manipulation_Extension-on-CVA6-RISC-V.pdf)
- The same paper reports ASIC gate counts (TSMC 65nm): RV64IMAFDC 515 kGE vs RV32IMAFC 186 kGE. — [Trovato et al.](https://10xengineers.ai/wp-content/uploads/Implementation-and-Performance-Evaluation-of-Bit-Manipulation_Extension-on-CVA6-RISC-V.pdf)
- A third-party openXC7 report (weak source) says Vivado puts CVA6 at roughly 40–50K LUT6. On the same Genesys 2 build it reports 24,218 FFs, 71 DSP48E1 and 36 RAMB36E1 for cv64a6_imafdc_sv39; Yosys mapped the design to an inflated 628K LUTs. — [randomizedcoder/rtl-fun PR #77](https://github.com/randomizedcoder/rtl-fun/pull/77)
- CVA6 with H extension v1.0 plus Sstc ran on Genesys 2 at 100 MHz. The authors collected FPGA utilization but omitted it "due to lack of space". In 22nm FDX the chosen configuration (h-16-gtlb-8) cost 0.78% area and 0.33% power; L2 TLB options added up to 8% area. — [Sá et al., arXiv 2302.02969](https://ar5iv.labs.arxiv.org/html/2302.02969)
- CVA6 demonstrated Buildroot and Yocto Linux. — [CVA6 docs](https://docs.openhwgroup.org/projects/cva6-user-manual/01_cva6_user/Introduction.html); [Zephyr CV64A6 Genesys 2 page](https://docs.zephyrproject.org/latest/boards/openhwgroup/cv64a6_genesys_2/doc/index.html)
- A Linux port to Agilex 7 (2026) uses a 100 MHz main clock; the article gives no resource counts. — [PlanV](https://planv.tech/2026/01/17/linux-on-cva6-on-agilex7-development-kit/)
- A community fork claims "RVA23 compliant MMU extensions" for CVA6. No details or results are published. — [samarthyx/cva6](https://github.com/samarthyx/cva6)

**NaxRiscv / VexRiscv / VexiiRiscv (SpinalHDL)**
- NaxRiscv is an OoO core, RV32/RV64 IMAFDCSU, Sv32/Sv39. "13.3 KLUT on Artix 7-3" for a high-performance config (2.93 DMIPS/MHz, 5.02 CoreMark/MHz), with 155 MHz mentioned. Linux/Buildroot works on hardware. **Measured; the exact config (RV32 vs RV64, FPU present or not) is unclear.** — [NaxRiscv README](https://github.com/SpinalHDL/NaxRiscv)
- VexRiscv is RV32 only, so it cannot run riscv64 Ubuntu. "Linux balanced" uses 2,883 LUT and 2,130 FF at 180 MHz on Artix-7. "Full with MMU" uses 2,021 LUT and 1,541 FF at 151 MHz. **Measured.** — [VexRiscv README](https://github.com/SpinalHDL/VexRiscv)
- VexiiRiscv is RV32/64 IMAFDCSU with Sv32/Sv39 and CBM. It "can run linux/buildroot/debian on FPGA hardware (via litex)". H and V are not listed. — [VexiiRiscv docs](https://spinalhdl.github.io/VexiiRiscv-RTD/master/VexiiRiscv/Introduction/index.html)
- Efinix's Sapphire RV64 SoC is built on VexiiRiscv. On Titanium, a single core with 64 KB L2 uses 14,258 logic/adders, 12,624 FFs, 188 memory blocks and 17 DSPs, and reaches 170 MHz. The L1-only config uses 10,740 logic and 9,024 FFs. **Measured, but Efinix XLR logic cells are not Xilinx LUT6s.** — [Efinix Sapphire RV64](https://www.efinixinc.com/support/ip/riscv-sapphire-rv64.php)

**XiangShan**
- Kunminghu V2 is "based on the RVA23 profile and server SOC spec" and supports RVV 1.0 with "VLEN 128bit x 2". — [XiangShan user guide](https://docs.xiangshan.cc/projects/user-guide/en/kunminghu-v3/introduction/)
- Kunminghu V2 is described as implementing the RVA23 profile with hardware virtualization at 45 SPECint06 at 3 GHz. — [RISC-V Summit Europe 2025 abstract](https://riscv-europe.org/summit/2025/media/proceedings/2025-05-13-RISC-V-Summit-Europe-P2.1.06-TANG-abstract.pdf)
- A GitHub issue reports that Zvbc is unimplemented on kunminghu-v2 despite its "stable rva23" positioning. Zvbc is optional in RVA23, so this does not by itself break compliance. — [XiangShan issue #6601](https://github.com/OpenXiangShan/XiangShan/issues/6601)
- BOSC prototypes XiangShan on S2C Prodigy VU19P systems. — [RISC-V Intl blog](https://riscv.org/blog/s2cs-fpga-prototyping-accelerates-iterations-of-xiangshan-risc-v-processor/)
- A XiangShan maintainer said neither Nanhu nor Kunminghu, "in their default or minimal configs", fits ZCU104, ZCU106, PYNQ-ZU or Alveo boards. A tailored default config could fit a VU19P. A smaller "nanhu-G" branch exists for smaller FPGAs. — [xiangshan-all mailing list](https://www.mail-archive.com/xiangshan-all@ict.ac.cn/msg00085.html)

**T-Head OpenC906 / OpenC910**
- C906 is RV64GC with optional RVV **0.7.1** (VLEN 128). — [CNX Software](https://www.cnx-software.com/2021/10/20/alibaba-open-source-risc-v-cores-xuantie-e902-e906-c906-and-c910/)
- An OpenC906 FPGA port exists for Kintex-7 xc7k325t, bare-metal with UART. No LUT numbers are given. — [Irisaka/OpenC906_FPGA](https://github.com/Irisaka/OpenC906_FPGA)

**Vector units**
- **Ara/AraOS** (RVV 1.0 coprocessor to CVA6, in the Cheshire SoC):
  - The FPGA flow targets only VCU128/VCU118, "bare-metal and with Linux", and "the tested configuration is with 2 lanes". — [pulp-platform/ara](https://github.com/pulp-platform/ara)
  - The AraOS paper says: "Adding Ara2 (1.33 M LUTs) to the Cheshire SoC (1.02 M LUTs) incurs a 2.3× footprint". That is for 2 lanes, VLEN=2048, on VCU128 at 50 MHz. MMU/OS support cost 45 kGE (+2.4%) in 22nm. — [AraOS, arXiv 2504.10345](https://arxiv.org/html/2504.10345)
  - **Caution: these "M LUT" figures cannot be literal Vivado LUTs.** The combined design would exceed the VCU128's roughly 1.3M LUTs. The figures may come from an open-source flow with inflated mapping (compare the Yosys 12x inflation for CVA6 above) or be a unit error. Treat them as unreliable.
- New Ara (RVV 1.0) in 4-lane ASIC: the VMFPU together with the VRF and operand queues "accounts for almost 90%" of a lane's energy budget. VU1.0 cell area is 0.49 mm² (GF22). — [arXiv 2210.08882](https://arxiv.org/html/2210.08882v2)
- **Vicuna** (32-bit, integer and fixed-point only, RVV 0.10 draft):
  - Configurations on Xilinx 7-series: small (VLEN 128, 32-bit multiplier datapath, 100 MHz); medium (VLEN 512, 128-bit, 90 MHz); fast (VLEN 2048, 1024-bit, 80 MHz).
  - Exact LUT counts appear only in a radar chart. The fast config is below about 90K LUTs, and the authors call it "similar" to VESPA/VEGAS.
  - There is no FP and no 64-bit support, so it does not meet RVA23 V.
  - Source: [Platzer & Puschner, ECRTS 2021](https://drops.dagstuhl.de/storage/00lipics/lipics-vol196-ecrts2021/LIPIcs.ECRTS.2021.1/LIPIcs.ECRTS.2021.1.pdf)
- **Arrow** (RVV 0.9 integer subset, dual-lane, beside a MicroBlaze on an XC7A200T at 100 MHz, Fmax 112 MHz):
  - MicroBlaze alone uses 2,241 LUTs. MicroBlaze plus Arrow uses 2,715 LUTs and 2,268 FFs, so Arrow adds roughly 0.5K LUTs. **Measured.**
  - This is suspiciously small, and the design covers only an integer subset, so it is not comparable to full V.
  - Source: [Al Assir et al., CARRV 2021](https://arxiv.org/pdf/2107.07169)
- **Saturn** (UCB, RVV 1.0, Chisel) is parameterized by VLEN/DLEN/MLEN. The only FPGA use found is EARTH on an Intel Stratix 10 GX 10M (VLEN 256/DLEN 128 with a Shuttle core at 20 MHz). It reports no FPGA resource counts; area is from a 3nm-class ASIC flow. — [EARTH, arXiv 2504.08334](https://arxiv.org/html/2504.08334)
- **Spatz** is a compact RVV-subset unit paired with an RV32 Snitch core (ASIC GF12). It has no MMU or Linux path. — [Spatz, arXiv 2207.07970](https://arxiv.org/pdf/2207.07970)

### Inferences
- **Fits on K26 (117K LUTs):** Rocket single core with FPU (about 27.5K + 10.8K uncore, measured on 7-series), CVA6 SoC (about 74K whole SoC, measured on Kintex-7; the core is probably 40–50K), VexiiRiscv/NaxRiscv class.
- **Does not fit:** BOOM medium/large, XiangShan (any config), Ara at its published FPGA configuration.
- Rocket's per-core LUT count on ZCU104 with H is about 25K per core (50,922 / 2 cores, including uncore share). That matches vivado-risc-v's 27.5K per core on 7-series, so a single in-order RV64GC+H core is about 25–30K LUTs on UltraScale+. **Measured basis, simple derivation.**
- No open core with published FPGA utilization implements RV64 + full RVV 1.0 (with FP) + H in a single small FPGA. This is a genuine gap in prior art.

### Gaps
- I could not retrieve the utilization tables (LUT/FF/BRAM/DSP/Fmax on Virtex UltraScale+) from Dörflinger et al., CF'21, which compares Rocket, BOOM, CVA6 and SHAKTI C-Class. The TU Braunschweig PDF is behind a bot check and ACM returns 403. It is likely the best single comparative source. — [TU-BS copy](https://leopard.tu-braunschweig.de/servlets/MCRFileNodeServlet/dbbs_derivate_00048198/riscv-survey-cf-zweitpublikation.pdf), [ACM DOI 10.1145/3457388.3458657](https://dl.acm.org/doi/pdf/10.1145/3457388.3458657)
- No numeric FPGA utilization found for: OpenC910 (FPGA), T-Head C908/C920 (closed IP), Saturn (any FPGA), Ara at VLEN=128 or 1 lane, CVA6+H (omitted by its authors), or a CV-X-IF vector coprocessor.
- No LUT/FF/DSP split for an RVV 1.0 vector unit with FP64 at VLEN=128 on any Xilinx part.

## Q4. Open or academic cores claiming RVA23 compliance (2024–2026), and their size

### Takeaway
The only open-source core found that claims RVA23 is XiangShan Kunminghu (V2/V3). It is a large OoO server-class core that fits only VU19P-class FPGAs. Commercial RVA23 cores (SpacemiT X100/K3 and others) are not open. CVA6 and Rocket have pieces (H, Sstc, B, RVV via Ara) but no published full-RVA23 configuration.

### Cited Findings
- XiangShan Kunminghu V2 is "based on the RVA23 profile" with RVV 1.0 (VLEN 128 x 2) and hardware virtualization. It is too big for ZCU104/ZCU106-class boards; VU19P is suggested. — [XiangShan docs](https://docs.xiangshan.cc/projects/user-guide/en/kunminghu-v3/introduction/); [RISC-V Summit EU 2025](https://riscv-europe.org/summit/2025/media/proceedings/2025-05-13-RISC-V-Summit-Europe-P2.1.06-TANG-abstract.pdf); [mailing list](https://www.mail-archive.com/xiangshan-all@ict.ac.cn/msg00085.html)
- XiangShan's RVA23 claim has a reported hole: Zvbc is missing. Zvbc is optional ("development") in RVA23, so this is not a compliance break. — [issue #6601](https://github.com/OpenXiangShan/XiangShan/issues/6601); [riscv-profiles](https://github.com/riscv/riscv-profiles/blob/main/src/rva23-profile.adoc)
- SpacemiT K3 (announced July 2025) uses RVA23-compliant X100 cores; it is commercial. — [Wikipedia: SpacemiT](https://en.wikipedia.org/wiki/SpacemiT); [SpacemiT K3 doc](https://forum.spacemit.com/uploads/short-url/60aJ8cYNmrFWqHn4ddwwSzMLjlY.pdf)
- CVA6 has H v1.0 plus Sstc (academic). — [arXiv 2302.02969](https://ar5iv.labs.arxiv.org/html/2302.02969)
- CVA6 has Bitmanip. — [CF'23](https://10xengineers.ai/wp-content/uploads/Implementation-and-Performance-Evaluation-of-Bit-Manipulation_Extension-on-CVA6-RISC-V.pdf)
- RVV 1.0 is available for CVA6 via Ara/AraOS, with MMU support. — [AraOS](https://arxiv.org/html/2504.10345)
- A community CVA6 fork targets "RVA23 compliant MMU extensions". — [samarthyx/cva6](https://github.com/samarthyx/cva6)

### Inferences
- CVA6 plus Ara plus the H patches is the closest open "kit" to RVA23. Those features live in different branches and papers, and nobody has published them combined on a single FPGA or certified them against RVA23.
- A from-scratch simple-pipeline RVA23 core would be novel among small FPGA cores.

### Gaps
- I found no RISC-V International RVA23 compliance or certification list, and no ACT (architecture compatibility test) results for any open core.
- I did not check whether Rocket-chip mainline or Chipyard ships an "RVA23" config (Rocket has H; Saturn provides V) as of 2026.

## Q5. Estimated LUT budget for a simple-pipeline single-hart RVA23S64 core, and fit on K26

### Takeaway
Estimate: about 60–100K LUTs for a single-hart, in-order RVA23S64 core with VLEN=128 and a 64-bit vector datapath, including caches, FPU, H, V and a minimal SoC uncore. The midpoint is about 75–80K, which is 65–70% of the K26's 117K LUTs. That leaves roughly 20–50K LUTs for an LLM accelerator. The fit is plausible but tight. **V (especially vector FP64) and the scalar FPU dominate. H is roughly +10–15% of the scalar core.** DSPs (1,248) and BRAM/URAM are not the binding constraint; LUTs are.

### Cited Findings (anchors used for the estimate)
- Rocket RV64GC in-order: about 27.5K LUTs per core plus 10.8K shared on 7-series, **measured**. — [vivado-risc-v](https://github.com/eugene-tarassov/vivado-risc-v)
- Rocket+H on UltraScale+ ZCU104: about 25K LUTs per core including uncore share; H costs +11–12% LUTs and +27–30% FFs, **measured**. — [arXiv 2103.14951](https://ar5iv.labs.arxiv.org/html/2103.14951)
- CVA6 RV64GC SoC on Kintex-7: 73.7K LUTs, **measured**. — [CF'23](https://10xengineers.ai/wp-content/uploads/Implementation-and-Performance-Evaluation-of-Bit-Manipulation_Extension-on-CVA6-RISC-V.pdf)
- CVA6 RV64GC vs RV32IMAFC: 515 vs 186 kGE (ASIC). Going 64-bit with D roughly 2.8x'es the gate count. — [CF'23](https://10xengineers.ai/wp-content/uploads/Implementation-and-Performance-Evaluation-of-Bit-Manipulation_Extension-on-CVA6-RISC-V.pdf)
- Bitmanip: +4% LUTs on CVA6. — [CF'23](https://10xengineers.ai/wp-content/uploads/Implementation-and-Performance-Evaluation-of-Bit-Manipulation_Extension-on-CVA6-RISC-V.pdf)
- In Ara lanes, the FPU plus VRF plus operand queues account for about 90% of lane energy, which indicates the FPU dominates the lane. — [arXiv 2210.08882](https://arxiv.org/html/2210.08882v2)
- VexRiscv RV32 Linux core is about 2–3K LUTs on Artix-7; the RV32 integer pipeline with MMU is very small. — [VexRiscv](https://github.com/SpinalHDL/VexRiscv)

### Inferences (all ESTIMATES, UltraScale+ LUT6, Vivado)
| Block | Estimate (LUTs) | Reasoning |
|---|---|---|
| Scalar RV64IMAC in-order pipeline + B + Zicond/Zcb/Zfa decode, CSRs, PMP (8–16 entries) | 8–15K | VexRiscv RV32 MMU core is about 2–3K; 64-bit roughly doubles to triples datapath and CSR width. Rocket and CVA6 integer pipelines including their L1 controllers fit within their 25–45K totals together with the FPU. PMP costs about 150–300 LUTs per entry (comparators). |
| MMU: Sv39 PTW + ITLB/DTLB (16–32 entries) + Svnapot/Svpbmt/Svinval | 3–6K | TLB CAMs in LUTs dominate. Sv48/Sv57 are optional and should be skipped. |
| L1 I$/D$ controllers (data in BRAM), AXI to PS DDR, Zicbom/z | 3–6K | Data arrays go to BRAM36/URAM; the LUT cost is control and muxing. |
| Scalar F/D FPU (FMA, div/sqrt, conversions incl. Zfhmin) | 8–15K LUTs + about 10–30 DSPs | A DP FMA uses about 10–20 DSP48E2s plus normalization logic; div/sqrt are iterative. Not directly sourced; based on CVA6 using 71 DSPs SoC-wide. |
| H extension (Sha): VS CSRs, two-stage Sv39/Sv39x4 PTW, GTLB | +3–6K LUTs, +30% FFs | Rocket measured +11–12% LUT and +30% FF ([2103.14951](https://ar5iv.labs.arxiv.org/html/2103.14951)); CVA6 ASIC +0.78% area for a minimal config, up to +8% with an L2 TLB ([2302.02969](https://ar5iv.labs.arxiv.org/html/2302.02969)). |
| V, VLEN=128, 32-bit datapath | 12–20K | VRF of 32x128b = 4 Kb, LUTRAM-friendly (multi-port via replication or banking). Integer ALU, mul via DSPs, permute/slide/gather, mask unit, segmented/strided LSU with MMU interaction, vsetvl. Vector FP32/FP64 support is required (Zve64d inside V) and can be folded onto a narrow shared FMA. Zvbb/Zvkt add about 1–2K. |
| V, 64-bit datapath | 18–30K | About 1.5x the 32-bit version. FP64 FMA in vector lanes, possibly shared with the scalar FPU. |
| V, 128-bit datapath | 30–50K | The full-width VRF port and permute crossbar grow superlinearly (crossbar is about N²). |
| Uncore: CLINT/ACLINT, PLIC, UART, debug, AXI interconnect to PS | 3–8K | DDR comes from the Zynq PS, so no MIG is needed in fabric. That saves the large MIG LUT cost that 7-series boards (Genesys 2, VC707) pay. |

- **Totals:**
  - With a 32-bit vector datapath: about 40–75K.
  - With 64-bit: about 46–85K.
  - With 128-bit: about 58–105K.
  - Typical expectation: about 65–80K for the 64-bit configuration, or 55–70% of 117K. That leaves about 35–50K LUTs plus most of the 1,248 DSPs and the URAM for an LLM accelerator.
- **Cost ranking:** (1) V unit, especially its LSU/permute and FP; (2) scalar FPU; (3) integer pipeline, MMU, caches and CSRs; (4) H; (5) everything else in RVA23 (B, Zfa, Zicond, Zcb, Svnapot, Svpbmt, Sstc, Sscofpmf, pointer masking, CBO), likely under 5K total.
- **Cost-saving levers:**
  - Share one FMA between scalar F/D and vector FP, with vector FP done at 64 bits per cycle or slower. RVA23 mandates functional V, not throughput.
  - Use a VLEN=128 VRF in LUTRAM or BRAM.
  - Implement only Sv39 (plus Sv39x4).
  - Use small TLBs with a shared PTW for both stages.
  - Implement rarely used ops (vrgather, segment loads, vector div/sqrt, FP64 vector reductions) as slow multi-cycle sequencers. Trap-and-emulate is not allowed for a compliant V, but a slow implementation is.
- Using the PS's DDR controller instead of a fabric MIG is a major saving relative to the published 7-series SoC totals. CVA6's 73.7K on Genesys 2 includes MIG and peripherals.
- **Risks to the estimate:** UltraScale+ routing congestion at 70%+ utilization, and FF pressure from H (+30%), though FFs are plentiful at 234K.

### Gaps
- No primary source gives a measured LUT cost for an RVV 1.0 unit with FP64 at VLEN=128 on UltraScale+. The V estimate is the least certain line, possibly off by about 2x.
- No measured LUT figure for a standalone RV64 DP FPU on UltraScale+ (for example CVA6's FPnew alone) was retrieved.
- Without the Dörflinger CF'21 tables, I have no per-core UltraScale+ comparison for CVA6 vs Rocket.

## Q6. Typical Fmax on UltraScale+ and Linux boot times

### Takeaway
Linux-capable RV64 soft cores in the published flows run at 50–100 MHz on Xilinx parts. Lighter SpinalHDL cores reach 150–180 MHz (RV32, Artix-7), and Efinix's VexiiRiscv RV64 reaches 170 MHz. On a K26 (-2LV UltraScale+), a simple RV64 in-order core with V and H could plausibly close at about 100–150 MHz (estimate). I found no measured "minutes to Ubuntu shell" figure for any soft core.

### Cited Findings
- Rocket/BOOM Debian flow: up to 100 MHz on VC707 and 50 MHz on Nexys Video (7-series). — [vivado-risc-v](https://github.com/eugene-tarassov/vivado-risc-v)
- CVA6 with H on Genesys 2 runs at 100 MHz. — [arXiv 2302.02969](https://ar5iv.labs.arxiv.org/html/2302.02969)
- CVA6 on Agilex 7 has a 100 MHz main clock. — [PlanV](https://planv.tech/2026/01/17/linux-on-cva6-on-agilex7-development-kit/)
- CV32A6 target is above 150 MHz on Kintex-7 (cv32a6_imac_sv32). — [CVA6 requirements spec](https://docs.openhwgroup.org/projects/cva6-user-manual/02_cva6_requirements/cva6_requirements_specification.html)
- AraOS/Cheshire runs at 50 MHz on VCU128. — [AraOS](https://arxiv.org/html/2504.10345)
- NaxRiscv reaches about 155 MHz (Artix-7). — [NaxRiscv](https://github.com/SpinalHDL/NaxRiscv)
- VexRiscv Linux balanced reaches 180 MHz (Artix-7). — [VexRiscv](https://github.com/SpinalHDL/VexRiscv)
- Efinix Sapphire RV64 (VexiiRiscv) reaches 170 MHz on Titanium. — [Efinix](https://www.efinixinc.com/support/ip/riscv-sapphire-rv64.php)
- Vicuna runs at 80–100 MHz on 7-series; larger VLEN lowers Fmax because of VRF port latency. — [ECRTS 2021](https://drops.dagstuhl.de/storage/00lipics/lipics-vol196-ecrts2021/LIPIcs.ECRTS.2021.1/LIPIcs.ECRTS.2021.1.pdf)
- A search summary claimed "VexRiscv runs at 100 MHz and boots Linux in about 4 seconds". That is an RV32 Buildroot boot, not Ubuntu, and I could not verify the primary source. — (unverified; candidates: [Antmicro LiteX/VexRiscv SMP blog](https://antmicro.com/blog/2020/05/multicore-vex-in-litex))

### Inferences
- UltraScale+ -2 parts are generally about 1.3–1.6x faster than Artix-7 for the same RTL (general experience, not sourced). Rocket/CVA6-class designs at 50–100 MHz on 7-series suggest about 100–150 MHz on K26. The vector permute crossbar and FP64 FMA paths are the likely critical paths.
- Boot time (rough estimate): an in-order soft core at 100 MHz delivers roughly 100–200 DMIPS. Debian/Ubuntu systemd boots on such cores are commonly anecdotally several minutes to a login prompt, dominated by systemd unit startup and SD I/O. A full Ubuntu server image would be minutes, not seconds. Use a minimal image, disable services, or use an initramfs for faster bring-up.

### Gaps
- No measured Fmax for CVA6, Rocket or a vector unit specifically on Zynq UltraScale+ (ZCU104/ZCU102/K26) was found. The Rocket-H ZCU104 paper gives LUT counts but I did not extract its clock.
- No published measured boot time (to shell) for Debian or Ubuntu on Rocket, CVA6 or VexiiRiscv FPGA builds was found.
