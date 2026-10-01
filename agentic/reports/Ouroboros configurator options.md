# Ten questions steer every Ouroboros build

The Ouroboros configurator has about **85 levers**, but they all draw on four scarce resources of the target: fabric LUTs (117,120 on the KV260's XCK26), DDR bandwidth (about 19.2 GB/s peak), DDR capacity (4 GB, shared with Ubuntu) and the high-performance memory ports into it. So nearly every lever has a recommended value that can be **computed from the `.gguf` header and the target's platform specification**. Eight trade-offs are left that only the user's goal can settle, and those, with the two inputs (model and target), make up the ten always-asked questions. The eight are: which I/O, RVA23 or less, wide vector unit or not, faster CPU or faster systolic array, big KV cache or not, decode or prefill, lots of PEs or not, and whether to rebuild OpenSBI/Linux. Each question opens with Ouroboros's recommended answer already filled in, and the estimates update live. The research shows that several of these questions are less independent than they sound, and the configurator should say so plainly. Decode speed is set by DDR bandwidth, so above a small "decode floor" of about 64–128 MACs per cycle, **more PEs and a prefill emphasis buy time-to-first-token, not tokens per second**. A faster soft CPU barely moves decode once whole layers, and sampling, run on the accelerator. It mostly buys boot time and desktop responsiveness, and the vector datapath width is its largest single cost. The remaining ~75 levers sit in an expanded view and a full, searchable view. These are two views of one flat configuration, not deeper menus. Any of them can be overridden, and a datatype override in particular replaces the default that follows the `.gguf`. To make every combination build and work, the report proposes six mechanisms. One typed constraint model whose rules come from authoritative sources (the RVA23 profile, the Linux device-tree schema, the platform's resource counts). Explanations of impossible combinations drawn from the solver's unsatisfiable core. A validation ladder that costs milliseconds to minutes before any multi-hour Vivado run. Five to ten always-green golden configurations, plus sampled combinations tested nightly through the existing `scripts/pipeline.py` stages. Content-addressed reuse of every stage's output. And ordered fallbacks that never silently change a functional choice.

Note on naming: the research notes behind this report called the configurator "Hydra". The program is Ouroboros, and that name is used throughout.

## Four scarce resources make every lever a trade-off

The flow the owner has set out (`docs/ouroboros-flow.md`) is: pick a model from `gguf/`, pick a target from `FPGAs/`, see a recommendation, walk through the choices, confirm a plan, then generate, synthesise and implement into `build/<FPGA-Name>-<DateTime>/`. Every lever in that walk spends one of four budgets, and the configurator is only honest if it shows which.

**Fabric logic.** The XCK26 has **117,120 LUTs, 234,240 FFs, 1,248 DSP48E2, 144 BRAM36 and 64 URAM** ([DS987](https://mm.digikey.com/Volume0/opasdata/d220001/medias/docus/7161/SM-K26-XCL2GI.pdf)). LUTs bind first. A full RVA23S64 core was estimated at **40–75K LUTs with a 32-bit vector datapath, 46–85K at 64 bits and 58–105K at 128 bits**. These are estimates built from Rocket, CVA6 and Rocket-with-H anchors ([Sá, Martins, Pinto](https://ar5iv.labs.arxiv.org/html/2103.14951); [Trovato et al.](https://10xengineers.ai/wp-content/uploads/Implementation-and-Performance-Evaluation-of-Bit-Manipulation_Extension-on-CVA6-RISC-V.pdf)), and the vector line may be off by 2×. Measured KV260 LLM engines run from **26K LUT / 179 DSP for a decode-only design** ([Hummingbird](https://arxiv.org/html/2507.03308v1)) to **98–102K LUTs (84–87%) for designs that also accelerate prefill and attention** ([TeLLMe v2](https://arxiv.org/html/2510.15926v2); [PD-Swap](https://arxiv.org/html/2512.11550)). The core and an ambitious accelerator therefore cannot both be large. That fact *is* the "faster CPU or faster systolic array?" question. DSPs, by contrast, are nearly free for the CPU, so most of them go to the array whatever the user answers.

**DDR bandwidth.** All 4 GB of DDR4 hangs off the PS memory controller. It is reachable from the fabric only through **four HP and two HPC ports (plus ACP, ACE and LPD)**, and one HP port measured about 3 GB/s ([UG1085](https://0x04.net/~mwk/xidocs/ug/ug1085-zynq-ultrascale-trm.pdf); [j-marjanovic.io](https://j-marjanovic.io/exploring-the-ps-pl-axi-interfaces-on-zynq-ultrascale-mpsoc.html)). Decode at batch 1 is a matrix-vector product, so **tok/s ≈ η·BW ÷ (weight bytes + context × KV bytes per token)**. Measured KV260 decoders land within about 5% of that formula at 84–94% efficiency ([Hummingbird](https://arxiv.org/html/2507.03308v1)). With Ubuntu sharing the controller, the planning efficiency is 0.6–0.8. Ports are a hard, countable budget, and this is the clearest example of a combination that can fail. Near-roofline decode needs **at least four ports**, the core needs one, the display engine one, and each enabled MIPI camera one more. On the KV260 the six HP/HPC ports are already spoken for by a four-port accelerator, the core and the display, so enabling a camera must take a port from the accelerator, share one, or be refused.

**DDR capacity.** Weights, KV cache, Linux and the framebuffer share 4 GB, in two 2 GB windows that the generated memory map has to hide or describe ([litex-boards](https://raw.githubusercontent.com/litex-hub/litex-boards/master/litex_boards/targets/xilinx_kv260.py)). KV bytes per token are exactly computable from GGUF metadata. Qwen2.5-1.5B needs **28 KiB per token at f16** ([config](https://huggingface.co/Qwen/Qwen2.5-1.5B/raw/main/config.json)). A model without grouped-query attention, such as SmolLM2-1.7B, needs **192 KiB** ([config](https://huggingface.co/HuggingFaceTB/SmolLM2-1.7B/raw/main/config.json)). That is the "big KV cache?" question, and it is also a speed question, because the whole cache is re-read for every token.

**On-chip RAM.** About 2.25 MiB of URAM and 648 KB of BRAM (estimated from the counts) have to hold the core's caches and optional L2, the accelerator's activation and accumulator tiles, stream FIFOs and the display line buffers. An L2 cache in URAM competes directly with the prefill array's activation tiles.

The fixed decisions narrow the space before any question is asked, and the configurator should show them as read-only facts, not hide them. There is **one hart**. **VLEN is 128**, and only the datapath width varies. All hardware is HLS C++. Nothing on the ARM cores runs after the generated FSBL parks. The tools are pinned to **2026.1**. The core runs on the FPGA's clock in every mode, and DoomV and Sail take their clock from the core's cycle stamps (`docs/decisions.md`). Two consequences matter for the levers. First, the "hard A53s could run the non-matmul ops" escape that published KV260 designs relied on ([Qwen2.5 on KV260](https://arxiv.org/html/2504.17376v1)) does not exist here. Offloading RMSNorm, RoPE, SiLU, attention and sampling is close to mandatory, not a preference. Second, changing a clock target never weakens lock-step, because strict lock-step follows the core's own cycle count. A clock fallback only regenerates the device tree's timebase.

## The .gguf and the target derive almost every answer

Ouroboros reads only the GGUF header, key/value metadata and tensor-info table ([gguf.md](https://github.com/ggml-org/ggml/blob/master/docs/gguf.md)) in step 1. In step 2 it reads the target's resources, memory, ports, clocks and interfaces from its platform specification (`FPGAs/<target>/target.toml` pointing at board files or an XSA). From those two inputs a fixed derivation produces the recommendation in step 3. It follows the pattern every mature FPGA generator uses: a few parallelism knobs with divisibility constraints, sized from a throughput target or a resource budget. Examples are FINN's PE/SIMD folding set from `target_fps` ([FINN](https://finn.readthedocs.io/en/latest/source_code/finn.transformation.fpgadataflow.html)), hls4ml's ReuseFactor and Precision with layer-level overrides ([hls4ml](https://fastmachinelearning.org/hls4ml/api/configuration.html)), the AMD DPU's named B512–B4096 sizes with published resource tables ([PG338](https://www.readkong.com/page/dpuczdx8g-for-zynq-ultrascale-mpsocs-product-guide-6779141)), and Intel's `c_vector`/`k_vector` with a compiler-generated default ([FPGA AI Suite](https://www.intel.com/content/www/us/en/docs/programmable/768974/2024-3/architecture-description-file-format.html)). No published recommender goes from GGUF to an FPGA configuration, so this part of Ouroboros is new.

The derivation runs in a fixed order, because later steps spend what earlier ones leave. **First, the platform's fixed costs come off the top.** These are the uncore (timer, interrupt controller, UART, display engine), the fan PWM that the bitstream must always drive, and every enabled interface at the resource estimate stored with its catalogue entry (`docs/io-catalog.md`). Disabling an interface returns its share to the array (`docs/platform-generator.md`). **Second, the core is sized from the ISA rung and vector width**, at the default rule described below. **Third, the decode floor is sized from the model.** The decode lane count is `M_dec = ceil(η·BW / (b_w·f))`, rounded up to a power of two and a multiple of the 32-weight block. Here b_w is the average streamed bytes per weight taken from the tensor-type histogram. For a Q4_K_M model at η = 0.8 and 250 MHz this gives about 102, recommended as **128 MACs/cycle**. Q8_0 gives **64**, F16 **32** (estimates). Memory ports are `ceil(η·BW / (16 B · f · 0.9))`, which is four at 250 MHz, plus two for K/V streams if attention is offloaded, a PD-Swap precedent ([PD-Swap](https://arxiv.org/html/2512.11550)). These are capped by what the platform has after the core and display take theirs. **Fourth, whatever DSP, LUT and URAM remain** up to a utilization ceiling is split by the decode-vs-prefill answer into the prefill array and its token tile. **Fifth, memory** sets the context length and KV precision from the DDR left after the OS reserve, weights and scratch.

**Datatypes follow the `.gguf` unless the user says otherwise.** The datapath is built from the set of `ggml_type`s actually present among offloaded tensors, never from the file name. llama.cpp's Q4_K_M recipe deliberately mixes types: Q6_K for `attn_v` on selected layers and for early `ffn_down`, Q5_K or Q4_K elsewhere ([llama-quant.cpp](https://raw.githubusercontent.com/ggml-org/llama.cpp/master/src/llama-quant.cpp)). So a "Q4" file needs Q4_K, Q5_K and Q6_K unpackers. FlightLLM's precedent shows one INT8 MAC core serving 2/3/4/8-bit weights behind per-type dequantizers ([FlightLLM](https://arxiv.org/html/2401.03868)). Ouroboros should therefore generate only the unpackers the histogram needs, in front of a single INT8-activation integer core with a per-block scale stage. Codebook types (IQ2/IQ3) need grid ROMs and should prompt a choice: re-quantize, CPU path, or refuse. Ternary types call for a table-lookup engine. A user override, for example FP16 everywhere for debugging, replaces the derived set and is then checked like any other choice.

| GGUF field | What it drives |
|---|---|
| tensor types + `general.file_type` | unpacker set, average bytes per weight, decode width, port count, decode tok/s |
| tensor sizes | total weights (DDR fit), streamed weights (tok/s) |
| `embedding_length` | activation tile size, norm and attention widths |
| `feed_forward_length` | largest reduction length (accumulator bits), SiLU/mul width |
| `block_count` | KV bytes per token, dispatch count (how much fusion is needed) |
| `attention.head_count`, `head_count_kv`, `key_length`, `value_length` | GQA ratio, attention engines, KV bytes per token |
| `attention.sliding_window` | KV cap per sliding-window layer |
| `context_length` | upper bound on recommended context |
| `rope.*` | RoPE unit (partial rotary, scaling type support) |
| `vocab_size` | logits buffer, sampling cost, sampler offload |
| `expert_count`, `expert_used_count` | mixture-of-experts streamed bytes, router unit |
| `general.architecture` | op set (activation, QK-norm, biases) or "unsupported architecture" |

Key spellings are confirmed against `gguf-py` ([constants.py](https://raw.githubusercontent.com/ggml-org/llama.cpp/master/gguf-py/gguf/constants.py)).

**Overrides follow llama.cpp's `--fit` semantics** ([llama.cpp server](https://raw.githubusercontent.com/ggml-org/llama.cpp/master/tools/server/README.md)). Any lever the user leaves unset is solved. Any lever the user sets is honoured, or reported as infeasible together with the rule that breaks. The saved `config.toml` stores only the deltas from the recommendation, plus pinned input hashes (`.gguf`, platform specification, tools 2026.1, generator commit). This is Buildroot's `savedefconfig` idea ([Buildroot manual](https://buildroot.org/downloads/manual/manual.html)). Changing the model later therefore re-derives every unset lever while keeping the user's explicit choices and re-checking them.

## Ten questions, asked every time, carry the user's intent

The usability evidence argues for a few high-impact questions up front, with the rest one step away. It also argues against more than two disclosure levels: "designs that go beyond 2 disclosure levels typically have low usability" ([NN/g](https://www.nngroup.com/articles/progressive-disclosure/)). The three tiers should therefore be **three views of one flat configuration**, not nested menus. The *always* view is the walk-through in step 4. The *expanded* view lists every lever with a plain-language trade-off, grouped by subsystem. The *full* view is a searchable table of every symbol, like menuconfig's `/` search. Consumer precedents ask 3–6 questions: Raspberry Pi Imager's customisation step, create-vite's prompts with a `--no-interactive` path ([Vite](https://vite.dev/guide/)), and NVIDIA App's one-click Optimize with a Performance/Balanced/Quality slider ([NVIDIA](https://www.nvidia.com/en-us/geforce/news/nvidia-app-download-and-features/)). The owner's list is longer, at eight questions plus the two inputs. It stays usable only if every question opens with Ouroboros's answer pre-selected and a reason attached, so Enter accepts it, and if the estimate panel (resources with headroom, decode and prefill tok/s, time to first token, context, RAM left for Linux, estimated watts against the 10 W budget, build time) updates on every keystroke. A good always-asked question has high impact, no universal default because it depends on the user's goal, a jargon-free answer, and is reversible only by rebuilding. Anything with a derivable answer, such as clocks or port counts, is shown as a recommendation, not asked.

The **order** matters because each answer spends a budget the next one sees. I/O comes first because it subtracts fixed costs and ports. Then ISA and vector width (the core), then the CPU-versus-array split, then KV cache, then decode-versus-prefill and PE count (the accelerator), and last the software question, which depends on all of the above. Each recurring question has an honest framing the research supports.

*"Which I/O do you want?"* lists every interface the platform specification shows, each a switch with its cost. On the KV260 the display (HDMI/DP through the PS DisplayPort controller), USB, Ethernet and SD are PS hard peripherals. They cost only generated glue, firmware and, for video, the display engine and a memory port. Cameras and Pmod are fabric logic and cost LUTs and a port each (`docs/platform-generator.md`). The recommendation is the laptop set: display, USB, SD and Ethernet on; cameras, AP1302 and Pmod off. This mirrors Kconfig's rule that options default off unless they are universal infrastructure ([Kconfig](https://www.kernel.org/doc/html/latest/kbuild/kconfig-language.html)). The answer should show the LUT and port delta per interface, not a blanket "frees LUTs" claim, because disabling PS USB frees almost nothing.

*"Is RVA23 good, or do you want less?"* offers a ladder: RV64GC/RVA20, RVA22S64, RVA23S64. The project's target is RVA23S64. Ubuntu 25.10 and 26.04 LTS require it ([Phoronix](https://www.phoronix.com/news/Ubuntu-25.10-To-Require-RVA23); [Canonical](https://ubuntu.com/blog/canonical-and-ubuntu-risc-v-a-2025-retro-and-looking-forward-to-2026)). Ubuntu 24.04 LTS, Debian 13 and Fedora still run on RV64GC ([RISCstar](https://riscstar.com/blog/rva23-from-ratification-to-real-world-readiness/)). Less than RVA23 is a legitimate bring-up and area-saving choice, and it removes V, H and the rest of the mandatory tail ([RVA23 profile](https://github.com/riscv/riscv-profiles/blob/main/src/rva23-profile.adoc)). The question should show a distro compatibility badge per rung and grey out Ubuntu ≥ 25.10 below RVA23. Optional RVA23 extensions belong in the expanded view.

*"Wide vector unit or not?"* sets the vector datapath width (32, 64 or 128 bits at VLEN = 128). That is the largest single LUT lever in the system, at roughly 12–20K, 18–30K and 30–50K LUTs. A narrow datapath runs each LMUL=1 operation in VLEN/DLEN beats ([Saturn](https://arxiv.org/html/2412.00997)). Software is unaffected, because distro binaries are vector-length agnostic. The KV260 recommendation is **32 bits**, with wider widths recommended automatically when the target has more LUTs.

*"Faster CPU or faster systolic array?"* is a single slider in NVIDIA's style with named stops (Linux-first, Balanced, LLM-first). It moves the core tier (FPU style, caches, L2, branch prediction, mul/div speed, and vector width if not already answered) against the accelerator's LUT budget. The honest answer comes from a per-token time model, `t_tok = max(t_mem, t_compute) + t_cpu + t_dispatch`, and it has two regimes (estimates). If the soft CPU does sampling over a 151,936-entry vocabulary at about 100 MHz, that alone costs 15–60 ms per token. Running RMSNorm, RoPE and SiLU in software costs about 47 ms, and per-op dispatch without fused layer commands 3–17 ms. Any of these would cap tok/s below the 14–18 tok/s bandwidth roofline of a 1.5B Q4 model. Once whole layers and sampling run on the accelerator, a faster CPU barely changes tok/s. It buys boot time, compile speed and desktop responsiveness, and the slider's label should say exactly that. The configurator enforces a minimum offload level for each CPU tier, so a "Linux-first" answer can never quietly cripple decode.

*"Big KV cache or not?"* is asked as a maximum context length, with a live DDR bar split into OS, weights, KV and scratch. The recommendation is `min(GGUF context_length, what fits in DDR, a speed cap)`. The speed cap is the context at which decode slows by a chosen fraction. For Qwen2.5-1.5B Q4 a 20% slowdown at a full window allows about 7.8K tokens at f16 KV or about 15K at q8_0 (estimates). The precision sub-choice uses Ollama's wording: f16, q8_0 "approximately 1/2 the memory … very small loss", q4_0 "approximately 1/4 … small-medium loss" ([Ollama FAQ](https://raw.githubusercontent.com/ollama/ollama/main/docs/faq.mdx)). It also carries llama.cpp's own rule: a **quantized V cache requires flash attention** ([llama-context.cpp](https://raw.githubusercontent.com/ggml-org/llama.cpp/master/src/llama-context.cpp)). So choosing q8_0 V forces the accelerator's blockwise online-softmax attention path, and turning that path off greys out quantized V. Models whose GGUF shows n_kv = n_h should be flagged as KV-heavy.

*"Decode or prefill?"* is a prefill-emphasis slider p from 0 to 100. It sets the fraction of the post-decode-floor DSP/LUT budget given to the prefill array, and the token tile `T = next_pow2(max(T_min, p·T_max))`. At p = 0 the engine is GEMV-only. At p ≥ 20 it becomes GEMV plus a weight-stationary array sharing the dequant front end. The named stops are Chat (15), Balanced (50) and Long prompts/RAG (85). The panel must show that decode tok/s stays flat across the slider while prefill tok/s rises: for Qwen2.5-1.5B Q4 at η = 0.7, decode is about 14 tok/s at every position, while time to first token for a 512-token prompt falls from about 36 s at p = 0 to about 5 s at p = 50 and about 2.6 s at p = 100 (uncalibrated estimates). This message is the reason to ask the question at all. Prefill buys time to first token, not tokens per second. PD-Swap's dynamic reconfiguration between phase-specific engines (about 45 ms per swap on the KV260, mostly hidden) belongs in the full view as an advanced topology ([PD-Swap](https://arxiv.org/html/2512.11550)).

*"Lots of PE units or not?"* is related but distinct. It sets the utilization ceiling the accelerator may grow to: decode floor only, moderate (about 70% LUT), or fill (about 85%). This is the honest place to state the costs of a full chip. Above about 80% utilization, place-and-route time and timing-closure difficulty climb sharply ([edaboard](https://www.edaboard.com/threads/vivado-taking-a-long-time-to-run-synthesis-implementation.384348/), a low-authority source). Power also rises against the KV260's 10 W application budget ([UG1089](https://docs.xibif.ch/_downloads/480ec1217d1ac2bd520e695148cfe86f/KV260_Userguide.pdf)). Showing "PEs beyond this point do not help decode" as a marker on the scale keeps the answer honest.

*"Should we rebuild OpenSBI/Linux for your configuration, or have you already done that?"* can be answered precisely, because most hardware changes need only a regenerated device tree. Linux detects V, Zba/Zbb, Zacas, Zabha, Zawrs, Zicbom/Zicboz/Zicbop, Svnapot, Svpbmt and pointer masking at boot from `riscv,isa-extensions` and patches itself ([Linux arch/riscv/Kconfig](https://github.com/torvalds/linux/blob/master/arch/riscv/Kconfig); [extensions.yaml](https://www.kernel.org/doc/Documentation/devicetree/bindings/riscv/extensions.yaml)). OpenSBI's generic platform with FW_DYNAMIC is driven entirely by the device tree. Ouroboros always generates the device tree and firmware platform, because they are board outputs (`docs/platform-generator.md`). The question is therefore about the kernel, OpenSBI binary and rootfs, and the answer comes from a rebuild matrix. Toggling optional extensions, cache or predictor sizes and the clock changes only the device tree. Changing the memory map forces new OpenSBI jump addresses unless FW_DYNAMIC is used. Dropping below RVA23 forces a switch of distro. Dropping the FPU forces a custom Buildroot image, since every distro uses the lp64d ABI. The question's choices are "build for me" (default), "reuse my last build" (accepted only if the software-relevant subset of the configuration hashes the same, or the changes are device-tree-only) and "use my images at this path". The last choice is then checked: the generated device tree against the image's expectations, the kernel `.config` for required symbols after `make olddefconfig` (which silently drops unmet ones), and OpenSBI's firmware type and addresses against the memory map.

## Combinations stay buildable through a constraint model, a validation ladder and golden configurations

Making every combination of about 85 levers build and work does not mean testing every combination, and no real project does. CVA6 defines a short list of "viable IP configurations" as CI targets ([CVA6](https://cva6.readthedocs.io/en/latest/02_cva6_requirements/cva6_requirements_specification.html)). Chipyard keeps named example configurations and tests prebuilt simulators ([Chipyard](https://github.com/ucb-bar/chipyard/blob/main/docs/Simulation/Software-RTL-Simulation.rst)). Linux's 0-day robot is 63% `randconfig` builds ([krepair, arXiv:2404.17966](https://arxiv.org/html/2404.17966v1)). The guarantee instead rests on five layers. Each catches what the one before cannot, and each is cheaper than the one after.

**Layer 1: one typed constraint model, not Kconfig.** Kconfig's `select` "will force a symbol to a value without visiting the dependencies" ([Kconfig](https://www.kernel.org/doc/html/latest/kbuild/kconfig-language.html)). Its `imply` can leave a direct dependency unmet without a warning ([linux-kbuild](https://www.spinics.net/lists/linux-kbuild/msg24741.html)). Both are traps for hardware options. Ouroboros should model its options in CP-SAT (or Z3): booleans for extensions and interfaces, bounded integers for widths, sizes, counts and clocks, and linear constraints for every budget. Every rule carries its own enforcement literal and message. When the user's choices are infeasible, the solver runs with those choices as assumptions and returns `sufficient_assumptions_for_infeasibility` ([CP-SAT Primer](https://d-krupke.github.io/cpsat-primer/parameters.html)). That core becomes a sentence such as "q4_0 V cache is impossible because flash-attention path is off". Assumptions and objectives conflict in CP-SAT, so explanation needs a separate feasibility-only solve. The rules come from authoritative data, not hand transcription. ISA implications come from the RVA23 profile or the RISC-V Unified DB ([UDB](https://riscv-software-src.github.io/riscv-unified-db/pdfs/RVA23ProfileRelease.pdf)), which says V needs F, D and Zvl128b, and RVA23S64 needs Sha (H). Extension dependencies come from the kernel's device-tree schema ([extensions.yaml](https://www.kernel.org/doc/Documentation/devicetree/bindings/riscv/extensions.yaml)): D ⇒ F, Zcb ⇒ Zca, Zve64d ⇒ D. Budgets come from the platform's part data plus the catalogue's measured per-interface costs. Generator rules sit alongside them: datapath width ≤ VLEN (Ara silently aliased registers until it added this check, [Ara PR #484](https://github.com/pulp-platform/ara/pull/484)), return-address stack and gshare require a BTB ([VexiiRiscv](https://spinalhdl.github.io/VexiiRiscv-RTD/master/VexiiRiscv/HowToUse/index.html)), PMP entries ≥ OpenSBI's needs, H with Sv48 ⇒ Sv48x4, ports ≤ platform ports, reduction lanes a multiple of 32 (FINN's `MH % PE == 0` analogue, [FINN](https://finn.readthedocs.io/en/latest/internals.html)), and "an interface exists on this platform". The same model emits every output of one build: the HLS parameter header, the device tree's `riscv,isa-extensions`, the OpenSBI and kernel config fragments, the distro badge, and the `-march` string and reference configuration for verification. That last output closes a gap: `scripts/pipeline.toml` today hard-codes one full RVA23-plus `march` for every suite. That is correct for one target but wrong for any narrower configuration.

**Layer 2: verification must be configured by the same model.** Strict lock-step needs DoomV, and Sail behind it, to model the same machine as the core. They need the same extension set, the same interrupt controller (PLIC or AIA, still open in `docs/board-contract.md`) and the same devices. So the constraint model must also reject any configuration DoomV cannot represent, and generate DoomV's `-march` and Sail's configuration from the build's own choices instead of `rva23s64.json` alone. This is the one place where "every option must work" depends on another repository. Each new ISA lever needs a matching DoomV/Sail capability, pinned in its own commit.

**Layer 3: a validation ladder before any long build.** FINN annotates resources at three fidelities: analytic estimate, HLS report and post-synthesis ([FINN](https://finn.readthedocs.io/en/latest/source_code/finn.transformation.fpgadataflow.html)). It also refuses to build until folding is set ([FINN PR #1665](https://github.com/Xilinx/finn/pull/1665)). Ouroboros should gate each rung on the one before. The ladder maps onto the existing pipeline stages, plus three new ones.

| Rung | Catches | Cost | `scripts/pipeline.py` stage |
|---|---|---|---|
| Constraint check | illegal combinations, budget overruns, unrepresentable verification | ms | new `validate` (the plan screen runs it on every keystroke) |
| Analytic estimate | resources, tok/s, context, watts, build time; fitted from past runs | ms | new `plan`, reading `Performance/` history |
| Native compile of every generated top with `static_assert` contracts at stream boundaries (datatype in supported set, widths divide) | composition and interface mismatches | seconds | part of `csim` |
| C simulation, lock-stepped against DoomV, and accelerator kernels checked against llama.cpp ops | functional bugs in this combination | minutes | `csim` + `accuracy` |
| HLS synthesis per component | per-component resources and II | tens of minutes | `hls` |
| RTL co-simulation of short directed tests | scheduling, stream depths, free-running behaviour | minutes–hours | `cosim` |
| Whole-system block design, synthesis, place and route | fit and timing *together* | hours | new `system-impl` (today's `impl` is per-component out-of-context) |
| Boot and model run | Linux boots; logits match llama.cpp within tolerance | hours | `accuracy` (boot suites) + new `llm-accuracy` |

Three changes to the pipeline follow. First, the run key that `new_run` hashes for regression comparison should include the configuration's canonical hash. Otherwise two different configurations of the same components are compared as if they were one, and a deliberate change reads as a regression. Second, the suites' `march` should come from the configuration. Third, a numerical-accuracy stage should run a fixed prompt set and compare logits or perplexity with llama.cpp's CPU reference. Datatype, activation-precision and KV-precision overrides can only be judged that way, since lock-step proves the core, not the arithmetic of the accelerator.

**Layer 4: golden configurations plus sampled combinations.** The evidence on configurable software is consistent. Of 135 known configuration faults, pairwise sampling found 125 and 4-wise found 132. The cheap heuristics most-enabled/most-disabled and one-enabled/one-disabled found 105–108 with fewer than two samples per file, and were the most efficient per sample ([Medeiros et al., ICSE 2016](https://arxiv.org/pdf/1602.02052)). NIST's data put 97% of failures at one- or two-way interactions ([Kuhn](https://csrc.nist.gov/CSRC/media/Presentations/Combinatorial-Testing-Rationale-and-Impact-Presen/images-media/kuhn-icst-14.pdf)). No study measures interaction degree in hardware generators, so these figures are a prior, not a guarantee. The regime that follows has three cadences. **5–10 golden configurations** are fully implemented, boot Linux and pass lock-step on every release, and they are exactly the presets the configurator offers. Examples: KV260 RV64GC-minimal, KV260 RVA23-minimum with decode-first accelerator, KV260 RVA23 balanced, KV260 RVA23 long-prompt, and a no-PS board (MIG stopgap). **Every commit** runs most-enabled, most-disabled and one-on/one-off samples through rungs 1–4. **Every night** a constrained pairwise covering array from PICT runs through C simulation and lock-step. PICT's sub-models allow higher strength inside tightly coupled groups such as ISA × vector width × FPU ([covertable/PICT](https://github.com/walkframe/covertable); [NIST tables](https://www.nist.gov/itl/math/nist-covering-array-tables)). One or two of those configurations, plus one uniform random valid sample, rotate through full system implementation each night. When a commit touches the generator for option X, the krepair idea applies. Instead of hoping a random configuration hits the change, Ouroboros tests the nearest golden configuration with X enabled. In Linux, random configurations covered only 29% of patches, against 98.5% for repaired ones ([krepair](https://arxiv.org/html/2404.17966v1)). The UI should mark configurations outside the golden set as "best effort", as CVA6 does.

**Layer 5: content-addressed reuse and ordered fallbacks.** Each stage's output should be keyed by the hash of the configuration *subset* it depends on, plus tool version and generator commit. A change to Linux options then never re-synthesizes the systolic array, and a change of I/O re-runs only the block design and implementation. This also avoids Buildroot's admitted gap, which is that it "does not attempt to detect what parts of the system should be rebuilt" ([Buildroot manual](https://buildroot.org/downloads/manual/manual.html)). The per-build folders under `build/` hold the outputs; a cache index maps hashes to them. When fit or timing fails, recovery should re-solve the constraint model, not retry ad hoc. Ouroboros adds the observed failure as a learned constraint, for example "128-lane prefill at 300 MHz fails on xck26", recalibrates the estimator, and asks for the nearest feasible configuration. It walks a fixed order: a Vivado strategy sweep at the same configuration (defaults first, then Performance_Explore, per [UG904](https://static.eetrend.com/files/2021-09/wen_zhang_/100553629-220271-ug904-vivado-implementation.pdf)), then fewer PEs, then a lower clock, then smaller caches or KV, then ask the user. Functional choices (ISA, datatypes, I/O, distro) never change silently, and every substitution is reported ("requested 1,024 MACs, built 768 because …"). Vivado has no true random seed any more ([Plunify](https://support.plunify.com/en/2017/01/11/who-says-you-cant-use-random-seeds-in-vivado/)). Reproducibility therefore means recording strategy, directives and all input hashes in the build folder's `config.toml`.

## The terminal flow should plan before it builds

The owner's eight-step flow already fits the precedents. The research adds four specifics. Step 5's plan screen should behave like `terraform plan`, which shows the full diff and changes nothing ([Terraform](https://developer.hashicorp.com/terraform/cli/commands/plan)). Its three columns are field, recommended and yours. Overrides are highlighted, each line has a one-sentence reason (for example "128 decode lanes because Q4_K_M streams 0.6 B/weight and 13.4 GB/s is available"), and every estimate is labelled with its provenance: analytic, HLS report, or measured on a previous build of this configuration. Compatibility verdicts should follow PCPartPicker's error/note split, but with explicit headroom, avoiding its zero-buffer flaw ([cgdirector](https://www.cgdirector.com/pcpartpicker-compatibility-warnings-explained/)). Every prompt needs a flag or `config.toml` equivalent, so a saved configuration replays with no questions. Ouroboros should fail rather than prompt when input is not a TTY ([clig.dev](https://clig.dev/)). In step 7, a failure should name the stage and the choice most likely responsible, for example "accelerator clock 300 MHz: try 250 MHz or fewer PEs". It should show the relevant log lines and suggest the next command. Writing BOOT.BIN to QSPI should require typed confirmation, because the KV260's stock A/B images and recovery tool are what a mistake falls back on ([UG1089](https://docs.xibif.ch/_downloads/480ec1217d1ac2bd520e695148cfe86f/KV260_Userguide.pdf)).

## Conclusion

The configurator's hardest job is honesty about coupling, more than breadth. Three of the owner's questions ("lots of PEs", "decode or prefill", "faster CPU or array") look independent but share one bandwidth roofline, so the configurator's main value is showing, live, which answer actually moves tokens per second and which moves only time to first token, boot time or build time. Several estimates here are still uncalibrated: the vector unit's LUT cost, prefill throughput on a 2-D array, soft-CPU sampling and dispatch latency, the OS memory reserve, and the per-interface resource costs. The configurator's first release should therefore treat its analytic model as a prior that every `pipeline.py` run corrects, with each build's outcome feeding the estimator. Two dependencies decide whether "every option works" is achievable. Every ISA lever must be expressible in DoomV and Sail before it is offered. The port budget, not LUTs, is the KV260 constraint most likely to refuse a reasonable-looking I/O choice, so the per-interface port and bandwidth costs should be measured in Phase 2, alongside LUTs.

## Always-asked questions

Asked in this order in step 4. Each opens with the recommendation selected, and Enter accepts it.

| # | Question, as shown | Choices | Recommended answer (rule) | Sets | Hidden or changed when |
|---|---|---|---|---|---|
| 0a | Which model? | `.gguf` files in `gguf/`, or a path | the only file, else ask | every model-derived lever | never |
| 0b | Which FPGA? | targets in `FPGAs/` | the attached, identified board; else the default target | every platform-derived lever | never |
| 1 | Which I/O do you want? | every interface the platform shows, each on/off, with LUT, port and bandwidth cost | laptop set: display, USB, SD, Ethernet on; cameras, ISP, Pmod, GPIO off | IO-* | interfaces the platform lacks are not listed; fan and clocks shown as always on |
| 2 | Is RVA23 good, or do you want less? | RVA23S64 / RVA22S64 / RV64GC (RVA20) | RVA23S64; distro badge per rung | ISA-1, SW-2 | never |
| 3 | Wide vector unit or not? | 32 / 64 / 128-bit datapath (VLEN 128) | largest width whose core estimate leaves the decode floor plus 15% LUT headroom; KV260: 32 | CORE-1 | hidden if no V (below RVA23) |
| 4 | Faster CPU or faster systolic array? | Linux-first / Balanced / LLM-first slider | Balanced; LLM-first if the model is ≥ 1B parameters and LUTs are tight | CORE-3…10, ACC-11 minimum | never |
| 5 | Big KV cache or not? | context length (2K / 4K / 8K / max that fits) and KV precision | min(GGUF context, DDR fit, 20%-slowdown cap); q8_0 when the flash path is on | MEM-1, MEM-2 | never |
| 6 | Decode or prefill? | Chat (15) / Balanced (50) / Long prompts (85), or 0–100 | Chat; Balanced if the target has spare DSP beyond the decode floor | ACC-7, ACC-9, ACC-10 | never |
| 7 | Lots of PE units or not? | decode floor only / moderate (~70% LUT) / fill (~85% LUT) | moderate; "PEs past this point do not raise decode" marked | ACC-8, PLAT-4 | never |
| 8 | Rebuild OpenSBI/Linux for this configuration, or have you already? | build for me / reuse last build / my images at a path | build for me; "reuse" preselected when only device-tree-level changes since the last build | SW-1 | never; device tree and firmware platform are always generated |

## Proposed option catalogue

Tier **A** = always asked (as above). Tier **E** = expanded view, every lever with a trade-off line, grouped by subsystem. Tier **F** = full view, searchable. **Fixed** = shown read-only as a project decision. Every A and E lever also appears in F. "Rule" is the default Ouroboros derives. Every lever is overridable unless Fixed, and an override is checked by the constraint model. Estimates are to be replaced by measured costs as Phase 2 produces them.

### Fixed by project decisions

| ID | Item | Value | Source |
|---|---|---|---|
| FX-1 | Harts | 1 | AGENTS.md |
| FX-2 | VLEN | 128 bits | AGENTS.md |
| FX-3 | Hardware language | C++ for Vitis HLS only; riscv-formal wrapper for testing only | decisions 2026-09-30 |
| FX-4 | IP | Ouroboros's own; vendor soft IP only as a listed stopgap (MIG); licensed IP never | decisions 2026-10-01 |
| FX-5 | Tools | Vivado/Vitis 2026.1; builds refuse any other | hls-coding-standard.md |
| FX-6 | Hard ARM cores | generated FSBL only, then parked | AGENTS.md |
| FX-7 | Core clock | the FPGA's clock in every mode; DoomV/Sail driven by the core's cycle stamps | decisions 2026-10-01 |
| FX-8 | Always generated | fan PWM, clocks and reset, uncore (timer, interrupt controller, UART, bridge) | platform-generator.md |

### Inputs and platform

| ID | Lever | Tier | Options | Rule | Depends on / constrains |
|---|---|---|---|---|---|
| PLAT-1 | Target | A | `FPGAs/*` | attached board, else default | any AMD part in 2026.1; supplies all budgets |
| PLAT-2 | Model | A | `.gguf` | only file, else ask | header only; supplies all model rules |
| PLAT-3 | Start from preset | E | golden presets for this target | "Recommended for this model" | presets are the always-green set |
| PLAT-4 | Utilization ceiling | E (set by Q7) | 60–90% per resource | LUT 85% hard, warn 80%; others 90% | caps ACC-8; fallback order |
| PLAT-5 | DDR efficiency η for estimates | F | 0.5–0.95 | 0.7 until measured | all tok/s estimates |
| PLAT-6 | Allow listed stopgap IP | F | yes / no | yes, reported | only meaningful on PS-less boards (MIG) |

### I/O (one row per interface the platform shows)

| ID | Lever | Tier | Options | Rule | Depends on / constrains |
|---|---|---|---|---|---|
| IO-1 | Display output, per connector | A | on / off | on (first connector) | needs display engine + 1 memory port; KV260: PS DP controller live input |
| IO-2 | Display mode | E | resolutions the platform's pixel clocks allow (KV260: 1024×768, 720p, 1080p) | 1080p60 if supported, else highest | bandwidth ≈ w·h·bpp·fps (1080p60 32 bpp ≈ 0.5 GB/s, est.) |
| IO-3 | Framebuffer depth | F | 16 / 32 bpp | 32 | IO-2 bandwidth |
| IO-4 | USB | A | on / off | on | PS glue; needs interrupt route or polling (IO-14) |
| IO-5 | Ethernet | A | on / off | on | PS glue |
| IO-6 | SD | A | on / off | on | required if BOOT-1 = SD or rootfs on SD |
| IO-7 | QSPI as a Linux device | E | on / off | off | QSPI holds boot image regardless |
| IO-8 | MIPI CSI-2 camera, per connector | A | on / off | off | LUTs + 1 memory port each; port budget |
| IO-9 | AP1302 ISP set-up | E | on / off | on iff its camera path is on | depends on IO-8 (IAS0) |
| IO-10 | Pmod | A | off / GPIO / UART / USB-HID / SPI-SD | off | fabric pins; HID and SPI-SD are fallbacks for PS USB/SD |
| IO-11 | GPIO, LEDs | E | on / off | off | MMIO window |
| IO-12 | Fan control | E | constant / temperature-controlled | temperature-controlled if IO-13 on | fan PWM always generated (FX-8) |
| IO-13 | SYSMON temperature, power monitor | E | on / off | on | I2C for VCC_SOM monitor |
| IO-14 | PS peripheral interrupts | F | interrupts / polling | interrupts if verified in Phase 2, else polling | interrupt controller (ISA-4) |
| IO-15 | Console UART route | F | platform's USB-UART / Pmod | platform's | uncore UART always present |

### ISA

| ID | Lever | Tier | Options | Rule | Depends on / constrains |
|---|---|---|---|---|---|
| ISA-1 | Profile rung | A | RVA23S64 / RVA22S64 / RV64GC | RVA23S64 | RVA23 ⇒ V, Sha(H), Sstc, Sscofpmf, Svnapot, Zicond, Zfa, Zcb, Zimop/Zcmop, Zawrs, Supm/Ssnpm, Zvbb, Zvkt, Zvfhmin, Zicbo*; distro (SW-2); DoomV/Sail config |
| ISA-2 | Zacas, Zabha | E | on / off | on if LUT headroom after ACC floor, else off | ⇒ A |
| ISA-3 | Zicfilp, Zicfiss (CFI) | E | on / off | off | Zicfiss ⇒ A + Zimop; kernel/glibc CFI support |
| ISA-4 | Interrupt controller | F | PLIC / AIA | whichever DoomV's strict platform models (open decision) | strict lock-step; device tree |
| ISA-5 | Zfh, Zvfh | E | on / off | off on KV260; on if LUT headroom | Zvfh ⇒ Zvfhmin + Zfhmin; needs V |
| ISA-6 | Zfbfmin, Zvfbfmin, Zvfbfwma | E | on / off | off on KV260 | needs F / V |
| ISA-7 | Ziccamoc, Zama16b | F | on / off | on if A path supports it | ⇒ A |
| ISA-8 | Zbc, Zvbc | F | on / off | off | Zvbc ⇒ V |
| ISA-9 | Zvkng, Zvksg | F | on / off | off | ⇒ V; large LUT cost |
| ISA-10 | Zkr | F | on / off | off | needs an on-chip entropy source; portability |
| ISA-11 | Sv48, Sv57 | F | on / off | off | with H ⇒ Sv48x4 / Sv57x4; PA width |
| ISA-12 | Svadu, Sdtrig, Ssstrict, Svvptc, Sspm | F | each on / off | off | Svadu ⇒ page-table walker writes |
| ISA-13 | Emulate in M-mode (where the spec allows, e.g. misaligned) | F | per item | hardware | custom OpenSBI ⇒ SW-1 rebuild |

### Core microarchitecture

| ID | Lever | Tier | Options | Rule | Depends on / constrains |
|---|---|---|---|---|---|
| CORE-1 | Vector datapath width | A | 32 / 64 / 128 | see Q3 | ≤ VLEN; needs V |
| CORE-2 | Core clock | E | platform clock choices (KV260 ~100 MHz planning) | highest the estimator closes timing at, rounded down | device-tree timebase; FX-7 |
| CORE-3 | Scalar FPU style | E | pipelined FMA / shared with vector / iterative | shared on KV260 | V ⇒ D; no FPU ⇒ not RVA23, no distro |
| CORE-4 | FP div/sqrt | F | radix-2 / radix-4 | radix-2 | — |
| CORE-5 | Multiplier, divider | E | 1-cycle DSP / pipelined / iterative; radix-2 / radix-4 / early-out | pipelined; radix-2 | DSP |
| CORE-6 | Vector slow sequencers (div/sqrt, permutes, indexed/segment, reductions, widening) | F | fast / serial, per class | serial | LUT |
| CORE-7 | Branch prediction | E | none / static / BHT+BTB / +RAS / +gshare; sizes in F | BHT 128 + BTB 32 + RAS 2 | RAS, gshare ⇒ BTB |
| CORE-8 | L1 I$, D$ size | E | 4–64 KiB; ways, line, write policy in F | 16 / 16 KiB | BRAM |
| CORE-9 | L2 | E | none / 64–512 KiB URAM | none on KV260 | URAM shared with ACC tiles |
| CORE-10 | TLBs | F | I/D 4–64 entries; L2 TLB 0–1024; G-stage TLB | 16 / 16, no L2 TLB | H ⇒ two-stage walk |
| CORE-11 | PMP entries | F | 0 / 8 / 16 / 64 | 8 | ≥ OpenSBI's need |
| CORE-12 | HPM counters | F | 0–29 | 4 | Sscofpmf rules on each implemented counter |
| CORE-13 | Pipeline depth | F | 3–7 | from clock target | Fmax vs stalls |
| CORE-14 | Physical address width | F | 32–56 | smallest that covers the platform's memory and MMIO windows | device tree |
| CORE-15 | Misaligned access | F | hardware / trap to SBI | hardware | trap ⇒ custom OpenSBI |
| CORE-16 | Board trace: hash interval N | F | 2^10–2^24 | 2^16 | lockstep.md board level |

### Accelerator

| ID | Lever | Tier | Options | Rule | Depends on / constrains |
|---|---|---|---|---|---|
| ACC-1 | Weight datatypes (unpackers) | E | follow `.gguf` / user list | types in the offloaded-tensor histogram | each type needs an unpacker; IQ/ternary per ACC-3 |
| ACC-2 | Activation precision | E | INT8 / FP16 / INT4 | INT8 | FP16 for accuracy; INT4 needs re-quantization |
| ACC-3 | Unsupported type handling | E | re-quantize / CPU path / refuse | ask when present | ACC-1 |
| ACC-4 | Decode lanes M_dec | F | 16–256 | `ceil(η·BW/(b_w·f))` → pow2, multiple of 32 | above it decode does not improve |
| ACC-5 | Decode MACs in DSP or LUT | F | DSP-packed / LUT | LUT if LUT headroom > 1.5·M_dec·30 | prefill always DSP |
| ACC-6 | Memory ports (weights, K/V) | F | 1–platform max | 4 + 2 if attention offloaded, capped by free ports | IO-1, IO-8, core take ports first |
| ACC-7 | Engine topology | E | GEMV only / GEMV + array / reconfigurable shape / DPR swap | from Q6: p = 0 → GEMV only; p ≥ 20 → GEMV + array | DPR is advanced; PCAP from fabric unproven |
| ACC-8 | Prefill array size and shape | A (Q7) / F (rows × cols) | 0 – DSP left; rows = 32k | fill to ceiling set by Q7 | DSP + LUT budget |
| ACC-9 | Prefill emphasis p | A (Q6) | 0–100 | 15 | ACC-7, ACC-10 |
| ACC-10 | Token tile T | F | 8–512 | next_pow2(max(T_min, p·T_max)) | activation buffer URAM; llama.cpp ubatch |
| ACC-11 | Offload level | E | 0 MUL_MAT / 1 + norm, RoPE, SiLU / 2 + attention, KV append / 3 fused layer / 4 + lm_head, sampling | 3, or 4 when vocab sampling > 20% of t_mem | minimum rises as CPU tier falls |
| ACC-12 | Attention engines | F | 1 – n_kv | 1 decode-first; 2 if p ≥ 50 | GQA ratio |
| ACC-13 | Accumulator format | F | 24-bit block + FP32 / fixed32 | FP32 cross-block | `feed_forward_length` |
| ACC-14 | On-chip buffer allocation | F | URAM/BRAM split | URAM for activation and accumulators, BRAM for FIFOs; ≥ 20% left for core caches | CORE-8, CORE-9 |
| ACC-15 | Accelerator clock | E | 150–300 MHz | 250 | separate domain (board contract) |
| ACC-16 | Mixture-of-experts router | F | on / off | on iff `expert_count` > 0 | MXFP4 unpacker if present |

### KV cache and memory

| ID | Lever | Tier | Options | Rule | Depends on / constrains |
|---|---|---|---|---|---|
| MEM-1 | Context length | A (Q5) | 256-token steps up to GGUF `context_length` | min(GGUF, DDR fit, speed cap) | KV bytes/token from GGUF |
| MEM-2 | KV precision K / V | A (Q5, sub-choice) | f16 / q8_0 / q4_0 | q8_0 if MEM-3 on, else f16 | quantized V ⇒ MEM-3 |
| MEM-3 | Flash-style attention path | F | on / off | on when ACC-11 ≥ 2 | required for quantized V |
| MEM-4 | Full sliding-window cache | F | on / off | off | only for SWA models |
| MEM-5 | OS memory reserve | E | 0.5–3 GiB | 1.25 GiB until measured | DDR fit |
| MEM-6 | Accelerator carve-out | F | reserved-memory / CMA | reserved-memory for weights, CMA for shared buffers | weights physically contiguous |
| MEM-7 | DDR split windows | F | remap to one range / describe both in the device tree | describe in the device tree | board contract |

### Software, boot and deployment

| ID | Lever | Tier | Options | Rule | Depends on / constrains |
|---|---|---|---|---|---|
| SW-1 | OpenSBI/Linux source | A (Q8) | build / reuse last / user images | build; reuse if the software-subset hash matches | rebuild matrix; user images validated |
| SW-2 | Distro | E | Ubuntu 26.04 / Ubuntu 24.04 / Debian 13 / Fedora / Buildroot | newest the ISA rung allows | Ubuntu ≥ 25.10 ⇒ RVA23S64; no FPU ⇒ Buildroot |
| SW-3 | Boot chain | E | OpenSBI → U-Boot → extlinux / OpenSBI → Linux | U-Boot (apt kernel updates work) | FW_DYNAMIC preferred |
| SW-4 | Kernel options (KVM, V default-on, CFI) | F | per symbol | derived from ISA | checked after `olddefconfig` |
| SW-5 | Kernel command line | F | console, carve-outs | derived | IO-15, MEM-6 |
| SW-6 | llama.cpp defaults | F | ctx, cache types, ubatch | MEM-1, MEM-2, ubatch = ACC-10 | ggml backend |
| BOOT-1 | Boot medium | E | SD / QSPI / JTAG (development) | SD, with QSPI holding BOOT.BIN | QSPI writes need typed confirmation |
| BOOT-2 | Flash after build | E | no / yes | no | BOOT-1 |

### Build and verification

| ID | Lever | Tier | Options | Rule | Depends on / constrains |
|---|---|---|---|---|---|
| BLD-1 | Verification before bitstream | E | validate only / + C-sim lock-step / + co-sim / + boot in C-sim | + C-sim lock-step + co-sim of changed components | pipeline stages |
| BLD-2 | Implementation strategy | E | default / Performance_Explore / sweep | default, sweep on failure | names to verify for 2026.1 |
| BLD-3 | Fallback policy | E | auto (non-functional levers only, reported) / ask / never | auto | order: strategy → PEs → clock → caches/KV → ask |
| BLD-4 | Parallel jobs | F | 1 – cores | cores / 2 | pipeline `--jobs` |
| BLD-5 | Stage reuse | F | on / off | on (content-addressed) | config-subset hashes |
| BLD-6 | Placement exploration | F | directive list | none | Vivado has no true seed |
| BLD-7 | LLM accuracy check | E | off / logits vs llama.cpp on fixed prompts | on when ACC-1/2 or MEM-2 differ from defaults | new `llm-accuracy` stage |
