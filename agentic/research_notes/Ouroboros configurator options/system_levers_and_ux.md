# Ouroboros configurator: system-level levers and configurator UX

Scope: (a) system-level knobs of a soft-RVA23-core + systolic-LLM-accelerator FPGA computer (first target AMD Kria KV260), beyond the core/accelerator microarchitecture itself; (b) how established configurators tier options, phrase trade-off questions, present recommendations, and run long builds in a terminal. Research date: 2026-10-01. "Evidence" = cited finding; "Inference" = my reasoning from the evidence, not sourced.

## Q1. What system-level levers exist beyond the core and the accelerator (I/O, memory split, clocks, build strategy, verification depth, platform, boot medium, display, power/thermal, reproducibility)?

### Takeaway
On the KV260 the board itself dictates several hard constraints that the configurator must surface as facts rather than choices: all DRAM (4 GB DDR4, ~19.2 GB/s peak) hangs off the hard PS DDR controller, QSPI is the primary boot device with SD secondary, power is a 12 V / 3 A input with a ~10 W application budget under the stock fansink, and the Vivado board flow already knows which peripherals are fixed vs. customizable. The real levers are: which I/O to instantiate, how to split 4 GB among OS / weights / KV cache, per-domain clock targets, Vivado strategy/directive/jobs/incremental reuse, verification depth before a multi-hour build, and reproducibility pins (tool version, strategy, directives); Vivado has no user "seed" in the classic sense.

### Cited Findings

**Board facts (KV260 / K26 SOM)**
- KV260 carrier interfaces: J2 Pmod (Digilent 2x6), J3 direct JTAG, J4 FTDI USB2.0 UART+JTAG, J5 HDMI out, J6 DisplayPort out, J7 IAS0 (4 MIPI lanes, via OnSemi AP1302 ISP), J8 IAS1 (4 MIPI lanes "connected directly to the Zynq UltraScale+ MPSoC HPA bank"), J9 Raspberry Pi camera (15-pin, 2 MIPI lanes, directly to the HPA bank), J10 1 Gb/s Ethernet RJ45, J11 microSD boot device, J12 12 V input, J13 12 V fan, U44/U46 two USB3.0 connectors each (4 ports total) — [AMD UG1089 v1.3 KV260 Starter Kit User Guide](https://docs.xibif.ch/_downloads/480ec1217d1ac2bd520e695148cfe86f/KV260_Userguide.pdf)
- Video outputs are DisplayPort 1.2a and HDMI 1.4 — [KV260 product brief (Mouser)](https://www.mouser.com/pdfDocs/xilinx-kv260-product-brief.pdf)
- The reset diagram in UG1089 shows SD_CARD_RESET_B, USB_PHY_RESET_B, USB_HUB_RESET_B and ETH_RESET_B on PS_MIO (PS side), while IAS_ISP_RESET_B, IAS_DIRECT_RESET_B and RPi_RESET_B are on PL HDIO — i.e., SD, USB and Ethernet are PS-attached peripherals and cameras are PL-attached — [UG1089](https://docs.xibif.ch/_downloads/480ec1217d1ac2bd520e695148cfe86f/KV260_Userguide.pdf)
- USB: four USB3.0 ports, each up to 900 mA at 5 V, total allocated 2.1 A across all four; Pmod supply 3.3 V / 100 mA — [UG1089](https://docs.xibif.ch/_downloads/480ec1217d1ac2bd520e695148cfe86f/KV260_Userguide.pdf)
- Power: kit requires a 12 V, 3 A adapter (not included); "The integrated fansink allows you to exercise the full 10W AMD Zynq UltraScale+ MPSoC application power budget"; a power monitor on VCC_SOM is readable over I2C — [UG1089](https://docs.xibif.ch/_downloads/480ec1217d1ac2bd520e695148cfe86f/KV260_Userguide.pdf)
- Fan: "By default, the fan runs at a constant speed. Variable fan speed control can be implemented through a FPGA based PWM fan controller. The fan gating signal is connected to a FPGA HD I/O bank pin" — [UG1089](https://docs.xibif.ch/_downloads/480ec1217d1ac2bd520e695148cfe86f/KV260_Userguide.pdf)
- Boot: "The primary boot device is a QSPI memory located on the SOM and the secondary boot device is an SD card interface on the carrier card. By default, the KV260 Starter Kit carrier card sets the XCK26 boot mode to QSPI32. The SOM boots up to U-Boot using the QSPI contents and then U-Boot does a hand-off to the secondary boot device." QSPI holds A/B firmware images with an on-target update tool and an Ethernet boot-image recovery tool — [UG1089](https://docs.xibif.ch/_downloads/480ec1217d1ac2bd520e695148cfe86f/KV260_Userguide.pdf)
- Production SOMs provide both QSPI and eMMC on the SOM (starter-kit SOM does not expose eMMC the same way) — [UG1089](https://docs.xibif.ch/_downloads/480ec1217d1ac2bd520e695148cfe86f/KV260_Userguide.pdf)
- Memory: K26 SOM has 4 GB 64-bit DDR4, driven by the PS DDR controller (DDRC) with configurable QoS — [AMD DS987 K26 SOM data sheet](https://www.amd.com/content/dam/xilinx/support/documents/data_sheets/ds987-k26-som.pdf); search-result summary gives DDR4-2400 => 64 bit x 2400 MT/s / 8 = 19.2 GB/s peak (arithmetic; verify speed grade in DS987) — [Mouser DS987 copy](https://www.mouser.com/datasheet/2/903/ds987_k26_som-2329045.pdf)
- Platform discovery: "Vivado Board Flow enables a level of hardware abstraction that automatically configures peripherals fixed on the SOM card (e.g., DDR4), defines associated timing constraints, and presents the customizable physical I/O available on the SOM connector(s)." Board files exist for KV260 Starter Kit, SM-K26-XCL2GC and SM-K26-XCL2GI — [UG1089](https://docs.xibif.ch/_downloads/480ec1217d1ac2bd520e695148cfe86f/KV260_Userguide.pdf)
- Vitis base platforms are named by enabled interfaces, e.g. `kv260_ispMipiRx_vcu_DP` "enables a MIPI receive interface to the ISP on the carrier card and a standard single video stream to the DisplayPort" — precedent for an I/O-set-as-identity naming scheme — [UG1089](https://docs.xibif.ch/_downloads/480ec1217d1ac2bd520e695148cfe86f/KV260_Userguide.pdf)

**LLM workload lever (prefill vs decode, KV cache)**
- Prefill has high arithmetic intensity and is compute-bound; decode (sequence length 1 per step) collapses arithmetic intensity and is usually memory-bandwidth-bound, reading the whole KV cache every step — [Towards Data Science: Prefill is compute-bound, decode is memory-bound](https://towardsdatascience.com/prefill-is-compute-bound-decode-is-memory-bound-why-your-gpu-shouldnt-do-both/); [SPAD: Specialized Prefill and Decode Hardware (arXiv 2510.08544)](https://arxiv.org/pdf/2510.08544); [Sarathi-Serve (arXiv 2403.02310)](https://arxiv.org/pdf/2403.02310)
- (Opinion/secondary) "as context grows, during decode, each new token reads all previous keys and values across all layers" — [WEKA: Prefill vs Decode](https://www.weka.io/learn/ai-ml/prefill-and-decode/)

**Build strategy (Vivado / Vitis)**
- "Strategies are a defined set of Vivado implementation feature options"; Performance strategies "improve design performance at the expense of run time"; "You should always try to meet timing goals, using the Vivado implementation defaults first, before choosing a Performance strategy"; Performance_Explore "is a good first choice when design goals cannot be met with default settings and increased runtime is acceptable" — [UG904 Vivado Implementation (2021.1 mirror)](https://static.eetrend.com/files/2021-09/wen_zhang_/100553629-220271-ug904-vivado-implementation.pdf); [docs.amd.com UG904 Defining Implementation Runs](https://docs.amd.com/r/2021.1-English/ug904-vivado-implementation/Defining-Implementation-Runs)
- Incremental implementation reuses a placed-and-routed reference checkpoint — [UG904](https://static.eetrend.com/files/2021-09/wen_zhang_/100553629-220271-ug904-vivado-implementation.pdf)
- Vitis/v++ passes Vivado run properties via `--vivado.prop run.impl_1.{STEPS.ROUTE_DESIGN.ARGS.DIRECTIVE}={NoTimingRelaxation}`, synthesis via `...{STEPS.SYNTH_DESIGN.ARGS.FLATTEN_HIERARCHY}={full}`, `--reuse_impl <checkpoint.dcp>` to skip re-implementation, and recommends putting these in `--config` files rather than the command line — [Vitis Tutorials: Controlling Vivado Implementation](https://xilinx.github.io/Vitis-Tutorials/2021-2/build/html/docs/Hardware_Acceleration/Feature_Tutorials/06-controlling-vivado-implementation/README.html)
- Strategy-sweep automation (trying multiple strategies, incremental optimization, routing critical nets first) exists as open scripts — [abs-tudelft/vivado-impl-scripts](https://github.com/abs-tudelft/vivado-impl-scripts)

**Reproducibility**
- Vivado uses an analytical placer and "removed the 'cost table' (also known as random seeds) user options"; yet tiny functionally-irrelevant tweaks can swing WNS by large amounts; vendor-adjacent tools emulate seeds via placement exploration that randomizes non-critical register locations (vendor blog, commercial interest — treat as opinion) — [Plunify: random seeds in Vivado](https://support.plunify.com/en/2017/01/11/who-says-you-cant-use-random-seeds-in-vivado/); [Plunify: placement seeds 53% WNS](https://support.plunify.com/en/2018/10/03/how-to-get-53-improvement-in-wns-from-running-placement-seeds-in-vivado/)
- Vitis and Vivado tools must be the same release version — [Vitis Tutorials](https://xilinx.github.io/Vitis-Tutorials/2021-2/build/html/docs/Hardware_Acceleration/Feature_Tutorials/06-controlling-vivado-implementation/README.html)
- `place_design` directive options documented per release (2023.2, 2025.2) — [UG835 place_design 2025.2](https://docs.amd.com/r/en-US/ug835-vivado-tcl-commands/place_design)
- Buildroot: "Buildroot does not attempt to detect what parts of the system should be rebuilt when the system configuration is changed"; toolchain changes need a full rebuild; `make clean all` after config changes; shared download cache via `BR2_DL_DIR`; out-of-tree builds with `O=` — [Buildroot manual](https://buildroot.org/downloads/manual/manual.html)

**Precedent CLIs for system levers**
- LiteX exposes system levers directly as flags: `--cpu-type rocket --cpu-variant linux --cpu-num-cores 1 --cpu-mem-width 2 --sys-clk-freq 50e6 --with-ethernet --with-sdcard`; peripheral inclusion changes the memory map (e.g., UART base) — [linux-on-litex-rocket](https://github.com/litex-hub/linux-on-litex-rocket)
- Chipyard composes configs from fragments with `++` (e.g., `new WithNBigCores(1) ++ ...`), selected at build time by `CONFIG=` — [Chipyard Heterogeneous SoCs](https://chipyard.readthedocs.io/en/stable/Customization/Heterogeneous-SoCs.html); [Chipyard Keys, Traits, Configs](https://chipyard.readthedocs.io/en/1.6.1/Customization/Keys-Traits-Configs.html)

### Inferences
- Full lever inventory for Ouroboros (my synthesis):
  1. Target platform: auto-detected from XSA / board file; manual override for "any AMD FPGA". Board flow already distinguishes fixed (DDR) from customizable I/O, which maps cleanly onto "always-on / toggleable" in the UI.
  2. I/O set: per interface on/off. On KV260, SD, USB, Ethernet are PS-MIO peripherals — disabling them likely frees little or no PL LUTs, but a soft RISC-V core needs PL-side bridges/drivers to reach them (via PS AXI slave ports), which do cost LUTs. Cameras (IAS1, RPi) and Pmod are PL HDIO/HPA and cost real PL logic (MIPI CSI-2 RX, etc.). The configurator should show the LUT delta per interface, not a binary "frees LUTs" claim.
  3. Memory map / split of 4 GB: OS RAM vs model weights vs KV cache (vs framebuffer). Weight size is fixed by the .gguf quantization; KV cache = 2 x layers x kv_heads x head_dim x context x bytes; OS gets the rest. This is the natural home for the "Big KV cache?" question, phrased as max context length.
  4. Clock domains: CPU, accelerator, memory-interface (AXI/HP port), video pixel clock. "Faster CPU or faster systolic array?" maps to clock targets plus LUT/DSP budget allocation.
  5. Prefill vs decode balance: because decode is bandwidth-bound and KV260 peak DRAM bandwidth is ~19.2 GB/s shared with the OS, extra PEs mainly help prefill; decode tokens/s is roughly bounded by bandwidth / (weight bytes per token). This makes "Lots of PEs?" and "Decode vs prefill?" partly the same question and the configurator should say so.
  6. Build strategy: Default → Performance_Explore → multi-strategy sweep with N parallel jobs; incremental reuse of last routed DCP; max timing-closure retries; fall back to lower clock if closure fails.
  7. Verification depth before bitstream: C-sim lock-step vs DoomV (fast), RTL co-sim of accelerator kernels, full Linux boot in simulation (hours), formal (optional). Default to "lock-step C-sim + co-sim of changed kernels".
  8. Software rebuild: "Rebuild OpenSBI/Linux/device tree for this configuration, or bring your own?" — device tree must match the I/O set and memory split, so this is mandatory whenever those change (Buildroot's "no automatic partial rebuild" warning supports making this explicit).
  9. Boot medium: QSPI32 (stock, holds A/B firmware) + SD rootfs (stock); JTAG for dev iterations. Overwriting QSPI is a destructive action requiring confirmation (A/B images and recovery tool exist).
  10. Display: DP vs HDMI vs headless; resolution affects pixel clock and framebuffer bandwidth stolen from decode.
  11. Power/thermal: 10 W application budget with stock fansink; optional PWM fan controller in PL; read VCC_SOM power monitor to report watts.
  12. Reproducibility: pinned Vivado/Vitis version (must match), recorded strategy+directives, toolchain commits, hash of .gguf and XSA; Vivado has no user seed, so "seed" in config should be documented as placement-exploration directive, not a true RNG seed.

### Gaps
- Could not confirm from UG1089 text whether the KV260 HDMI output is PL-driven and DisplayPort is PS-GTR (DPDMA) driven; common knowledge says so but I did not get a primary citation. Matters for the "disable HDMI frees LUTs" claim.
- Exact K26 DDR4 speed (2400 vs 2666) not verified from DS987 directly; 19.2 GB/s is derived.
- Did not fetch the current (2025.x) UG904 strategy list (the en-US page 404'd); strategy names (Performance_Explore, Area_Explore, Power_DefaultOpt, Flow_RunPhysOpt, Congestion_*, Flow_RuntimeOptimized) are from memory of older UG904 and should be verified for the pinned version.
- No source found on Vivado `-jobs` scaling or determinism across job counts.

## Q2. How do established configurators tier choices, and what makes a good always-asked question?

### Takeaway
The evidence converges on: show only a few high-frequency/high-impact choices up front, put the rest one click away, and avoid more than two disclosure levels (NN/g). Kconfig contributes the mechanics Ouroboros needs underneath the tiers (conservative defaults, `depends on` for visibility, `select` only for invisible symbols, `imply` for soft defaults, `choice` for exclusive options, `range` for numbers, help text per option, defconfigs). Successful consumer tools (Raspberry Pi Imager, create-vite, LM Studio, NVIDIA App) ask 3-6 plain-language questions and hide the rest behind a customization step, while always offering a non-interactive flag path.

### Cited Findings

**UX literature**
- Progressive disclosure: "Initially, show users only a few of the most important options" and "Offer a larger set of specialized options upon request"; improves "learnability, efficiency of use, and error rate"; must "disclose everything that users frequently need up front" without "too many options"; it must be "obvious how users progress"; decide placement using "task analysis and field studies", "frequency-of-use statistics", "observational usability testing" — [NN/g Progressive Disclosure](https://www.nngroup.com/articles/progressive-disclosure/)
- "designs that go beyond 2 disclosure levels typically have low usability" — [NN/g](https://www.nngroup.com/articles/progressive-disclosure/)
- Staged disclosure (a linear wizard, "one step at a time") is distinct from hierarchical progressive disclosure — [NN/g](https://www.nngroup.com/articles/progressive-disclosure/)

**Kconfig (Linux)**
- Defaults: "The default value deliberately defaults to 'n' in order to avoid bloating the build"; exceptions for `default y`: options replacing formerly always-built features, gatekeeping options that expose other settings, sub-driver behaviour, universal infrastructure (CONFIG_NET, CONFIG_BLOCK). Only the first visible default applies — [Kconfig language](https://www.kernel.org/doc/html/latest/kbuild/kconfig-language.html)
- `depends on` hides an entry when unmet and caps its value; `select` is a reverse dependency that forces a value "without visiting the dependencies. By abusing select you are able to select a symbol FOO even if FOO depends on BAR that is not set"; best practice: select only non-visible symbols with no dependencies — [Kconfig language](https://www.kernel.org/doc/html/latest/kbuild/kconfig-language.html)
- `imply` = weak reverse dependency the user may still set to n; `choice` = exactly one of a group; `range` bounds int/hex; `menuconfig` shows suboptions as a separate list gated by the parent; `visible if` controls display of a menu — [Kconfig language](https://www.kernel.org/doc/html/latest/kbuild/kconfig-language.html)

**Buildroot**
- `make savedefconfig` stores the minimal diff-from-defaults config; `make list-defconfigs` lists per-board starting points kept in `configs/`; frontends menuconfig/nconfig/xconfig/gconfig all have per-entry help and search — [Buildroot manual](https://buildroot.org/downloads/manual/manual.html)

**Hardware generators**
- Chipyard: named configs built from composable fragments, chosen with `CONFIG=` — [Chipyard docs](https://chipyard.readthedocs.io/en/stable/Customization/Heterogeneous-SoCs.html)
- LiteX: one flag per system feature (`--with-ethernet`, `--with-sdcard`, `--sys-clk-freq`) — [linux-on-litex-rocket](https://github.com/litex-hub/linux-on-litex-rocket)

**Consumer configurators**
- Raspberry Pi Imager: since v2.0, customisation is its own wizard step with six sub-steps — Hostname, Localisation, User, Wi-Fi, Remote access, Raspberry Pi Connect (third-party guide) — [raspberry.tips Imager guide](https://raspberry.tips/en/raspberrypi-tutorials/how-to-install-and-setup-raspberry-pi); official getting-started — [Raspberry Pi docs](https://www.raspberrypi.com/documentation/computers/getting-started.html)
- create-vite: prompts for project name / framework / variant; `-t/--template`, `--interactive/--no-interactive`; with `--no-interactive` it assumes defaults; useful "as part of some unmonitored CI/CD pipeline, or if an AI agent is running commands" — [Vite Getting Started](https://vite.dev/guide/); [vite discussion #20846](https://github.com/vitejs/vite/discussions/20846)
- LM Studio per-model load defaults: GPU offload, context size, Flash Attention; set via gear icon; changes made at load time can be saved as that model's default; settings are "totally optional" — [LM Studio per-model defaults](https://lmstudio.ai/docs/app/advanced/per-model)
- Ollama Modelfile: everything optional except `FROM`; parameters with defaults e.g. `num_ctx` 2048, `temperature` 0.8, `top_k` 40, `top_p` 0.9, `seed` 0, `num_predict` -1 — [Ollama Modelfile](https://github.com/ollama/ollama/blob/main/docs/modelfile.mdx)
- NVIDIA App: one-click "Optimize" applies recommended settings (available for 1,200+ titles); a single Performance↔Quality slider with Performance / Balanced / Quality presets; shows current vs recommended values and preview — [NVIDIA App release](https://www.nvidia.com/en-us/geforce/news/nvidia-app-download-and-features/); [NVIDIA Control Panel help](https://www.nvidia.com/content/Control-Panel-Help/vLatest/en-us/mergedProjects/3D%20Settings/To_make_your_3D_application_look_better.htm)
- PCPartPicker: compatibility checker flags incompatibilities (socket, BIOS, PSU wattage, slots, physical size) and an estimated wattage summed from part TDPs; it only warns if estimate > PSU (350 W est. on 350 W PSU = no warning, zero buffer); community recommends ~20% headroom; it does not check all size issues (secondary sources) — [cgdirector](https://www.cgdirector.com/pcpartpicker-compatibility-warnings-explained/); [PCPartPicker forum](https://pcpartpicker.com/forums/topic/171569-psu-wattage-compatibility-checker); [build-your-own-computer-plan](https://www.build-your-own-computer-plan.com/does-pc-part-picker-check-compatibility.html)

### Inferences
- NN/g's 2-level limit argues against three nested levels. Make the three tiers three *views of one flat config* rather than nested menus: Tier 1 "Essentials" (always asked), Tier 2 "Expanded" (all choices with trade-off framing, grouped by subsystem), Tier 3 "Full" (every Kconfig-style symbol, searchable, menuconfig-like). Tier 3 should be search-first (like menuconfig `/`) rather than deeper nesting.
- Proposed Tier 1 (always asked; ~5, each a plain-language trade-off with a recommended default): (1) Board/platform (auto-detected; confirm); (2) Model .gguf + max context length ("Big KV cache?"); (3) CPU vs accelerator balance — a single slider like NVIDIA's Performance↔Quality ("Faster Linux or faster tokens?"); (4) Which I/O (checkbox list pre-filled for a laptop: display, USB, Ethernet, SD on; cameras, Pmod off); (5) Rebuild OpenSBI/Linux/DT for this config (default yes; "already have" requires a path).
- Tier 2: ISA profile (RVA23 full vs RV64GC-ish subset), vector unit width (VLEN), PE array dims, prefill/decode balance, memory split, clock targets, display resolution, boot medium, verification depth, build strategy/jobs, power cap, fan control.
- Tier 3: individual extensions, cache sizes, AXI widths, HLS pragmas/II targets, Vivado directives per step, device-tree details, seeds/placement exploration, tool paths.
- Mechanics to copy from Kconfig: default-off for anything costing LUTs unless it is laptop infrastructure (display, USB, storage = "universal infrastructure" exception); use `depends on` so incompatible options vanish (e.g., cameras hidden when the platform lacks MIPI); never silently force-enable visible options (`select` abuse) — instead surface PCPartPicker-style compatibility errors/notes; persist as a minimal defconfig-style diff.
- Good always-asked question criteria (synthesis of NN/g + consumer precedents): high impact on outcome, no safe universal default (depends on the user's goal), answerable without hardware jargon, reversible only by rebuilding (so worth asking up front). Everything with a derivable default (clock, PE count from LUT budget) should be shown as a recommendation, not asked.

### Gaps
- Could not fetch AMD documentation on Vivado IP customization GUI tabs (Basic vs Advanced, e.g. Clocking Wizard / MIG / Zynq PS); no citation for that precedent.
- No primary source for SiFive Core Designer's UI tiering (product appears discontinued/limited availability; not researched).
- No Yocto-specific findings gathered (local.conf / MACHINE / DISTRO layering would be the analog).
- No empirical study on how many up-front questions is optimal for technical wizards; "3-6" is drawn from the observed consumer tools.

## Q3. How should a recommendation be presented, explained, estimated, overridden, diffed and saved?

### Takeaway
Best-in-class precedents separate "plan" from "apply": Terraform shows a full diff before any change and can save the plan; NVIDIA App shows current vs recommended values with one-click optimize plus a slider; PCPartPicker shows a running estimate (wattage) and compatibility verdicts as you change parts; Buildroot/Kconfig store only the delta from defaults (savedefconfig); create-vite/clig.dev require every prompt to have a flag equivalent so configs can be replayed non-interactively.

### Cited Findings
- `terraform plan` "alone does not actually carry out the proposed changes"; `-out=FILE` saves a plan to pass to `terraform apply`; a plan without `-out` is "speculative" and the world may change before apply; `-detailed-exitcode` returns 0 no changes / 1 error / 2 changes present — [Terraform plan](https://developer.hashicorp.com/terraform/cli/commands/plan)
- NVIDIA App: "Optimize" applies recommended settings; slider with presets; "visual on the optimization page that shows current values and a preview of recommended values" (secondary description) — [NVIDIA App](https://www.nvidia.com/en-us/geforce/news/nvidia-app-download-and-features/)
- PCPartPicker estimated wattage = sum of manufacturer max/TDP values; warns only when estimate exceeds capacity — [cgdirector](https://www.cgdirector.com/pcpartpicker-compatibility-warnings-explained/); [PCPartPicker forum](https://pcpartpicker.com/forums/topic/171569-psu-wattage-compatibility-checker)
- LM Studio lets the user save load-time overrides as a per-model default — [LM Studio](https://lmstudio.ai/docs/app/advanced/per-model)
- `make savedefconfig` (minimal config) and `BR2_DEFCONFIG`/`configs/` for shareable configs — [Buildroot manual](https://buildroot.org/downloads/manual/manual.html)
- clig.dev: "If --no-input is passed, don't prompt... If the command requires input, fail and tell the user how to pass the information as a flag"; only prompt when stdin is a TTY; config precedence flags > env > project config > user config > system; provide `--dry-run` so users "can see what'll happen before they commit to it" — [Command Line Interface Guidelines](https://clig.dev/)
- Vitis recommends `--config` files over long command lines for Vivado options — [Vitis Tutorials](https://xilinx.github.io/Vitis-Tutorials/2021-2/build/html/docs/Hardware_Acceleration/Feature_Tutorials/06-controlling-vivado-implementation/README.html)

### Inferences
- Recommended flow: inputs (.gguf + detected platform) → derive recommendation → show a "plan" screen with three columns: field / recommended / yours (overrides highlighted, like a diff) plus "why" one-liners → estimates panel (LUT/FF/DSP/BRAM % with headroom bar, estimated decode tok/s and prefill tok/s, max context, RAM left for Linux, est. boot time, est. build time, est. power vs 10 W) → compatibility verdicts (error = blocks build; note = warning), PCPartPicker-style, with explicit headroom (avoid PCPartPicker's zero-buffer flaw: warn at e.g. >85% LUT since routing congestion rises before 100%).
- Estimates should be labeled with confidence/provenance (model-based vs measured on a prior build of this config), because PCPartPicker-style sums are known to be rough.
- Save as `ouroboros.toml` containing only deltas from the recommendation plus pinned inputs (gguf hash, XSA hash, tool versions) — defconfig semantics; `ouroboros build --config x.toml --no-input` replays; `ouroboros plan` = dry-run that prints the diff and estimates with Terraform-like exit codes.
- Slider pattern: one "Linux ↔ LLM" balance slider and one "prefill ↔ decode" slider with named detents (e.g., Linux-first / Balanced / LLM-first) mirroring NVIDIA's Performance/Balanced/Quality; moving a slider live-updates the estimate panel, and dragging past feasibility shows the blocking constraint (e.g., "decode is DRAM-bandwidth-limited; more PEs won't raise tok/s").

### Gaps
- No published case study found of a hardware-generator UI that shows pre-build PPA estimates; the estimates panel is extrapolated from consumer precedents.
- No source on accuracy of HLS-report vs post-route LUT estimates for this kind of design (would set the confidence labels).

## Q4. Claude-Code-like terminal UX for a multi-hour build: progress, stages, failure attribution, resumability

### Takeaway
Claude Code's own UX offers concrete patterns: a toggleable task checklist (Ctrl+T, up to five items, pending / in-progress / complete), backgroundable long tasks with IDs (Ctrl+B, `/tasks`), a collapsed-by-default transcript expandable with Ctrl+O, Esc to interrupt while keeping work done, one-line recaps after stepping away, and `--resume/--continue` restoring state. clig.dev adds: always show progress for long operations, print logs on failure, put the most important info last, make errors actionable, be crash-only so re-running resumes, and suggest the next command.

### Cited Findings
- Task list: "items Claude created to plan multi-step work, with indicators showing what's pending, in progress, or complete"; "Press Ctrl+T to toggle the task list view. The display shows up to five tasks at a time"; expanded state is restored on `--resume`/`--continue` — [Claude Code interactive mode](https://code.claude.com/docs/en/interactive-mode)
- Ctrl+B backgrounds running Bash commands and agents; background tasks get unique IDs for tracking/output retrieval; `/tasks` lists running shells/subagents; commands that hit their timeout are moved to background rather than killed — [Claude Code interactive mode](https://code.claude.com/docs/en/interactive-mode)
- Ctrl+O toggles a transcript viewer with detailed tool usage and timestamps; repetitive calls are collapsed by default into one line (e.g., "Called slack 3 times") — [Claude Code interactive mode](https://code.claude.com/docs/en/interactive-mode)
- Esc stops the current operation "so you can redirect. Claude keeps the work done so far"; Ctrl+C interrupts, double-press exits — [Claude Code interactive mode](https://code.claude.com/docs/en/interactive-mode)
- Recap: after ≥3 minutes idle with terminal unfocused, a one-line recap of what happened is shown on return — [Claude Code interactive mode](https://code.claude.com/docs/en/interactive-mode)
- "If your program displays no output for a while, it will look broken"; for parallel progress bars "if there is an error, make sure you print out the logs"; "Put the most important information at the end of the output"; rewrite errors to be actionable; crash-only design so "you should be able to hit <up> and <enter> and it should pick up from where it left off"; suggest next commands; confirm dangerous actions, with a scriptable `--confirm=<name>` alternative — [clig.dev](https://clig.dev/)
- Vitis `-R2` writes DCP checkpoints for each implementation step, and `--reuse_impl` resumes from a DCP — natural resume points — [Vitis Tutorials](https://xilinx.github.io/Vitis-Tutorials/2021-2/build/html/docs/Hardware_Acceleration/Feature_Tutorials/06-controlling-vivado-implementation/README.html)

### Inferences
- Stage list for the checklist (each a resumable checkpoint keyed by input hash): parse .gguf + XSA → plan/estimate → HLS C-sim lock-step vs DoomV → HLS synthesis per kernel (parallel) → co-sim (optional) → block design/integration → Vivado synth → opt/place/phys_opt/route (DCP each) → timing check (retry with next strategy / lower clock) → bitstream + boot image → OpenSBI/Linux/DT build (can run in parallel with hardware) → package SD/QSPI images → optional flash.
- Failure attribution: map failures to the config field most likely responsible (e.g., timing fail on accelerator clock domain → "accelerator clock 300 MHz → try 250 MHz or fewer PEs"; LUT overflow → list top LUT consumers vs enabled I/O), show the 5-10 relevant log lines, keep full logs one keystroke away (Ctrl+O analog), and end with the suggested next command.
- Resumability: content-addressed stage cache (hash of config subset + tool version) so changing only Linux options doesn't redo the bitstream, and vice versa — explicitly avoiding Buildroot's "no partial-rebuild detection" trap.
- Destructive action (overwrite QSPI boot firmware) needs typed confirmation; mention A/B fallback and recovery tool (UG1089).

### Gaps
- Did not fetch Claude Code docs on status line customization, plan mode, or permission prompts specifically; patterns above are from the interactive-mode page only.
- No measured data on typical KV260 Vivado runtimes for a design of this size, so build-time estimates must be learned from the user's own runs.
