# A KV260 can carry Ouroboros, barely

Ouroboros is feasible as a proof of concept on the Kria KV260, but only just, and three of its parts have no published precedent. Measured prior art makes the rest credible. Single-hart in-order RV64GC cores fit in **25–30K LUTs on UltraScale+**. Bandwidth-bound LLM decoders on the same board reach **93–94% of DDR bandwidth in 26K LUTs**. HLS has produced pipelined RISC-V cores of near-RTL quality. The three first-of-kind parts are a Linux-capable RV64 core written in HLS, which nobody has published; an RVA23 core (full RVV with FP64, plus H) small enough for a 117K-LUT part; and a RISC-V kernel driving the Zynq PS's USB, DisplayPort and SD controllers while the ARM cores stay idle. The binding resource is LUTs. A full RVA23S64 core is estimated at **46–85K LUTs with a 64-bit vector datapath**, which leaves roughly 30–70K for the accelerator on a 117,120-LUT device. "No ARM software" cannot be literal on this board: a standalone boot always runs an **FSBL on an A53 or R5**. That FSBL can be cut to one run of clock, DDR and bitstream setup, after which it parks, and it can live entirely in the board folder. Once integrated, an estimated **14–18 tok/s for a 1.5B Q4 model** and an Ubuntu boot measured in minutes are reasonable targets. The plan below front-loads design documents, the DoomV lock-step harness and small board experiments. Each of those retires a specific unknown before the core and the accelerator are written.

## Every piece has precedent, but never in this combination

The feasibility question breaks into five parts. Each part has a different evidence base.

**The ISA target is fixed and well defined.** RVA23 was ratified on 22 October 2024 ([HPCwire](https://www.hpcwire.com/off-the-wire/risc-v-announces-ratification-of-the-rva23-profile-standard/)). RVA23S64 makes the following mandatory: V, Sha (H plus related items), Sv39, Sstc, Svnapot, Svpbmt, Svinval, Sscofpmf, Ssnpm/Supm and a long tail of small Z* extensions. **Sv48, Sv57 and the CFI extensions Zicfilp/Zicfiss are optional** ([riscv-profiles](https://github.com/riscv/riscv-profiles/blob/main/src/rva23-profile.adoc)). A minimal compliant core therefore needs only Sv39 plus the Sv39x4 G-stage. Most of the tail is decode or CSR work. On CVA6, the B extension measured +4% LUTs ([Trovato et al.](https://10xengineers.ai/wp-content/uploads/Implementation-and-Performance-Evaluation-of-Bit-Manipulation_Extension-on-CVA6-RISC-V.pdf)), and Sstc had "negligible impact on the area" ([Sá et al.](https://ar5iv.labs.arxiv.org/html/2302.02969)). Three blocks carry the cost: the vector unit (full V implies Zve64d, so vector FP32/FP64 is required), the scalar F/D FPU, and two-stage translation for H.

**The Ubuntu target supports a staged bring-up.** Ubuntu 24.04 LTS needs only RVA20 (RV64GC). Starting with 25.10, Canonical made **RVA23 the minimum baseline and keeps it for 26.04 LTS** ([Ubuntu blog](https://ubuntu.com/blog/canonical-and-ubuntu-risc-v-a-2025-retro-and-looking-forward-to-2026); [Phoronix](https://www.phoronix.com/news/Ubuntu-25.10-To-Require-RVA23)). At release, 25.10's only supported riscv64 platform was QEMU ([Phoronix](https://www.phoronix.com/news/Ubuntu-25.10-RISC-V-QEMU)). An Ouroboros that boots 26.04 would be among the first RVA23 machines Ubuntu runs on, and certainly the first FPGA one. The staging matters for the plan. An RV64GC + Sv39 subset of the core can boot stock 24.04, which is a real milestone well before V and H exist. Canonical states that profiles do not cover boot, device discovery or drivers ([Ubuntu blog](https://ubuntu.com/blog/risc-v-profiles-why-is-rva23-significant)). Ouroboros must therefore provide the platform itself: OpenSBI, a CLINT/ACLINT, a PLIC, a UART, a block device and a device tree. Prior FPGA ports needed custom OpenSBI and U-Boot platforms ([PlanV](https://planv.tech/2026/01/17/linux-on-cva6-on-agilex7-development-kit/)).

**No existing core shows the target fits.** The only open core claiming RVA23 is XiangShan Kunminghu, a server-class out-of-order design. Its maintainers say it does not fit ZCU104-class parts ([XiangShan mailing list](https://www.mail-archive.com/xiangshan-all@ict.ac.cn/msg00085.html)). CVA6 has H, B and an RVV coprocessor (Ara), but these live in separate branches and papers, and Ara has only been put on an FPGA with 2 lanes on VCU118/VCU128 ([pulp-platform/ara](https://github.com/pulp-platform/ara)). No published core combines RV64, full RVV 1.0 with FP and H on a small FPGA. Ouroboros's simple-pipeline RVA23S64 core would be new.

**No Linux-capable core has been written in HLS.** The published HLS cores are RV32. Comet (Catapult) is a 5-stage RV32IMF pipeline. HL5 (Stratus) is RV32IM. Goossens's cores (Vivado/Vitis HLS) include an out-of-order RV32IM that ran at **100 MHz on a ZCU106 in 9,146 LUTs** and was written by one person in two weeks ([Goossens slides](https://open-src-soc.org/2019-10/media/slides/2nd-RISC-V-Meeting-2019-10-02-10h15-Bernard-Goossens.pdf)). Every Linux-capable soft core found is RTL.

**The board is unusual too.** On ZynqMP, existing soft-RISC-V work either keeps the ARM running Linux as a front-end server (fpga-zynq/Rocket on ZCU102) or treats the soft core as a co-processor beside PetaLinux. LiteX's KV260 target defaults to the A53 as its CPU ([litex-boards](https://raw.githubusercontent.com/litex-hub/litex-boards/master/litex_boards/targets/xilinx_kv260.py)). No project was found that boots Linux on a ZynqMP PL soft core with the ARMs idle, and none boots Ubuntu on any ZynqMP soft core.

The table below sorts the risks by how much evidence there is against them.

| Area | Evidence | Verdict |
|---|---|---|
| RV64GC + Sv39 core fits K26 | Rocket+H about 25K LUT per core on ZCU104, measured | Low risk |
| HLS can express a pipelined CPU | Comet, HL5, Goossens: RV32 near Rocket area | Medium risk: RV64 + MMU + traps not shown |
| Full RVA23 (V + H) fits next to an accelerator | Estimate only; V cost "possibly off by about 2x" | **High risk: LUT budget** |
| LLM decode at near-roofline on KV260 | Hummingbird 4.8 tok/s at 93–94% BW | Low risk for the engine; medium with a CPU competing for DDR |
| GGUF-generic accelerator generator | No precedent; all prior designs are per-model | Medium risk: engineering, not physics |
| RISC-V Linux driving PS USB/DP/SD | No prior art; ZynqMP drivers assume firmware calls | **High risk: board layer** |
| Lock-step against DoomV | Ibex/Spike, Dromajo, DiffTest all do this | Low risk; HLS C-sim makes it faster |

## LUTs, not DSPs, decide whether core and accelerator share 117K

The XCK26 has **117,120 LUTs, 234,240 FFs, 1,248 DSP48E2, 144 BRAM36 and 64 URAM**. It runs at a 0.72 V VCCINT, so its timing is slower than a standard -2 part ([DS987](https://mm.digikey.com/Volume0/opasdata/d220001/medias/docus/7161/SM-K26-XCL2GI.pdf)). DSPs, block RAM and URAM are plentiful for this design. LUTs are not.

The core estimate is built from measured anchors. Rocket costs about 27.5K LUTs per core plus 10.8K uncore on 7-series ([vivado-risc-v](https://github.com/eugene-tarassov/vivado-risc-v)). Rocket with H on a ZCU104 measured **50,922 LUTs for two cores, with H adding 11–12% LUTs and 27–30% FFs** ([Sá, Martins, Pinto](https://ar5iv.labs.arxiv.org/html/2103.14951)). A whole CVA6 RV64GC SoC on Kintex-7 is 73,726 LUTs ([Trovato et al.](https://10xengineers.ai/wp-content/uploads/Implementation-and-Performance-Evaluation-of-Bit-Manipulation_Extension-on-CVA6-RISC-V.pdf)). The vector unit has no reliable FPGA anchor. Published Ara figures cannot be literal Vivado LUTs, and no RVV 1.0 unit with FP64 at VLEN=128 has a measured Xilinx utilization. The V line in the table below is therefore the least certain, possibly off by 2x. Because DDR comes from the PS, no fabric memory controller is needed, which saves LUTs that the 7-series totals above include.

| Block (UltraScale+ LUT6, estimates) | LUTs |
|---|---|
| Scalar RV64IMAC pipeline, B/Zicond/Zcb/Zfa decode, CSRs, PMP | 8–15K |
| Sv39 PTW, I/D TLBs, Svnapot/Svpbmt/Svinval | 3–6K |
| L1 I$/D$ control (arrays in BRAM), AXI to PS, Zicbom/Zicboz | 3–6K |
| Scalar F/D FPU with FMA, div/sqrt, Zfhmin | 8–15K (+10–30 DSP) |
| H (Sha): VS CSRs, Sv39x4 two-stage walk, G-TLB | +3–6K |
| V, VLEN=128, **32-bit** datapath | 12–20K |
| V, VLEN=128, **64-bit** datapath | 18–30K |
| V, VLEN=128, **128-bit** datapath | 30–50K |
| Uncore: ACLINT, PLIC, UART, debug, interconnect | 3–8K |
| **Core total, 32 / 64 / 128-bit V datapath** | **40–75K / 46–85K / 58–105K** |

The owner's configurable vector datapath width is therefore the main lever on the whole system, not a detail. Each step from 32 to 64 to 128 bits costs roughly 6–30K LUTs, and the permute crossbar grows roughly with the square of the width. RVA23 mandates functional V, not throughput. A compliant core can share one FMA between scalar F/D and vector FP, and can run vrgather, segment loads, vector div/sqrt and FP64 reductions as slow multi-cycle sequencers. Trap-and-emulate is not compliant, but slow is.

On the accelerator side, a bandwidth-matched decoder is small. Hummingbird runs LLaMA3-8B at **4.8 tok/s on the KV260 in 26K LUT, 179 DSP, 59 BRAM and 18 URAM** ([Hummingbird](https://arxiv.org/html/2507.03308v1)). Designs that also accelerate prefill and attention fill the chip: TeLLMe v2 uses **98,303 LUT (84%)** and PD-Swap uses **102,102 LUT (87%)** ([TeLLMe v2](https://arxiv.org/html/2510.15926v2); [PD-Swap](https://arxiv.org/html/2512.11550)). Combining a 64-bit-datapath core (about 65–80K expected) with a Hummingbird-class decoder gives about 91–106K LUTs, or 78–90% of the device. Above about 80% utilization, place-and-route time and timing-closure difficulty climb sharply ([edaboard](https://www.edaboard.com/threads/vivado-taking-a-long-time-to-run-synthesis-implementation.384348/), low-authority forum source). The KV260 default should be the **32-bit vector datapath plus a decode-first accelerator** that does its multiply-accumulates in LUTs and DSPs and spends spare DSPs on prefill. The 64- and 128-bit datapaths stay configurable for larger boards. An HLS-specific overhead sits on top of these numbers. Comet's rv32i used 2,032 LUTs against PicoRV32's 880, though Rocket's RTL was similar at 2,253 ([Comet](https://people.rennes.inria.fr/Olivier.Sentieys/publications/2019/Rokicki19ICCAD.pdf)). The first synthesized scalar core is the measurement that decides the final split.

Clock speed follows the same logic. Linux-capable RV64 soft cores run at **50–100 MHz** in published Xilinx flows, and CVA6 with H ran at 100 MHz on Genesys 2 ([Sá et al.](https://ar5iv.labs.arxiv.org/html/2302.02969)). HLS RV32 cores reached 70–80 MHz on Artix-7 against 110–140 MHz for tuned RTL ([Comet](https://people.rennes.inria.fr/Olivier.Sentieys/publications/2019/Rokicki19ICCAD.pdf)). A planning figure of **about 100 MHz for the core** is realistic on the 0.72 V K26. The accelerator can run in its own clock domain at 200–300 MHz, as the KV260 LLM designs do. No measured time-to-shell exists for Ubuntu on any soft core. At this clock, a full systemd boot takes minutes, so the first images should be minimal.

## HLS can build the core if the pipeline is scheduled by hand

The constraint that all hardware is C++ for Vitis HLS is the project's largest engineering risk. The evidence also shows how to manage it. The root problem is that HLS schedules for the worst case. An ISS-style `while(1){fetch; decode; execute}` loop cannot reach II=1, because of read-after-write hazards through the register file and the next-PC dependency, which forces **II≥3** ([Comet](https://people.rennes.inria.fr/Olivier.Sentieys/publications/2019/Rokicki19ICCAD.pdf)). A student project that tried an out-of-order core in Vivado HLS gave up because the tool lacked "clocking mechanisms" to describe concurrent state ([Hanselman](https://www.hanselmandrew.com/projects/risc-v-cpu-in-hls)). Every successful HLS core stops letting the tool find the pipeline and writes it out explicitly.

Comet supplies the core pattern. One loop body runs at II=1 and executes every stage on each iteration, using explicit inter-stage register structs. It computes a stall vector first (from cache miss, load-use hazard or a busy multi-cycle unit), updates only unstalled stage registers, forwards by comparing register indices, and processes stages in reverse order so no dependency crosses loop iterations. Multi-cycle units are written as FSMs with one state per cycle that raise stall, because a `for` loop inside the pipeline makes the tool assume the worst-case latency for the whole body. Comet used this for the divider, the FPU and set-associative caches ([Comet](https://people.rennes.inria.fr/Olivier.Sentieys/publications/2019/Rokicki19ICCAD.pdf)). HL5 shows the complementary pattern: stages as separate clocked processes linked by latency-insensitive channels, using conditionally-blocking channels for in-order flow ([HL5](http://www.cs.columbia.edu/~luca/research/mantovani_CICC20.pdf)). Goossens adds multi-ported BRAM variables, fully unrolled tables and manual removal of false dependencies such as the PC written in execute and read in fetch ([Goossens slides](https://open-src-soc.org/2019-10/media/slides/2nd-RISC-V-Meeting-2019-10-02-10h15-Bernard-Goossens.pdf)).

**Decomposition is a requirement.** In Comet, the FPU and core synthesized separately came out smaller than the two together (8,147 + 15,299 µm² against 26,760 µm²), and HLS runtime fell from 23 minutes to about 2 minutes each. The authors read this as "reaching the limits of what current HLS tools can perform" ([Comet](https://people.rennes.inria.fr/Olivier.Sentieys/publications/2019/Rokicki19ICCAD.pdf)). An RVA23 core is an order of magnitude larger than Comet, so Ouroboros's core should be several HLS top functions, each synthesized and packaged as its own Vivado IP and connected by `hls::stream`/AXI4-Stream in a Vivado block design:

- an integer pipeline with the CSR file and trap unit,
- the FPU,
- the vector unit, whose datapath width is a template parameter,
- the MMU/page-table walker,
- the cache and bus bridge to the board's memory ports.

That connection must still be a Vivado-generated wrapper, never hand-written HDL.

Memory belongs behind streams too. `m_axi` accesses inside an II=1 loop serialize on worst-case latency. A request/response stream to a separate HLS cache and AXI bridge gives variable latency through valid/ready. Streams also suit verification. Vitis co-simulation of free-running `ap_ctrl_none` designs supports **only combinational designs, II=1 pipelines, or designs with stream ports** ([AMD forum](https://adaptivesupport.amd.com/s/question/0D54U00008IBZiNSAX/cosim-error-cosim-only-supports-the-following-apctrlnone-designs?language=en_US)). A core whose only ports are memory streams, interrupt inputs and a retirement-trace stream fits that envelope.

Three points remain new ground with no published HLS precedent:

- precise traps across a large CSR file,
- interrupts that are synchronous to retirement,
- two-stage page walks.

The mitigation is the C-simulation lock-step described below. Every hazard and trap corner is found at software speed against DoomV, before any synthesis run. Two tooling facts shape the setup:

- From 2025.1, the classic `vitis_hls` command is gone. Synthesis is `v++ -c --mode hls --config hls_config.cfg`, and C-sim, co-sim and packaging are `vitis-run --mode hls --csim|--cosim|--package` ([UG1399](https://docs.amd.com/r/en-US/ug1399-vitis-hls/vitis-v-and-vitis-run-Commands); [AMD AR 75342](https://adaptivesupport.amd.com/s/article/75342?language=en_US)).
- Directives change between releases. hls4ml broke on 2024.2 when `config_array_partition -maximum_size` was removed ([hls4ml #1231](https://github.com/fastmachinelearning/hls4ml/issues/1231)). Goossens's repository warns against 2023.1/2023.2 ([goossens-book-ip-projects](https://github.com/goossens-springer/goossens-book-ip-projects)).

Ouroboros should pin one AMD release per project release and refuse to build on any other. The K26 needs no paid licence under Vivado ML Standard ([AMD forum](https://adaptivesupport.amd.com/s/question/0D52E00007G0tIJSAZ/vivado-and-kria-board-k26-som?language=en_US)).

## DoomV lock-step runs at three speeds from one record format

Industry practice is retirement-level step-and-compare, and it maps directly onto DoomV. The core emits one record per retired instruction or trap. The harness calls DoomV's step and compares the two. Events that cannot be predicted are copied from the device under test to the reference at the exact instruction where they happen. The record follows RVFI ([riscv-formal RVFI](https://github.com/SymbioticEDA/riscv-formal/blob/master/docs/rvfi.md)): order, pc and next pc, instruction, privilege mode, trap flag with cause and tval, an interrupt flag on the first handler instruction, rd index and value (X, F and a vector-write summary), CSR writes, and memory address, mask and data. Precedent shows what DoomV needs beyond a plain step function:

- Ibex's Spike co-simulation exposes `set_mip`, `set_nmi`, `set_debug_req` and `notify_dside_access`, and masks `mcycle` ([Ibex cosim](https://ibex-core.readthedocs.io/en/latest/03_reference/cosim.html)).
- Dromajo's `raise_interrupt` redirects the reference into the handler.
- Dromajo found that loading programs through the debug module caused false mismatches, which pre-loaded memory checkpoints fixed ([Kabylkas et al., MICRO'21](https://masc.soe.ucsc.edu/docs/micro21.pdf)).
- Dromajo also showed that post-run trace comparison "fails to work when we test an external stimulus such as interrupts".

DoomV therefore needs override hooks: take interrupt X before the next step, return this value for this MMIO load, force this `time`/`cycle` read. It also needs a checkpoint format that both sides can start from. This fits the project's determinism rule, because the recorded event log becomes part of the input that makes a run reproducible.

The three levels share the record and differ in speed by about four orders of magnitude.

| Level | Where | Expected speed | Use |
|---|---|---|---|
| C simulation | HLS C++ core and DoomV in one process | about 10⁶–10⁷ cycles/s (Comet's C++ model ran 11.6–23.6 M cycles/s) | Every commit; riscv-tests, riscv-vector-tests, arch-test, riscv-dv seeds; full Linux and Ubuntu boots |
| RTL simulation | Vitis cosim (XSim) or Verilator on the generated Verilog | kHz class (Rocket booting Linux in Verilator: about 30 kHz) | Short directed tests that prove the generated RTL matches the C++ |
| On board | KV260, trace to DDR ring buffer or periodic signatures | link-limited: about 1 MHz (Fromajo) to 7.8 MHz (DiffTest-H, batched) on fast links | Milestone boots at full speed; bisect divergences offline |

Sources for the speeds: [Comet](https://people.rennes.inria.fr/Olivier.Sentieys/publications/2019/Rokicki19ICCAD.pdf), [GSIM](https://arxiv.org/pdf/2508.02236), [SonicBOOM/Fromajo](https://people.eecs.berkeley.edu/~krste/papers/SonicBOOM-CARRV2020.pdf), [DiffTest-H](https://talks-pubs.xiangshan.cc/publications/micro2025-DiffTestH.pdf).

The C-simulation level is the main benefit of HLS for verification, and the plan should depend on it. An RTL team must lock-step Linux boots in Verilator at tens of kHz, which takes days. Ouroboros can do the same at C speed in minutes to hours, because the C++ is the hardware. Comet's authors noted that their C++ source doubled as a cycle-accurate simulator. The caveat is that C-sim proves only the C++ semantics. HLS scheduling, stream depths and `ap_ctrl_none` behaviour must still be checked at RTL level, which is why a cosim regression of short tests on the generated Verilog is mandatory on every synthesis.

The board level is constrained by the KV260's host link. The board has only an FTDI USB-UART/JTAG for the host ([UG1089](https://docs.xibif.ch/_downloads/480ec1217d1ac2bd520e695148cfe86f/KV260_Userguide.pdf)). Its Ethernet sits on the PS, and in the published FPGA co-simulation systems the link, not the device, set the speed: communication was over 99% of Fromajo's run time ([DiffTest-H](https://talks-pubs.xiangshan.cc/publications/micro2025-DiffTestH.pdf)). No published project lock-stepped a full Linux boot over JTAG or UART. The recommended on-board design is therefore an inference, not a demonstrated technique:

1. The core writes retirement records, or a running hash of them, into a DDR ring buffer.
2. Only non-deterministic events are logged in full.
3. DoomV replays the event log offline and compares hashes.
4. A mismatch interval is bisected by re-running with full traces around it.

riscv-formal checks the RVFI port of the generated Verilog. Its wrapper is testbench code, not hardware, so it does not conflict with the no-HDL rule, but the owner should confirm that reading.

## The PS is unavoidable plumbing, so confine it to one folder

The KV260 is not a neutral FPGA board. Its processing system owns DDR, the PL clocks, boot and every PC-style peripheral. The research turns "no software on the ARM cores" into a precise, minimal statement and a concrete board layer.

**Memory.** All 4 GB of DDR4 (64-bit, 2400 MT/s, 19.2 GB/s theoretical) sits on the PS DDR controller. The PL reaches it only through the PS-PL AXI slave ports: four HP, two HPC, plus ACP, ACE and LPD. These are 32/64/128-bit on the PL side ([DS987](https://mm.digikey.com/Volume0/opasdata/d220001/medias/docus/7161/SM-K26-XCL2GI.pdf); [UG1085](https://0x04.net/~mwk/xidocs/ug/ug1085-zynq-ultrascale-trm.pdf)). One HP port measured about 3 GB/s ([ResearchGate summary](https://www.researchgate.net/publication/336714879_Unexpected_Diversity_Quantitative_Memory_Analysis_for_Zynq_UltraScale_Systems)) and reached 60–70% utilization on an Ultra96 ([j-marjanovic.io](https://j-marjanovic.io/exploring-the-ps-pl-axi-interfaces-on-zynq-ultrascale-mpsoc.html)). Near-roofline LLM decode therefore needs **at least four ports in parallel**, as both KV260 decoders found. DDR appears as two 2 GB windows, at 0x0 and at 0x8_0000_0000 ([litex-boards](https://raw.githubusercontent.com/litex-hub/litex-boards/master/litex_boards/targets/xilinx_kv260.py)). That split must be hidden by a remap in the board layer or described in the device tree. The soft core should use a non-coherent HP port, since no ARM caches need to stay coherent.

**Clocks.** The KV260 has **no PL clock source independent of the PS**. PL clocks come from `pl_clk`, which the FSBL configures ([litex-boards platform](https://raw.githubusercontent.com/litex-hub/litex-boards/master/litex_boards/platforms/xilinx_kv260.py); [kv260_bringup](https://github.com/tomverbeure/kv260_bringup)).

**Boot.** After power-on, the PMU ROM and the CSU BootROM always run. Both are hardwired, triple-redundant controllers. The CSU then loads an FSBL "for execution by either the RPU and APU", and the FSBL's `psu_init` sets PLLs, `pl_clk`, MIO and the DDR controller and loads the bitstream through PCAP ([UG1085](https://0x04.net/~mwk/xidocs/ug/ug1085-zynq-ultrascale-trm.pdf); [AMD FSBL wiki](https://xilinx-wiki.atlassian.net/wiki/spaces/A/pages/18842019/FSBL)). There is no hardware path in which the boot ROM configures DDR or the PL alone. The minimal unavoidable ARM involvement is:

- **one FSBL run on the R5-0**, chosen in the boot header, which performs `psu_init`. Beyond clocks and DDR, it leaves PS-GTR, USB, SD and DisplayPort clocks and resets statically enabled.
- **one PCAP bitstream load**,
- **then a WFI park**. The A53 cluster stays in reset, because the FSBL releases only the cores it loads images for.

PMU firmware is "required in most systems" ([UG1085](https://0x04.net/~mwk/xidocs/ug/ug1085-zynq-ultrascale-trm.pdf)). Whether a BOOT.BIN without it boots cleanly is unverified. The PS power domains, DDR controller and FPD switch must stay up for the whole session, so "no ARM software" never means "no PS".

For development there is a stricter option with zero ARM instructions: XSCT replays the exported `psu_init.tcl` register writes over JTAG and configures the PL over JTAG ([Trenz wiki](https://wiki.trenz-electronic.de/display/PD/MPSoC+Debug); [AMD wiki](https://xilinx-wiki.atlassian.net/wiki/spaces/A/pages/84444479/TCL+script+to+auto-generate+a+jtag+boot+script+based+on+HDF+file+for+Zynq+Ultrascale)). That is tethered, so a laptop still needs the FSBL. Handing DDR training to the RISC-V after a clocks-only FSBL is theoretically possible but needs a ported DDR PHY training sequence, and is not recommended.

The stock Kria chain must also be replaced. It runs ImgSel, FSBL, PMUFW, TF-A, U-Boot and then Linux on the A53s, with A/B images in QSPI ([UG1089](https://docs.xibif.ch/_downloads/480ec1217d1ac2bd520e695148cfe86f/KV260_Userguide.pdf); [Kria boot FW](https://xilinx.github.io/kria-apps-docs/bootfw/build/html/docs/bootfw_overview.html)). This changes the toolflow. The vendor's custom-PL path, an app folder loaded by `xmutil loadapp` through dfx-mgr ([Kria firmware docs](https://xilinx.github.io/kria-apps-docs/kv260/2022.1/build/html/docs/generating_custom_firmware.html)), runs on ARM Linux and is therefore excluded. Ouroboros's KV260 deliverable is its own BOOT.BIN: FSBL, possibly PMUFW, and the bitstream. Writing it to QSPI so that it bypasses ImgSel and the A/B confirmation is untested. Interrupting stock A/B boot leaves an unconfirmed image that reverts to Image A, so the board-bring-up phase must prove the flashing path, over JTAG or the Boot Image Recovery tool, before anything depends on it.

**Peripherals.** Everything a laptop needs is on the PS: USB 3.0 through a hub, HDMI and DP (both from the PS DisplayPort controller through an STDP4320 demultiplexer), Gigabit Ethernet, microSD, QSPI and eMMC. The PL owns only the camera interfaces, one 8-pin Pmod and the fan-enable pin ([UG1089](https://docs.xibif.ch/_downloads/480ec1217d1ac2bd520e695148cfe86f/KV260_Userguide.pdf); [Kria design overview](https://xilinx.github.io/kria-apps-docs/kv260/2022.1/build/html/docs/smartcamera/docs/introduction.html)). Since the fan's PWM pin is on the PL, the Ouroboros bitstream must drive it.

A PL master can in principle reach the PS peripheral registers through S_AXI_LPD. The obstacle is software. Linux's ZynqMP USB, SD and DP glue gets clocks and resets through firmware calls via TF-A and PMUFW, and a riscv64 kernel cannot make those calls. The workaround is to leave the clocks and resets enabled at FSBL time and describe the controllers to Linux as generic `snps,dwc3` and SDHCI nodes with fixed clocks. That is plausible but has no prior art. DisplayPort link training is software too. It can run on the RISC-V itself, in M-mode firmware or U-Boot inside the board layer, which then hands Linux a simple framebuffer that the PL fills or the DPDMA scans out. This split is an inference; it keeps all board code on the one processor Ouroboros allows. Whether PS peripheral interrupts reach a PL interrupt controller is also unverified, and polling is the fallback.

The fallback that needs no PS peripherals uses the Pmod: two pins for a USB low/full-speed HID host, four for SPI-mode microSD at roughly 1–3 MB/s, and two for a UART. The existing small HID-host core uses under 300 LUTs ([nand2mario/usb_hid_host](https://github.com/nand2mario/usb_hid_host)), but it is Verilog. Under the HLS rule, open PL peripheral cores such as this one serve only as reference designs to re-implement in C++. That includes the HID host, LiteSDCard and VGA timing generators.

**What portability means concretely.** The core and the accelerator should see only a small, board-agnostic contract:

- one or more memory-request streams, each with a physical address window,
- an MMIO window,
- interrupt lines,
- clock and reset,
- a retirement-trace stream.

Everything the KV260 forces lives in `FPGA-Hardware/boards/kv260/`:

- a resource and part descriptor that Hydra reads (LUT/DSP/BRAM/URAM counts, `xck26-sfvc784-2LV-c`, memory windows, number and width of memory ports),
- the Vivado block-design Tcl that instantiates `zynq_ultra_ps_e` with its HP/LPD ports and `pl_clk`,
- the HLS memory-port adapters that map the core's streams onto the HP ports and hide the split DDR map,
- the XDC with the fan and Pmod pins,
- the FSBL configuration and BIF that build BOOT.BIN,
- the OpenSBI/U-Boot platform and device-tree fragment, including any DP link-training and PS-peripheral setup code that runs on the RISC-V.

A second board then becomes a second folder. The notes suggest the right second targets, each of which exercises a different variant of the contract. A Genesys 2 (Kintex-7, about 204K LUTs, 1 GB of PL DDR3, no ARM) removes the FSBL entirely, and vivado-risc-v already boots Debian on it ([Digilent](https://digilent.com/reference/programmable-logic/genesys-2/start); [vivado-risc-v](https://github.com/eugene-tarassov/vivado-risc-v)). A ZCU104 (about 230K LUTs, PL DDR4 SODIMM) keeps ZynqMP but gives the soft core its own memory ([UG1267](https://www.mouser.com/pdfDocs/ug1267-zcu104-eval-bd.pdf)). Either one is the escape route if the KV260's LUT budget fails, without forking the code.

## Hydra should size decode by bandwidth and prefill by DSPs

Decode at batch 1 is a matrix-vector product with no weight reuse, so its speed is set by memory bandwidth: **tok/s ≈ effective bandwidth ÷ (weight bytes + context length × KV bytes per token)**. Measured results support this model. The DATE'25 KV260 decoder ran LLaMA2-7B at **4.9 tok/s at 84% of bandwidth**, and Hummingbird ran LLaMA3-8B at **4.8 tok/s at 93–94%**, each within about 5% of the formula ([Hummingbird](https://arxiv.org/html/2507.03308v1); [adamgallas/llama-fpga](https://github.com/adamgallas/llama-fpga)). Those designs had the DDR to themselves. With a soft CPU running Ubuntu on the same controller, 60–80% efficiency is the planning range, which gives 11.5–15.4 GB/s:

| Model | Q4 (4.5 bpw) tok/s | Q8_0 tok/s | Fits beside Ubuntu in 4 GB? |
|---|---|---|---|
| 0.5B | 41–55 | 22–29 | Yes |
| 1B | 21–27 | 11–15 | Yes |
| 1.5B | 14–18 | 7–10 | Yes (Qwen2.5-1.5B: 28 KiB KV per token, 32K context ≈ 0.9 GiB) |
| 3B | 7–9 | 4–5 | Q4 yes; Q8 tight |
| 7B | 3–4 | no | No, once an OS is resident |

These are estimates from the notes' arithmetic, using the [Qwen2.5-1.5B config](https://huggingface.co/Qwen/Qwen2.5-1.5B/raw/main/config.json). KV traffic lowers them as context grows: 4K of context costs Qwen2.5-1.5B about 12%, and 32K roughly halves decode. Non-GQA models such as SmolLM2-1.7B carry 192 KiB of KV per token ([config](https://huggingface.co/HuggingFaceTB/SmolLM2-1.7B/raw/main/config.json)) and should be flagged by Hydra. The sweet spot on the KV260 is **0.5–1.5B GQA models at Q4/Q8**. A published soft-CPU-hosted result does not exist; every KV260 design used the A53s.

Two consequences follow for the hardware Hydra generates. First, decode needs very few multipliers. 15.4 GB/s of Q4 weights is about 27 G MAC/s, about 109 MACs per cycle at 250 MHz, which is roughly 28–55 DSPs or about 3K LUTs of 4×8-bit multipliers. DSP packing gives four INT4 multiplies per DSP48E2 ([AMD WP521](https://docs.amd.com/api/khub/documents/SDFn1nGbW4R1ag1QuXRHRg/content)) or two INT8 multiplies that share an operand ([AMD WP486](https://docs.amd.com/api/khub/documents/z7yAy_aweTmRYkGaTVyhbw/content)). Unsigned Q4_K values need their own correction analysis. What decode needs is several 128-bit AXI masters and a dequant pipeline wide enough to keep up with them. Second, prefill is compute-bound. With 1,024 DSPs and INT8 packing at 250 MHz, the peak is about 1 TOPS, or at most about 330 tok/s for a 1.5B model. At Q4 the array becomes compute-bound once a tile reuses each weight across **about 19 tokens**, and the activation buffer for that is trivial next to the URAM.

The owner's systolic array fits this shape. One dimension streams weight blocks at DDR rate. The other dimension is the token tile T: it is 1 in decode, where the array degenerates to a GEMV row, and grows only to buy prefill throughput. The user's "fast prefill / fast decode / balanced" choice in the configurator then maps onto those two dimensions. Dynamic partial reconfiguration, as in PD-Swap, can swap prefill and decode attention logic at runtime ([PD-Swap](https://arxiv.org/html/2512.11550)). That is a later option, since driving PCAP from the PL is itself unproven.

GGUF makes the generator practical. The parser can stop before the tensor data: a fixed header, typed key/value metadata and a tensor-info table give the architecture, dimensions and per-tensor `ggml_type` ([gguf.md](https://github.com/ggml-org/ggml/blob/master/docs/gguf.md)). The PE datatype set comes from a per-tensor type histogram, not from the file name, because "Q4_K_M" files mix Q4_K and Q6_K. The quant blocks are fixed-size ([ggml-common.h](https://raw.githubusercontent.com/ggml-org/llama.cpp/master/ggml/src/ggml-common.h)): Q4_0 and Q8_0 hold 32 weights with an fp16 scale, and Q4_K holds 256 weights with fp16 d/dmin and 6-bit sub-scales. A PE therefore computes an integer dot product per 32-weight sub-block. One post-stage applies `d·sc_j` and subtracts `dmin·m_j·Σx`, using activation sums precomputed as llama.cpp's Q8_K `bsums` do, at about 1/32 of the MAC cost. The first PE set should be Q4_0, Q8_0, Q4_K, Q6_K and F16. The IQ codebook formats can wait.

No published FPGA engine consumes native GGUF K-quant blocks. All of them re-quantize to AWQ, GPTQ or ternary layouts. Re-laying out the GGUF weights at load time into burst-aligned streams is an untested design decision. No prior design is model-generic either. The DATE'25 design is "tightly coupled to the internal structure of LLaMA2-7B" ([llama-fpga](https://github.com/adamgallas/llama-fpga)). Hydra's GGUF-to-configuration generation would be new.

The software side should be a **new ggml backend** that claims MUL_MAT through `supports_op`/`offload_op` and drives the accelerator through MMIO descriptors and DMA ([ggml-backend.h](https://raw.githubusercontent.com/ggml-org/llama.cpp/master/ggml/include/ggml-backend.h)). SECDA-LLM showed this pattern for FPGA matmul offload ([SECDA-LLM](https://arxiv.org/pdf/2408.00462)). Because the host is a roughly 100 MHz in-order core, Ouroboros should also offload RMSNorm, RoPE, SiLU, softmax/attention and the KV-cache append. In the Qwen2.5 KV260 design those ran on the A53, and matmul was still 91.6% of the latency ([Qwen2.5 on KV260](https://arxiv.org/html/2504.17376v1)). Weights must sit in physically contiguous memory (CMA or hugepages) for the accelerator's AXI masters. The submodule `llama.cpp` doubles as the numerical reference: C-sim of each HLS kernel should match its GGML CPU op bit-for-bit or within a stated tolerance.

**The configurator's own build is routine.** Hydra emits:

- a generated `ouro_params.h`, a single hashed source of truth, rather than scattered `-D` flags,
- `hls_config.cfg` files for `v++`,
- a non-project `vivado -mode batch` Tcl script that sources the board's block-design Tcl,
- the BOOT.BIN BIF.

It reports estimates in three labelled tiers: analytic in seconds, `csynth.xml` in minutes, and post-route reports read through Tcl queries or `.rpx` as ground truth ([AMD AR 62391](https://www.xilinx.com/support/answers/62391.html)). It should fail fast when the analytic tier exceeds about 80% of any resource. For the Claude-Code-style interface, Python with Rich (inline live region plus scrollback) or Textual fits best. llama.cpp's `gguf-py` can be reused directly, Vivado runs natively on the owner's Windows 11, and AMD's `[Tool ID-Num]` message IDs make "what failed and why" classification tractable. Claude Code itself uses Ink with React ([Pragmatic Engineer](https://newsletter.pragmaticengineer.com/p/how-claude-code-is-built)). Builds should run under a short path with no spaces, since folder names like "Emmanuel Roy" are a common source of Tcl failures.

## Off-the-shelf parts make a $460–650 laptop

The physical laptop is the least risky part. The KV260 runs from **12 V at 3 A**, and AMD sizes its fansink for a 10 W MPSoC budget ([UG1089](https://docs.xibif.ch/_downloads/480ec1217d1ac2bd520e695148cfe86f/KV260_Userguide.pdf)). The parts list:

- the KV260 kit at about $249–294,
- a 67 Wh TalentCell 12 V pack at about $30 ([Amazon](https://us.amazon.com/Talentcell-Rechargeable-6000mAh-Battery-Portable/dp/B00MF70BPU)),
- an HDMI-to-eDP driver board at $17–22 with a 14-inch panel ([eBay](https://www.ebay.com/itm/167229239433)),
- a USB keyboard on the Pmod HID path.

That gives a 3D-printed clamshell for roughly $480–650. A CrowView Note shell gives a similar cost, but its battery outputs only 5 V ([CNX](https://www.cnx-software.com/2024/08/17/crowview-note-review-a-14-inch-laptop-shell-designed-for-raspberry-pi-5-and-jetson-nano-developer-kit/)). At an inferred 10–20 W, the pack lasts about 3–6 hours. Whether the KV260's input regulator tolerates a 3S pack's 9–12.6 V range, and whether the board survives pass-through-charging glitches, is unmeasured. The 36 mm board height makes the base thick.

A custom K26 carrier is the long-term answer for both the laptop and the peripheral problem, and under the portability rule it is just another board folder. The SOM needs only 5 V at up to 4 A plus VCCO rails, and Antmicro's open 8-layer, non-HDI carrier shows the complexity ([antmicro/kria-k26-devboard](https://github.com/antmicro/kria-k26-devboard)). A laptop carrier could put the keyboard matrix, an I²C touchpad and a 4-bit SD slot directly on the 69 PL HDIO pins ([DS987](https://mm.digikey.com/Volume0/opasdata/d220001/medias/docus/7171/122_SM-K26-XCL2GC.pdf)). That removes the PS USB and SD dependency entirely, at an estimated $900–1,400 for the first unit.

## Eight phases from paper to laptop

The plan follows the repository's rule of research, then design, then verification, then implementation. Each implementation phase ends at a measurement that can change the next phase's budget. The work streams for the core and for Hydra are separate once the board contract exists, so they can run in parallel.

| Phase | Deliverables (repo location) | Exit criterion / gate |
|---|---|---|
| **0. Architecture and decisions** | Design docs in `docs/`. ISA configuration and bring-up subsets (RV64GC+Sv39 → +B/Z* → +H → +V). Board contract (streams, MMIO, IRQs, clocks, trace). Memory map that hides the split DDR. Retirement-record and event-log format (RVFI-equivalent). HLS coding standard (Comet-style II=1 loop, FSM multi-cycle units, stream-only ports, per-block IP decomposition). Pinned Vitis/Vivado release. Boot-flow spec for the KV260. Initial LUT budget with the KV260 default of a 32-bit vector datapath. | Owner signs off each decision doc; open questions listed with the experiment that answers them |
| **1. Verification foundation** | DoomV lock-step API: step, interrupt injection, load/CSR override, checkpoint load/save. C-sim harness that links the HLS top and DoomV and compares records. Bring-up builds of riscv-tests and riscv-vector-tests. riscv-dv generator configs. Cosim and Verilator regression scripts. Bug log in `agentic/bugs/`. | Harness passes against a trivial "DoomV-as-DUT" stub; same trace on repeated runs |
| **2. Board experiments (KV260)** | In `FPGA-Hardware/boards/kv260/`, each a small HLS block: (a) BOOT.BIN with FSBL on R5-0 plus bitstream, R5 parked, fan PWM driven from PL; test with and without PMUFW; (b) prove a QSPI flashing path that bypasses ImgSel/A-B; (c) HP-port bandwidth generator on 1–4 ports; (d) PL master reads and writes PS USB/SD/DP registers via S_AXI_LPD and tests PS→PL interrupts; (e) a toy RV32I pipeline in Comet style, to calibrate HLS LUT/Fmax on K26 | Go/no-go on the PS-peripheral route vs the Pmod route; measured GB/s per port; measured HLS Fmax |
| **3. Scalar core to Linux** | RV64IMAC Zicsr M/S/U, Sv39, then F/D, as separate HLS IPs. riscv-tests and arch-test in C-sim lock-step. OpenSBI platform, device tree and Buildroot Linux in C-sim, then on the board. **Ubuntu 24.04 (RVA20) boot** | Linux boot lock-stepped in C-sim end to end; synthesized LUT/Fmax measured, budget re-baselined |
| **4. RVA23 completion** | B, Zfa, Zicond, Zcb, CBO, Svnapot, Svpbmt, Svinval, Sstc, Sscofpmf, pointer masking; H with Sv39x4 (DAMO tests); V at VLEN=128 with a templated datapath width (riscv-vector-tests); riscv-formal on the generated RTL. **Ubuntu 26.04 (RVA23) boot** | Full arch-test and DAMO clean against DoomV; core LUTs ≤ the budget set in Phase 0, or a recorded decision to narrow the datapath or change board |
| **5. Hydra estimator and accelerator** (can start after Phase 2) | `Source/`: GGUF metadata parser, analytic estimator calibrated on the KV260 published points, three-tier report. HLS PE templates for Q4_0/Q8_0/Q4_K/Q6_K/F16, decode GEMV engine on N HP ports, prefill tile T, non-linear ops. Kernels checked in C-sim against llama.cpp ops. ggml backend | Estimator within a stated error of post-route results; decode efficiency measured vs roofline on the board |
| **6. Integration and laptop** | Combined bitstream; Ubuntu with the ggml backend; display (simple framebuffer via DP or Pmod fallback), keyboard and storage; enclosure, battery and power measurements in `Performance/` | tok/s and watts measured for one reference model (e.g. Qwen2.5-1.5B Q4) |
| **7. Portability proof** | A second board folder (Genesys 2 or ZCU104), optionally a custom K26 carrier | Same core and Hydra sources build unchanged for both boards |

Three gates matter most. After Phase 2, if PS peripherals cannot be driven from the PL, the KV260 laptop uses Pmod peripherals and the custom carrier moves earlier. After Phase 3, the measured HLS overhead decides whether the RVA23 core can stay near 65–80K LUTs. After Phase 4, if the core plus a minimal decoder does not fit at an acceptable Fmax, the options in order are: narrow the vector datapath, shrink TLBs and sequence rare vector ops, build a decode-only accelerator, or move to a ZCU104-class board. The board contract makes the last option a new folder, not a fork.

## Conclusion

The research turns two of the owner's constraints from liabilities into design drivers. The all-HLS rule makes the core the hardest part to build, but it also gives Ouroboros a verification path RTL projects lack: the same C++ that becomes the hardware can be lock-stepped against DoomV through a full Ubuntu boot at C-simulation speed. Phase 1 should therefore be treated as core development, not overhead. Portability, meanwhile, turns out to be the project's insurance policy. The KV260's PS-owned DDR, PS-sourced clocks, unavoidable FSBL and PS-only peripherals are confined to one folder behind a stream-and-MMIO contract. A failed LUT budget or a failed peripheral experiment then becomes a change of board rather than a redesign.

What remains unknown is narrow and testable: the real LUT cost of an RVV 1.0 unit with FP64 written in HLS; the HLS area penalty at RV64 scale; whether a riscv64 kernel can run the ZynqMP USB, SD and DP controllers with firmware dependencies removed; whether the board boots without PMUFW; and how much DDR efficiency a busy soft CPU costs the accelerator. Each maps to a specific Phase 2–4 measurement. Ouroboros is a credible proof of concept that would be first-of-kind on several counts. Its first milestone should be a modest one: Ubuntu 24.04 on a lock-stepped RV64GC core in a stock KV260.
