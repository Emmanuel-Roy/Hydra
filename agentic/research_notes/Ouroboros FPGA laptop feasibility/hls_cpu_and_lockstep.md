# Building a pipelined RISC-V CPU in Vitis HLS and verifying it in lock-step against a C++ ISS

Research date: 2026-09-30. Each finding is marked as **[Demonstrated]** (measured or shipped result), **[Claim]** (an author's statement or opinion), or **[Doc]** (tool or project documentation). Primary sources only, where they could be reached.

## Q1. Prior work: processors designed in HLS, and how they compare with RTL

### Takeaway
Several published in-order RV32 cores were built with HLS: Comet (Catapult), HL5 (Stratus/SystemC) and Goossens' book cores (Vivado/Vitis HLS). In-order RV32 cores reach area and frequency close to RTL equivalents, but their FPGA Fmax is low: about 70-80 MHz on Artix-7, against 110-140 MHz for a hand-written small RTL core. I found no RV64, Linux-capable (MMU, S-mode) core built in HLS. Every Linux-capable soft core I found is RTL.

### Cited Findings
- **Comet (Inria/IRISA, ICCAD 2019).** A 5-stage pipelined RV32I/IM/IMF core written in C++ and synthesized with Catapult HLS v10.3a. The same C++ source also serves as a cycle-accurate and bit-accurate simulator — [Rokicki et al., "Designing a Processor Core from C++ Specifications", ICCAD'19](https://people.rennes.inria.fr/Olivier.Sentieys/publications/2019/Rokicki19ICCAD.pdf); repository at [gitlab.inria.fr/dpala/Comet](https://gitlab.inria.fr/dpala/Comet)
  - [Demonstrated] ASIC results (28 nm FDSOI, 700 MHz target): Comet rv32i 8,168 µm², rv32im 11,099 µm², rv32imf 26,760 µm². Rocket (Chisel) was 11,114, 12,606 and 26,550 µm²; PicoRV32 (Verilog) was 7,747 (rv32i) and 11,176 (rv32im) — same source
  - [Demonstrated] FPGA results (Artix-7 XC7A12T, Vivado 2018.3):
    - Comet rv32i: 80 MHz, 2,032 LUT, 1,503 FF
    - Comet rv32im: 70 MHz, 2,910 LUT, 3 DSP
    - Comet rv32imf: 74 MHz, 6,460 LUT
    - Rocket: 76 MHz, 2,253 LUT (rv32i)
    - PicoRV32: 140 MHz, 880 LUT (rv32i); 110 MHz (rv32im)
    - The authors write that "the manually optimized FPGA design of PicoRV is much more efficient than both Rocket and Comet" — same source
  - [Demonstrated] Dhrystone CPI is 1.9 for Comet and 4.1 for the best PicoRV32 configuration. Comet and Rocket have similar CPI — same source
  - [Demonstrated] Signs of HLS tool limits:
    - Synthesizing the FPU and the core separately gave a smaller total than synthesizing them together (8,147 + 15,299 µm² vs 26,760 µm²).
    - HLS runtime was 23 min for core+FPU, against about 2 min each when synthesized separately.
    - The authors read this as "reaching the limits of what current HLS tools can perform" as control flow grows — same source
  - [Demonstrated] The C++ model runs as a simulator at 23.6 M cycles/s (rv32i, no caches) down to 11.6 Mcps (rv32imf), on an i7 at 3.9 GHz — same source
- **HL5 (Columbia, CICC 2020).** An in-order RV32IM pipeline written in SystemC and synthesized with Cadence Stratus HLS 17.2 — [Mantovani et al., HL5, CICC'20](http://www.cs.columbia.edu/~luca/research/mantovani_CICC20.pdf); [github.com/sld-columbia/hl5](https://github.com/sld-columbia/hl5)
  - [Demonstrated] 12 RTL variants were generated from HLS knobs, with clock targets from 700 MHz to 2 GHz in 32 nm CMOS. They were compared with PULP zero-riscy: CPI was about 1.6-1.8 at about 12k-20k µm². The HL5 source is about 2k lines of SystemC, against more than 6k lines of RTL for zero-riscy — same source
  - [Demonstrated] Architecture: separate SC_CTHREAD stages (fedec, execute, memwb) connected by latency-insensitive point-to-point channels. Memory and write-back were merged into one "memwb" stage to avoid scheduling problems — same source
  - [Claim] "Conditionally-blocking" channels are the best choice for a pipeline across processes. Non-blocking channels are needed for parts that can execute out of order, to avoid deadlock. The naive ISS-style specification "cannot be synthesized with good quality-of-results", but small code changes get around this. The design took one person about two months — same source
- **Goossens (Univ. Perpignan): Springer book "Guide to Computer Processor Architecture: A RISC-V Approach, with High-Level Synthesis" (2023).**
  - [Doc] The book builds a progression of designs: fetching IP, non-pipelined RV32I, pipelined (branch delay/cancellation, bypassing, load delay, multicycle operators), a multicycle pipeline, a 6-stage multihart pipeline (up to 8 harts) and a multicore. The designs are tested on Pynq-Z1/Z2 boards — [Springer book page](https://link.springer.com/book/10.1007/978-3-031-18023-1); [multihart chapter](https://link.springer.com/chapter/10.1007/978-3-031-18023-1_10)
  - [Doc] The IP projects are available in folders for Vitis HLS 2022.1 (the book version), 2024.1 and 2025.1. The repo says "2023.1 and 2023.2 versions are not recommended" — [goossens-book-ip-projects](https://github.com/goossens-springer/goossens-book-ip-projects)
- **Goossens & Parello, out-of-order RV32IM core in Vivado HLS (RISC-V Week, Paris, 2019).**
  - [Demonstrated]
    - Design: 4 concurrent stages, no cache, flat memory, no branch predictor. Fetch blocks on conditional/indirect branches.
    - Effort: written in 2 weeks by one person, under 4,000 lines of C.
    - FPGA result: ZCU106 at 100 MHz, 9,146 LUT and 11,215 FF.
    - ASIC estimate (Catapult, 28 nm at 700 MHz): 50,300 µm².
  - [Claim] The design techniques used were: multiple ports on BRAM variables, full unrolling of tables, and "elimination of dependencies (e.g. PC write in execute stage and read in fetch stage)". The authors conclude that "HLS is now adult and can be used in replacement of VHDL/Verilog, at least for prototypes" — [slides](https://open-src-soc.org/2019-10/media/slides/2nd-RISC-V-Meeting-2019-10-02-10h15-Bernard-Goossens.pdf)
- **Negative report (Vivado HLS, out-of-order CPU, student project).** [Claim/experience] "The lack of clocking mechanisms in Vivado HLS was not sufficient to describe the concurrent out of order model of our intended CPU." HLS pipelining did not handle a control-heavy OoO design as hoped — [Hanselman, RISC-V CPU in HLS](https://www.hanselmandrew.com/projects/risc-v-cpu-in-hls)
- **Linux-capable small cores are RTL.** [Demonstrated] An RV64IMAFDC SystemVerilog core boots OpenSBI v1.2 and Linux 6.12 to userspace on a Zybo Z7-20 (Zynq-7020) at 25 MHz over AXI4. Verification: riscv-tests, RISCOF against Spike, and Verilator, which it reports as about 100x faster than iverilog — [y0sshi/RISC-V](https://github.com/y0sshi/RISC-V)
- Other HLS cores exist but report few metrics: a multi-cycle core for a custom HLS compiler ([can-lehmann/riscv_hls](https://github.com/can-lehmann/riscv_hls)).

### Inferences
- For a single-hart RV32 in-order pipeline, HLS reaches roughly Rocket-class area and frequency. On a 7-series device, plan for an Fmax of about 70-100 MHz rather than the 150+ MHz of tuned RTL.
- An RVA23S64 core is far larger than anything demonstrated in HLS. It needs RV64GC, Sv39/48/57 MMU, S/U modes, H extension, V and many Z-extensions. Comet's FPU result (HLS QoR got worse as control flow grew, and synthesis time went up about 10x) suggests the design will need to be split into separately synthesized blocks.
- No published HLS core handles the RVA23 privileged architecture (MMU page walks, precise traps across many CSRs, interrupts). This would be new ground.

### Gaps
- I found no RV64 or Linux-booting core built with Vitis/Vivado HLS, and no HLS core with the vector extension.
- I could not reach the Goossens book chapters (paywalled). His measured CPI/Fmax for the in-order pipelined RV32I on Pynq is not in these notes.
- I could not extract HL5's absolute Fmax on FPGA.

## Q2. Known HLS limitations for CPUs and recommended coding patterns; when teams moved to RTL; mixed approaches

### Takeaway
The main obstacle is that HLS schedules for the worst case. A plain ISS-style `while(1){fetch;decode;execute}` loop cannot reach II=1, because of RAW hazards through the register file and the next-PC dependency (II≥3). Published HLS cores work around this the same way:
- write the pipeline by hand inside one II=1 loop body, with explicit inter-stage registers and explicit stall/forward signals;
- write multi-cycle units (divider, FPU, caches) as FSMs that stall the pipeline;
- or split stages into concurrent processes connected by channels or streams.

### Cited Findings
- [Demonstrated/analysis] "Current HLS tools cannot achieve an II of 1 with such an ISS-like processor description":
  - RAW through the register file: "HLS tools always schedule for the worst case".
  - Next-PC dependency: "leads to an Initiation Interval greater or equal to 3".
  - Fixing this needs scheduling for the most probable path, plus speculation and cancellation, which the tools do not do automatically — [Comet ICCAD'19](https://people.rennes.inria.fr/Olivier.Sentieys/publications/2019/Rokicki19ICCAD.pdf)
- [Demonstrated pattern, Comet] The loop body executes all pipeline stages each iteration, working on explicit inter-stage register structs:
  1. Compute `stall[5]` (from cache miss, global stall, or a load-use hazard).
  2. Update the stage registers only if not stalled.
  3. Forwarding logic compares source and destination register numbers and muxes in values from Execute or Memory.
  4. Process stages in reverse order so the loop has no inter-iteration dependencies.
  — same source
- [Demonstrated pattern, Comet] For multi-cycle operators, "an implementation based on a for loop is not suitable, as HLS compilers always schedule for the worst case and will hence lower the II". The fix is to write each one as an FSM (one state per cycle) that stalls Execute. This was used for the divider, the FPU, and the set-associative I/D caches (stalling on a miss while the line is filled). It also lets the tool share the ALU subtractor with the divider — same source
- [Demonstrated pattern, HL5] Stages are separate clocked threads connected by latency-insensitive point-to-point channels (conditionally-blocking for in-order flow, non-blocking where order is not fixed). Feedback paths (WB→F, D→F) are fixed pipeline registers — [HL5 CICC'20](http://www.cs.columbia.edu/~luca/research/mantovani_CICC20.pdf)
- [Demonstrated pattern, Goossens OoO] Multi-ported BRAM variables, fully unrolled tables, and manual removal of false dependencies (PC written in execute, read in fetch) let each stage fit a 10 ns cycle — [Goossens slides 2019](https://open-src-soc.org/2019-10/media/slides/2nd-RISC-V-Meeting-2019-10-02-10h15-Bernard-Goossens.pdf)
- [Experience] Vivado HLS lacked the "clocking mechanisms" needed to describe a concurrent OoO model, so that project ended without reaching its goal — [Hanselman](https://www.hanselmandrew.com/projects/risc-v-cpu-in-hls)
- [Doc] Free-running (`ap_ctrl_none`) Vitis kernels:
  - they have no control ports and cannot be started or stopped;
  - they talk only through `hls::stream` (no memory ports, in the Vitis acceleration kernel flow);
  - they need `#pragma HLS interface ap_ctrl_none port=return` inside the body.
  — [Vitis Accel Examples: streaming free-running kernel](https://xilinx.github.io/Vitis_Accel_Examples/2019.2/html/streaming_free_running_kernel.html); [UG1393 Free-Running Kernels](https://docs.amd.com/r/2022.2-English/ug1393-vitis-application-acceleration/Free-Running-Kernels)
- [Doc/forum] Co-simulation restriction: "Cosim only supports the following 'ap_ctrl_none' designs: (1) combinational designs; (2) pipelined design with II of 1; (3) designs with array streaming or hls_stream or AXI4 stream ports" — [AMD Adaptive Support forum](https://adaptivesupport.amd.com/s/question/0D54U00008IBZiNSAX/cosim-error-cosim-only-supports-the-following-apctrlnone-designs?language=en_US)

### Inferences
- **Recommended structure for Ouroboros, based on the Comet and HL5 patterns:**
  - One top-level function with `ap_ctrl_none` (or `ap_ctrl_hs` invoked once, with an internal `while(1)`), holding a single `#pragma HLS PIPELINE II=1` loop body.
  - Explicit `static` stage-register structs and an explicit hazard/forward unit.
  - Multi-cycle blocks (divider, FPU ops, page-table walker, cache refill) written as FSMs that raise stall.
  - Memory reached through `hls::stream` request/response channels to an external RTL or AXI adapter. This avoids II-breaking `m_axi` bursts inside the core loop and gives variable latency through valid/ready.
- Plain `m_axi` pointer accesses inside an II=1 CPU loop would serialize on worst-case latency. A stream-based memory interface, with an RTL or HLS cache/AXI bridge as a separate block, is the pattern consistent with the findings above.
- A mixed approach is a natural hedge: HLS for datapath-heavy blocks (FPU, vector lanes, divider, crypto) and RTL (SystemVerilog/Chisel/SpinalHDL) for the pipeline control and the MMU/trap logic. Comet's result that separately synthesized FPU and core came out smaller supports partitioning. I found no survey that measures how common this mix is (see Gaps).

### Gaps
- I did not find a documented project that started a CPU in HLS and then switched to RTL, with stated reasons, apart from the Hanselman student project.
- I found no paper on HLS-implemented MMU page-table walkers, precise interrupts, or CSR files. Trap and interrupt handling in HLS cores is not described in the sources I could reach.
- I could not access UG1399 sections on `m_axi` latency/outstanding settings, `hls::stream` depth, or the "free-running pipeline" (`ap_ctrl_none` + `#pragma HLS pipeline style=frp`) in full. Check them directly in [UG1399](https://docs.amd.com/r/en-US/ug1399-vitis-hls).

## Q3. Vitis HLS tool facts (2024-2026)

### Takeaway
From 2025.1 the classic `vitis_hls` GUI/command is gone. Work is driven by a config file (`hls_config.cfg`):
- synthesis: `v++ -c --mode hls`
- C simulation, C/RTL co-simulation, packaging and out-of-context implementation: `vitis-run --mode hls --csim|--cosim|--package|--impl`

Packaging produces a Vivado IP Catalog IP (or a `.xo` for the acceleration flow).

### Cited Findings
- [Doc] Commands in UG1399 2025.x:
  - `v++ -c --mode hls --config hls_config.cfg --work_dir <dir>` (synthesis)
  - `vitis-run --mode hls --csim --config ...`
  - `vitis-run --mode hls --cosim --config ...`
  - `--package` (IP Catalog export for Vivado), `--impl` (Vivado out-of-context implementation)
  - The Unified IDE (`vitis -w <workspace>`) calls these same commands internally.
  - `vitis-run --tcl` / `--itcl` remain for Tcl scripting.
  — [UG1399: vitis, v++ and vitis-run Commands (2025.2)](https://docs.amd.com/r/en-US/ug1399-vitis-hls/vitis-v-and-vitis-run-Commands); see also [Vitis-HLS-Introductory-Examples execution methods](https://deepwiki.com/Xilinx/Vitis-HLS-Introductory-Examples/2.1-execution-methods)
- [Doc] In 2025.1:
  - Vitis HLS Classic is deprecated and removed, and the `vitis_hls` command no longer works.
  - Tcl `open_project`/`open_solution` are for batch only; `open_component` is recommended instead.
  - The Unified IDE is the only GUI.
  — [AMD AR 75342: Vitis HLS Known Issues and Updates per Release](https://adaptivesupport.amd.com/s/article/75342?language=en_US)
- [Doc] `export_design` packages the RTL as Vivado IP or as a Vitis `.xo` kernel, and is still present in 2025.1 — [UG1399 export_design](https://docs.amd.com/r/ja-JP/ug1399-vitis-hls/export_design)
- [Doc] AMD maintains a 2026.x known-issues page, so the Vitis 2026.x line exists — [AMD 000040220 Vitis 2026.x Known Issues](https://adaptivesupport.amd.com/s/article/000040220?language=en_US)
- [Doc] `ap_ctrl_none` co-simulation is limited to combinational, II=1 pipelined, or stream-port designs — [AMD forum](https://adaptivesupport.amd.com/s/question/0D54U00008IBZiNSAX/cosim-error-cosim-only-supports-the-following-apctrlnone-designs?language=en_US)

### Inferences
- A free-running CPU top whose ports are only `hls::stream`/AXI4-Stream (instruction/data memory request and response, retire-trace output) fits the supported `ap_ctrl_none` co-simulation categories. An `m_axi` master inside a free-running core would not.
- The C testbench used for csim can be the lock-step harness itself: call DoomV per retired instruction from the stream drained by the testbench. The same testbench is then reused for C/RTL co-simulation (XSim), which is slow (see Q6).
- Fix the Vitis version early. The Goossens repo's warning about 2023.x shows that QoR and behaviour change between releases.

### Gaps
- I did not find a release note confirming the exact 2025.2 or 2026.1 default co-simulation simulator, or whether Verilator is supported as a co-simulation target. Check the UG1399 "C/RTL Co-Simulation" chapter.

## Q4. Lock-step co-simulation of RISC-V RTL against an ISS

### Takeaway
Industry and open-source practice is retirement-level step-and-compare:
1. A monitor in the core emits one record per retired instruction (or trap). This is RVFI or a similar interface.
2. The testbench calls `step()` on the ISS through DPI-C and compares PC, instruction, rd write, memory accesses and CSRs.
3. Non-deterministic events (interrupts, debug requests, MMIO reads, bus errors, cycle counters) are copied from DUT to ISS at the exact instruction where they occur, rather than modelled independently.

DoomV's Sail-format trace already covers the fields RVFI carries.

### Cited Findings
- **RVFI** [Doc]. Per-retirement fields:
  - `rvfi_valid`, `rvfi_order` (64-bit, no gaps or duplicates), `rvfi_insn`, `rvfi_trap`, `rvfi_halt`, `rvfi_intr` (set on the first instruction of a trap handler), `rvfi_mode`, `rvfi_ixl`
  - `rs1/rs2_addr+rdata`, `rd_addr+wdata`, `pc_rdata/pc_wdata`
  - `mem_addr/rmask/wmask/rdata/wdata`
  - per-CSR `rvfi_csr_<name>_rmask/wmask/rdata/wdata`
  - NRET channels for multi-retire
  — [riscv-formal RVFI spec](https://github.com/SymbioticEDA/riscv-formal/blob/master/docs/rvfi.md)
- **Ibex + Spike co-simulation (lowRISC)** [Doc]:
  - A Spike fork (`ibex_cosim` branch) runs in lock-step. RVFI is extended with `rvfi_ext_*` for interrupts, debug and CSRs.
  - API: `step(write_reg, write_reg_data, pc, sync_trap)`, `set_mip()`, `set_nmi()`, `set_debug_req()`, `notify_dside_access()` (every load/store with error flag), `set_iside_error()`, `get_errors()`.
  - Asynchronous traps "take effect at the next step()". The next checked instruction must be the first handler instruction.
  - Interrupt state is sampled at IF→ID/EX and carried down the pipeline. `rvfi_ext_irq_valid` can signal interrupt changes without a retirement.
  - Limitations: only Spike and VCS are supported, and `mcycle` and other performance-counter CSRs mismatch, so test binaries must avoid reading them.
  — [Ibex Co-simulation System docs](https://ibex-core.readthedocs.io/en/latest/03_reference/cosim.html)
- **CVA6 + Spike "tandem"** [Doc]: CVA6 exposes `rvfi_probes` and an RVFI tracer, and runs Spike in tandem through DPI. An open task adds DPI functions to read and write Spike CSRs and to push interrupt and debug signals, "to align RTL and Spike-Tandem" in CSR and interrupt tests — [CVA6 issue #2317](https://github.com/openhwgroup/cva6/issues/2317); [spike.sv](https://github.com/openhwgroup/cva6/blob/master/corev_apu/tb/common/spike.sv); [rvfi_tracer.sv](https://github.com/openhwgroup/cva6/blob/master/corev_apu/tb/rvfi_tracer.sv)
- **OpenHW core-v-verif / ImperasDV (now Synopsys)** [Doc/Claim]:
  - For CV32E40P, step-and-compare with an ISS was replaced by the ImperasDV reference model through the open RVVI.
  - RVVI-TRACE carries retirement state plus "net changes" (interrupt pins and similar) to the reference.
  - Imperas added virtual peripherals for asynchronous events.
  — [CV32E40P verification](https://docs.openhwgroup.org/projects/cv32e40p-user-manual/en/latest/verification.html); [RVVI GitHub](https://github.com/riscv-verification/RVVI); [RVVI news](https://riscv.org/ecosystem-news/2022/07/open-standard-risc-v-verification-interface-rvvi-for-soc-testing-nick-flaherty-ee-news-europe/)
- **Dromajo (Esperanto; RV64GC; now masc-ucsc and chipsalliance)** [Demonstrated]:
  - DPI functions: `cosim_init()`, `step()` (passes PC, instruction and store data; called from the ROB head in BOOM), and `raise_interrupt()` (passes cause and redirects Dromajo into the handler).
  - Checkpoints hold registers, CSRs, memory, PLIC/CLINT programming and counters, so RTL and ISS start from the same state.
  - Found 13 bugs in CVA6, BlackParrot and BOOM. For example, CVA6 committed 0 for a `div -1/1` where Dromajo gave -1.
  - Finding: loading programs through the Debug Transport Module made simulation non-deterministic and caused false mismatches. Pre-loading memory and bootram checkpoints fixed this.
  - Pure post-run trace comparison "fails to work when we test an external stimulus such as interrupts", which is why on-line co-simulation with messages from DUT to ISS is needed.
  — [Kabylkas et al., "Effective Processor Verification with Logic Fuzzer Enhanced Co-simulation", MICRO'21](https://masc.soe.ucsc.edu/docs/micro21.pdf); [masc-ucsc/dromajo](https://github.com/masc-ucsc/dromajo)
- **XiangShan DiffTest** [Demonstrated/Doc]: DUT monitors emit verification events: instruction commit, register and CSR updates, loads/stores, exceptions/interrupts, MMIO. Deterministic events are executed by the REF (NEMU or Spike). Non-deterministic events (external interrupts, MMIO accesses) are "fully synchronize[d] ... from DUT to REF at precise instructions" — [DiffTest-H, MICRO'25](https://talks-pubs.xiangshan.cc/publications/micro2025-DiffTestH.pdf); [OpenXiangShan/difftest](https://github.com/OpenXiangShan/difftest)
- **Sail / TestRIG (Cambridge CHERI)** [Doc]: RVFI-DII adds Direct Instruction Injection and a standard byte-stream packet format over sockets. The Sail RISC-V model and implementations exchange RVFI traces, which are compared ("tandem execution"), with random instruction generation — [TestRIG](https://github.com/CTSRD-CHERI/TestRIG); [RVFI-DII.md](https://github.com/CTSRD-CHERI/TestRIG/blob/master/RVFI-DII.md); [TestRIG paper, IEEE D&T 2023](https://www.repository.cam.ac.uk/bitstreams/eaada502-d82e-485a-ad24-e7386bf2eb6b/download)

### Inferences
- **Minimum per-retirement record for Ouroboros (RVFI-equivalent, mapping directly onto DoomV's Sail-trace fields):**
  - order/seq, pc, next_pc, insn, privilege mode, trap flag + cause/tval, intr (first handler instruction)
  - rd index + value (separate X and F files), vector-register write summary
  - CSR writes (address + value)
  - memory accesses (addr, size/mask, rdata, wdata)
- **Additional non-deterministic event records** placed before the instruction they affect:
  - interrupt taken (cause, or `mip` value)
  - MMIO load value (so DoomV returns the DUT's value)
  - `time`/`cycle`/`instret` read values (either forced into DoomV, or masked from comparison as Ibex does)
  - LR/SC success/failure if there are ever multiple agents
- DoomV is deterministic per run, so DoomV needs a hook to accept forced values ("override this load or CSR read result", "take interrupt X before the next step"). This is the same role as Ibex's `set_mip`/`notify_dside_access` and Dromajo's `raise_interrupt`.

### Gaps
- I did not check whether sail-riscv has an official in-tree RVFI-DII/cosim mode today. It was historically provided via TestRIG builds.

## Q5. Running lock-step on the FPGA itself (streaming retirement traces)

### Takeaway
FPGA-hosted lock-step has been demonstrated (Fromajo/FireSim; XiangShan DiffTest-H over PCIe). The bottleneck is the DUT-to-host link and software processing, not the DUT clock. Naive per-instruction transfer gives about 1 MHz effective. Batching and packing gave 7.8 MHz for a 6-wide core. A plain trace dump with no live checking ran at about 6 MHz in FireSim's TracerV.

### Cited Findings
- [Demonstrated] Fromajo (FireSim + Dromajo): SonicBOOM on FPGA, with the committed-instruction stream checked against Dromajo at about 1 MHz. Divergences are cycle-exact and reproducible — [SonicBOOM CARRV 2020](https://people.eecs.berkeley.edu/~krste/papers/SonicBOOM-CARRV2020.pdf); [FireSim PR #541](https://github.com/firesim/firesim/pull/541); [FireSim Dromajo docs](https://docs.fires.im/en/1.12.0/Advanced-Usage/Debugging-and-Profiling-on-FPGA/Dromajo.html) ("highly experimental", single-core only)
- [Demonstrated] DiffTest-H (XiangShan; Xilinx VU19P over PCIe/XDMA, and Cadence Palladium):
  - Communication overhead was over 98% in baseline DiffTest on Palladium, and over 99% for Fromajo on a 100 MHz FPGA.
  - The fix combines Batch (tight packing of variable-length events into one transfer), Squash (fusing events while keeping check order) and Replay (re-sending unfused events around a failure, for instruction-level debug).
  - Speeds: 7.8 MHz on FPGA (78x over baseline, 1945x faster than 16-thread Verilator); 478 kHz on Palladium.
  - Found 151 bugs, some of which took up to 2 months to hit in Verilator but 11 hours on Palladium.
  - Typical platform speeds cited: RTL simulator about 3 kHz, emulator about 500 kHz, FPGA about 50 MHz.
  — [DiffTest-H MICRO'25](https://talks-pubs.xiangshan.cc/publications/micro2025-DiffTestH.pdf)
- [Demonstrated] FireSim TracerV sends one 512-bit token per committed instruction to the host. Simulation drops from about 40 MHz to about 6 MHz when the trace is saved through xz compression. Another user saw 30 MHz drop to 2 MHz with a custom tracing bridge — [FireSim TracerV docs](https://docs.fires.im/en/latest/Advanced-Usage/Debugging-and-Profiling-on-FPGA/TracerV.html); [Berkeley CS262a report](https://people.eecs.berkeley.edu/~kubitron/courses/cs262a-F22/projects/reports/project9_report_ver2.pdf); [FireSim forum](https://groups.google.com/g/firesim/c/03GMvjpddkc)
- [Doc] ZynqParrot (BlackParrot) does FPGA-accelerated co-emulation scaled down onto Zynq boards — [ZynqParrot arXiv 2509.20543](https://arxiv.org/pdf/2509.20543)

### Inferences
- **Laptop-attached board (USB-JTAG/UART only), with a 64-128 bit compressed record per instruction:**
  - JTAG-to-AXI or UART (~1-12 Mb/s) gives roughly 10^4-10^5 instructions/s. That is too slow for full Linux boots, which take billions of instructions, but fine for tests.
  - A practical alternative: run free on the board, write the retirement trace into DDR as a ring buffer, and stop on a hardware-detected condition. Better still, check on-chip by comparing a hash/signature of retirement records at intervals against DoomV-generated signatures. This approach is not demonstrated in the sources; it is an inference.
- Live per-instruction lock-step over a slow link is limited by the link. Because DoomV is deterministic, a better design for long runs is:
  1. DoomV produces a golden trace offline.
  2. The FPGA streams its trace (or periodic checksums) and records only non-deterministic events.
  3. DoomV replays those events offline.
  4. Narrow the divergence window by bisection.
- A 1 Gb Ethernet or PCIe link (if the board has one) puts you in the 1-10 MHz class demonstrated by Fromajo and DiffTest-H, if you use batching.

### Gaps
- I found no project that did full per-instruction lock-step for a complete Linux boot over JTAG or UART. The published FPGA co-simulation systems use PCIe (XDMA) or FireSim's host link.
- I found no published trace compression ratios for retirement records, beyond TracerV's xz usage and DiffTest-H's Squash reduction ("up to 99.7%" communication overhead reduction per the paper's search summary).

## Q6. Simulator speeds: Verilator vs XSim, and FPGA reference points

### Takeaway
Single-thread Verilator simulates an in-order single-issue core of student or Rocket size at about 30-900 kHz. Rocket runs at about 30 kHz during a Linux boot. A billion-instruction Linux boot therefore takes hours to days in Verilator. FPGA prototypes and FireSim run at 10s-100s of MHz, so on-FPGA execution (with a trace or checksum) is the only practical way to cover a Linux boot.

### Cited Findings
- [Demonstrated] Verilator (single thread) on an i9-9900K booting Linux:
  - student in-order core: about 900 kHz
  - Rocket: about 30 kHz
  - BOOM: about 9 kHz
  - XiangShan: about 0.9 kHz
  - GSIM reports 7.34x over Verilator for the XiangShan Linux boot and 19.94x for CoreMark on Rocket.
  — [GSIM, arXiv 2508.02236](https://arxiv.org/pdf/2508.02236)
- [Demonstrated] Verilator ran rocket-chip asm tests in 42 min against 2,242 min for iverilog (about 50x faster). The thread has no measured VCS comparison — [rocket-chip issue #2160](https://github.com/chipsalliance/rocket-chip/issues/2160)
- [Claim] An RV64 SV core reports Verilator as about 100x faster than iverilog — [y0sshi/RISC-V](https://github.com/y0sshi/RISC-V)
- [Demonstrated] FireSim runs at "10s to 100s of MHz", and Rocket/BOOM Linux at about 40 MHz without tracing — [FireSim](https://fires.im/); [CS262a report](https://people.eecs.berkeley.edu/~kubitron/courses/cs262a-F22/projects/reports/project9_report_ver2.pdf)
- [Demonstrated] The Comet C++ model itself runs as a cycle-accurate simulator at 11.6-23.6 M cycles/s — [Comet ICCAD'19](https://people.rennes.inria.fr/Olivier.Sentieys/publications/2019/Rokicki19ICCAD.pdf)

### Inferences
- An HLS design gives a third, fast verification level for free: C simulation of the HLS source. Judging by Comet, that is likely 10^6-10^7 cycles/s, fast enough to lock-step a Linux boot against DoomV in software in minutes to hours.
- RTL-level co-simulation (Vitis cosim with XSim, or Verilator on the exported Verilog) should be kept for short tests, given the kHz-class speeds above.
- The FPGA gives full speed. All three levels can share one retirement-record format.

### Gaps
- I found no published numbers for Vivado XSim speed on a CPU-sized design. It is widely held to be slower than Verilator, but I have no citable measurement.
- I found no measured C-simulation speed for a Vitis HLS CPU model (Comet's figure is for g++ on Catapult-style C++).
