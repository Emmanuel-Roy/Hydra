# Automating the AMD Vitis HLS + Vivado flow from a CLI configurator, and building it as a polished TUI

Scope: fact base for the Ouroboros configurator (.gguf + FPGA target, KV260 first -> estimate doc -> parameterised HLS C++ -> HLS synth -> Vivado impl/bitstream -> Kria firmware package -> report). Research date 2026-09-30. Items marked "(training knowledge, not re-verified this session)" come from prior knowledge of the tools; they are well established but the writer should treat them as lower-confidence than cited items.

## Q1. Command-line flows for current AMD tools (2024.x-2026.x): HLS, Vivado batch, Zynq US+ block design, Kria bitstream loading and boot update

### Takeaway
Since the 2024.x unified Vitis release, HLS is driven headless by `v++ -c --mode hls --config hls_config.cfg` (synthesis) and `vitis-run --mode hls --csim|--cosim|--impl|--package|--tcl` (everything else); the `vitis_hls` executable is deprecated and the classic HLS IDE was removed in 2025.1, so a generator should emit a `.cfg` file (with a `vitis-run --mode hls --tcl` fallback for legacy Tcl). Vivado is driven by `vivado -mode batch -source build.tcl` in non-project mode; the Kria deliverable is not BOOT.BIN but a firmware folder (`.bit.bin` + `.dtbo` + `shell.json` [+ `.xclbin`]) in `/lib/firmware/xilinx/<app>/` loaded with `xmutil loadapp`.

### Cited Findings
**Vitis HLS (unified Vitis, 2024.2 -> 2025.2/2026.1 docs)**
- UG1399 documents `v++ -c --mode hls --config <cfg> [--work_dir <dir>] [--part <part>] [--freqhz <f>] [-f <xpfm|xsa>] <input>` for synthesis, and `vitis-run --mode hls` with `--csim`, `--cosim`, `--impl` (Vivado out-of-context implementation of the HLS IP), `--package`, `--tcl` (evaluate an HLS Tcl file), `--itcl` (interactive Tcl), `--input_file`. The current doc page states `vitis_hls` is deprecated in favour of `v++`/`vitis-run`. — [UG1399: vitis, v++, and vitis-run Commands](https://docs.amd.com/r/en-US/ug1399-vitis-hls/vitis-v-and-vitis-run-Commands)
- Config file `[hls]` section keys include `syn.file=` (sources), `syn.top=` (top function), clock (`clock=`/`--freqhz`), `part=`, and packaging via `package.output.format=` (`ip_catalog`, `xo`, etc.). — [UG1399](https://docs.amd.com/r/en-US/ug1399-vitis-hls/vitis-v-and-vitis-run-Commands); [UG1702 Vitis Compiler Configuration File](https://docs.amd.com/r/en-US/ug1702-vitis-accelerated-reference/Vitis-Compiler-Configuration-File)
- AMD's introductory examples run as: `vitis-run --mode hls --csim --config hls_config.cfg --work_dir work_dir`, `v++ --compile --mode hls --config hls_config.cfg --work_dir work_dir`, and legacy `vitis-run --mode hls --tcl run_hls.tcl`. — [Vitis-HLS-Introductory-Examples execution methods (DeepWiki summary of the AMD repo)](https://deepwiki.com/Xilinx/Vitis-HLS-Introductory-Examples/2.1-execution-methods)
- "Vitis HLS Classic IDE has been discontinued ... You can only launch the Unified IDE in 2025.1+"; `vitis_hls` no longer works as before. — [AMD AR 75342 Vitis HLS Known Issues per Release](https://adaptivesupport.amd.com/s/article/75342?language=en_US) (summarised via search; also [daiphys Vitis notes](https://www.daiphys.com/portal/fpga/xilinx/tools/vitis.html))
- Real-world breakage: with Vitis 2024.2, hls4ml's generated Tcl hits the deprecation warning ("The vitis_hls executable is deprecated. Consider using vitis-run --mode hls --tcl"), fails on removed directive options (`-maximum_size` in `config_array_partition`), and then reports "CSynthesis report not found / Vivado synthesis report not found". — [hls4ml issue #1231](https://github.com/fastmachinelearning/hls4ml/issues/1231)
- Packaging for Vivado: HLS exports a Vivado IP catalog package (the "Vivado IP flow"), which is then added to a Vivado IP repo (`set_property ip_repo_paths ...; update_ip_catalog`). — [UG1399 Enabling the Vivado IP Flow (2022.1)](https://docs.amd.com/r/2022.1-English/ug1399-vitis-hls/Enabling-the-Vivado-IP-Flow)

**Vivado non-project batch flow**
- Non-project batch is the standard scriptable flow: `vivado -mode batch -source build.tcl -tclargs ...`; script body: `read_verilog/read_vhdl/read_ip/read_xdc` (or `read_bd`), `synth_design -top <top> -part xck26-sfvc784-2LV-c`, `opt_design`, `place_design`, `phys_opt_design`, `route_design`, `write_checkpoint`, `report_utilization`, `report_timing_summary`, `write_bitstream`. (training knowledge, not re-verified this session; canonical docs: [UG892 Design Flows Overview](https://docs.amd.com/r/2023.2-English/ug892-vivado-design-flows-overview/Performing-Implementation-with-Incremental-Compile), UG894 Using Tcl Scripting, [UG835 Tcl reference](https://docs.amd.com/r/en-US/ug835-vivado-tcl-commands/report_timing_summary))
- K26 part string used in Tcl: `create_project project_1 -part xck26-sfvc784-2LV-c`. — [AMD forum: Vivado and Kria K26 SOM](https://adaptivesupport.amd.com/s/question/0D52E00007G0tIJSAZ/vivado-and-kria-board-k26-som?language=en_US)
- Incremental compile (`read_checkpoint -incremental`) is the documented way to cut re-implementation time when only small parts change. — [UG892 Incremental Compile](https://docs.amd.com/r/2023.2-English/ug892-vivado-design-flows-overview/Performing-Implementation-with-Incremental-Compile)
- Block designs with a Zynq UltraScale+ PS are scripted with `create_bd_design`, `create_bd_cell -type ip -vlnv xilinx.com:ip:zynq_ultra_ps_e:*`, `apply_bd_automation -rule xilinx.com:bd_rule:zynq_ultra_ps_e -config {apply_board_preset 1}` (requires the KV260 board files / `board_part` set, e.g. `xilinx.com:kv260_som:part0:*` with the carrier connection), `apply_bd_automation` for AXI connections, `validate_bd_design`, `make_wrapper`, `generate_target`; `write_bd_tcl` dumps an existing BD to a reproducible Tcl script. BDs require an in-memory/project context even in otherwise non-project scripts. (training knowledge, not re-verified this session)
- Kria "Vivado accelerator flow" doc: the vendor-supported path for custom PL on Kria uses Vivado to make the platform/bitstream, then converts it into dfx-mgr firmware. — [Kria SOM Vivado Accelerator Flow (2022.1)](https://xilinx.github.io/kria-apps-docs/creating_applications/2022.1/build/html/docs/vivado_accel_flow.html)

**Kria bitstream loading (runtime) and boot firmware**
- `xmutil loadapp` invokes the DFX Manager daemon (dfx-mgr), which manages on-target apps and loads/unloads bitstreams. Each app lives in `/lib/firmware/<company>/<app>/` (AMD examples use `/lib/firmware/xilinx/<app>`) and must contain: bitstream converted to `*.bit.bin`, device-tree overlay `*.dtbo`, `.xclbin` only if it is an XRT/Vitis design, and `shell.json` (e.g. `{"shell_type":"XRT_FLAT","num_slots":"1"}`). Commands: `sudo xmutil listapps`, `sudo xmutil unloadapp`, `sudo xmutil loadapp <app>`. — [Kria KV260 Generation of Firmware Binaries](https://xilinx.github.io/kria-apps-docs/kv260/2022.1/build/html/docs/generating_custom_firmware.html); [KD240 version](https://xilinx.github.io/kria-apps-docs/kd240/build/html/docs/generating_custom_firmware.html); [Generating DTSI and DTBO Overlay Files](https://xilinx.github.io/kria-apps-docs/creating_applications/2022.1/build/html/docs/dtsi_dtbo_generation.html)
- AMD's helper: `git clone --branch xlnx_rel_v2022.1 https://github.com/Xilinx/kria-apps-firmware.git`, put `.bit`/`.dtsi`(/`.xclbin`) in `kv260/custom`, copy an example `shell.json`, run `make` (Makefile converts `.bit`->`.bin` via bootgen and `.dtsi`->`.dtbo` via dtc). — [KV260 firmware generation](https://xilinx.github.io/kria-apps-docs/kv260/2022.1/build/html/docs/generating_custom_firmware.html)
- Underlying commands (training knowledge, not re-verified): `bootgen -image bit.bif -arch zynqmp -process_bitstream bin -w` with a BIF `all:{ design.bit }`; `dtc -@ -O dtb -o app.dtbo app.dtsi`; DTSI from XSCT `createdts -hw design.xsa -overlay -zocl -platform-name ...` or hand-written fpga-region overlay. Alternative `fpgautil -b design.bit.bin -o app.dtbo` loads directly without dfx-mgr.
- 2025.1 community guide shows custom PL overlays + generic-UIO on KR260 with PetaLinux 2025.1 (still the same .bit.bin/.dtbo model). — [controlpaths: Custom PL Overlays on KR260, PetaLinux 2025.1](https://www.controlpaths.com/2025/12/21/enabling-custom-pl-overlays-kr260/)
- Boot firmware (BOOT.BIN in QSPI) is separate from apps: `sudo xmutil bootfw_status`, `sudo xmutil bootfw_update -i <BOOT.BIN>`, then on the immediate next boot `sudo xmutil bootfw_update -v` or the A/B mechanism reverts to Image A. Legacy KV260 kits require the 2022.1+ boot FW update before booting Ubuntu 22.04; the Boot Image Recovery tool (web UI over Ethernet) is the fallback. — [element14: Kria firmware update for Ubuntu 22.04](https://community.element14.com/technologies/fpga-group/b/blog/posts/kria-kv260-kr260-firmware-update-for-booting-ubuntu-22-04); [FPGA Developer: Update Kria Boot Firmware](https://www.fpgadeveloper.com/update-kria-boot-firmware/); [Kria K26 SOM wiki](https://xilinx-wiki.atlassian.net/wiki/spaces/A/pages/1641152513/Kria+K26+SOM)

### Inferences
- The configurator should NOT generate BOOT.BIN for the normal path: Kria boots a fixed AMD boot FW + Ubuntu/PetaLinux, and the Ouroboros accelerator is an app overlay. BOOT.BIN only matters if a custom PS configuration is needed beyond the overlay model; a `bootfw_status` check belongs in the "deploy" preflight.
- Recommended layered emission: `hls_config.cfg` (v++), `build.tcl` (Vivado non-project, sourcing a generated `bd.tcl`), `bit.bif`, `app.dtsi`, `shell.json` -> one firmware tarball + `scp`/`xmutil` deploy step.
- Version risk is real (hls4ml #1231): pin one AMD release per Ouroboros release, and keep a thin adapter that maps "intent" -> cfg keys/Tcl directives per version.
- Bitstream on the K26 can also be loaded by PYNQ-style `fpgautil`; for an XRT-free LLM accelerator, the "XRT_FLAT" shell.json + generic UIO / `/dev/mem` is the lightest path.

### Gaps
- Did not fetch UG1399 config-key tables in full (exact key names for clock uncertainty, `package.output.syn`, `syn.directive.*`, `syn.cflags`), nor UG894; verify exact keys against the pinned release.
- Did not verify whether 2025.x `createdts` (XSCT) was replaced by SDT/`sdtgen` (System Device Tree) for DTSI overlay generation; AMD has been migrating to SDT flows — check before depending on XSCT.
- No direct confirmation of the exact KV260 board_part string for current releases.

## Q2. Parameterising HLS designs from a generator; pitfalls (compile time, nondeterminism, licensing)

### Takeaway
Generate a header of `constexpr`/`#define` parameters (dims, tile sizes, quant bits, unroll/partition factors) plus a generated `.cfg`/Tcl; directives that take literals must be fed by macros/constexpr. Licensing is favourable: the K26 (XCK26) is usable with the free Vivado ML Standard edition, no licence file needed.

### Cited Findings
- "No license is required for K26"; K26 is commonly recommended as a free-tier (Vivado ML Standard) device. — [AMD forum: Vivado and Kria K26 SOM](https://adaptivesupport.amd.com/s/question/0D52E00007G0tIJSAZ/vivado-and-kria-board-k26-som?language=en_US); [AMD forum: limitations of Vivado Standard Edition](https://adaptivesupport.amd.com/s/question/0D5Pd00001RQFhVKAX/please-tell-me-about-the-limitations-of-vivado-standard-edition?language=en_US)
- The `v++ -c --mode hls` flow accepts config files (recommended), with HLS directives expressible as config commands (interface, synthesis, packaging). — [UG1399](https://docs.amd.com/r/en-US/ug1399-vitis-hls/vitis-v-and-vitis-run-Commands)
- Directive/option drift between versions breaks generated scripts (e.g. `config_array_partition -maximum_size` removed by 2024.2). — [hls4ml #1231](https://github.com/fastmachinelearning/hls4ml/issues/1231)
- hls4ml's model of parameterisation (precision, ReuseFactor, strategy per layer -> templated C++ + generated build script) and its Vitis backend are documented; it is the closest open-source analogue of "generator writes HLS C++ from a model description". — [hls4ml Vivado/Vitis backend docs](https://fastmachinelearning.org/hls4ml/backend/vitis.html)
- Common parameter-passing mechanisms (training knowledge, not re-verified): `syn.cflags=-DTILE=64 -DQBITS=4` in cfg (Tcl: `add_files -cflags "-D..."`), `#pragma HLS UNROLL factor=N` / `ARRAY_PARTITION factor=N` accept macro- or constexpr-derived constants, templated top-functions need a non-template wrapper as `syn.top`.

### Inferences
- Prefer a generated `ouro_params.h` (single source of truth, hashed into the build ID) over `-D` flags scattered in scripts; it diffs cleanly and is easy to show in the requirements doc.
- Nondeterminism: Vivado P&R is deterministic for identical inputs/seed/thread count/version/host OS in practice, but results can change with `-maxThreads`/host differences; record `version`, `general.maxThreads`, directives and seeds in a build manifest (inference; not sourced this session).
- Long compile: keep HLS kernels small and compositional (one kernel per op type, reused), so parameter sweeps re-run only csynth for changed kernels; use OOC synthesis + incremental implementation for top-level changes.

### Gaps
- Did not find an official AMD device-support table for ML Standard in 2025.x listing XCK26 explicitly (only forum statements). Writer should cite AMD's licensing page if available, or note the forum basis.
- No primary source on Vivado determinism guarantees.

## Q3. Reliable early resource/timing estimates; report parsing; stage durations

### Takeaway
Three tiers: (1) analytic pre-estimates (FINN-style per-layer formulas / hls4ml surrogate models) in seconds, (2) HLS csynth reports (`csynth.xml`, minutes) which are known to deviate from implementation, (3) Vivado post-synth/post-route reports (`report_utilization`, `report_timing_summary -rpx`) as ground truth. No reliable public benchmark of wall-clock times for ~100K-LUT ZU5EV-class designs was found.

### Cited Findings
- `report_timing_summary` / `report_timing` can write an XML-based `.rpx` (`-rpx file`) since 2014.3, reloadable with `open_report`. — [AMD AR 62391](https://www.xilinx.com/support/answers/62391.html); [UG835 report_timing_summary (2025.2)](https://docs.amd.com/r/en-US/ug835-vivado-tcl-commands/report_timing_summary)
- `report_ram_utilization` exists as a separate report for BRAM/URAM detail (relevant for LLM weight buffers). — [UG835 report_ram_utilization](https://docs.amd.com/r/en-US/ug835-vivado-tcl-commands/report_ram_utilization)
- HLS-reported resources "may still differ from the final implementation due to synthesis optimizations"; FINN-R-style analytic per-layer models are used as a first estimate before synthesis. — [arXiv 2411.11678 Analysis of Hardware Synthesis Strategies](https://arxiv.org/pdf/2411.11678); [arXiv 2201.11409 RTL implementation of FINN MVU](https://arxiv.org/pdf/2201.11409)
- rule4ml predicts BRAM, DSP, FF, LUT and latency pre-synthesis for hls4ml; BRAM and DSP predictions are more accurate than LUT and FF. — [rule4ml, arXiv 2408.05314](https://arxiv.org/pdf/2408.05314)
- wa-hls4ml benchmark: 680k+ samples; GNN/transformer surrogates reach ~2.9% SMAPE for LUT/FF and R^2 > 0.9 for latency/II (on hls4ml-style networks). — [wa-hls4ml, ACM DOI 10.1145/3787490](https://doi.org/10.1145/3787490) (figures as summarised by search; not verified against the paper text)
- Place-and-route dominates runtime; utilisation above ~80% sharply increases compile time and timing-closure difficulty. — [edaboard thread on long Vivado runtimes](https://www.edaboard.com/threads/vivado-taking-a-long-time-to-run-synthesis-implementation.384348/) (forum, low authority)
- Report parsing (training knowledge, not re-verified): Vitis HLS writes `<work_dir>/hls/syn/report/csynth.xml` (+ per-function `<func>_csynth.xml`) containing `PerformanceEstimates` (latency, II, estimated clock) and `AreaEstimates/Resources` (BRAM_18K, DSP, FF, LUT, URAM) and `AvailableResources`; Vivado `report_utilization -file x.rpt` (text; parse tables) or query cells directly in Tcl (`get_cells -hier -filter {PRIMITIVE_GROUP==...}`), and `get_property SLACK [get_timing_paths -max_paths 1 -nworst 1 -setup]` for WNS — avoiding brittle text parsing.

### Inferences
- For Ouroboros, the LLM accelerator's resource story is dominated by DSP/BRAM/URAM (matmul engines + on-chip buffers) where analytic models are most accurate; LUT/FF estimates should carry wider error bars in the requirements doc.
- Good UX: show the estimate tier and its confidence explicitly ("analytic ±X%", "HLS estimate", "post-route actual"), and fail fast if the analytic tier exceeds ~80% of any K26 resource.
- K26 resources (from the K26 datasheet, numbers recalled not re-verified this session): ~117K LUTs, ~234K FFs, 1,248 DSP, 144 BRAM36, 64 URAM — [K26 SOM Data Sheet](https://my.avnet.com/wcm/connect/bc9583c9-99a5-4aac-bbbd-de761f06c0e4/K26+SOM+Datasheet.pdf?MOD=AJPERES&ContentCache=NONE&CACHE=NONE&CVID=oNpBWrh). A "~100K LUT" design is ~85% LUT on K26, i.e. in the slow-route regime.
- Rough expectations (inference only): csynth of a modest kernel = minutes; Vivado synth for ~100K LUT = tens of minutes; place+route = 30 min to several hours depending on congestion; total typically 1-3 h on a laptop. The configurator should present these as ranges and record actual times per run to self-calibrate.

### Gaps
- No authoritative stage-duration benchmarks for ZU5EV/K26 designs of ~100K LUTs found; recommend measuring on the target laptop.
- Did not confirm whether `report_utilization` supports `-format xml` in 2025.x (search did not confirm); safest is Tcl queries or RPX for timing.

## Q4. Reproducibility and CI: Docker, IP caching, version pinning, Linux vs Windows, WSL

### Takeaway
Vivado runs natively on Windows 10/11 and Ubuntu 22.04/24.04; WSL is not an officially supported OS but works in practice (WSL2 only). Containerised Vivado is common but images are huge (>200 GB for full installs), installs must be scripted via the installer's batch config, and the installer cannot be redistributed.

### Cited Findings
- Vivado 2025.2 supported OSes: Windows 10 22H2, Windows 11 23H2/24H2, RHEL/Alma 8.10/9.4-9.6/10.0, SLES 15 SP4/6/7, Amazon Linux 2023, Ubuntu 22.04.3-.5 and 24.04-24.04.2; WSL not listed. — [UG973 2025.2 (scribd mirror)](https://www.scribd.com/document/975752064/Ug973-Vivado-Release-Notes-Install-License-en-Us-2025-2); [AMD Installer and OS Support Information](https://www.amd.com/en/support/adaptive-socs-and-fpgas/installer-info-general.html)
- Community reports of Vivado inside WSL (openwifi build) and LiteX issues mixing native-Windows Vivado with WSL2 toolchains. — [openwifi discussion #341](https://github.com/open-sdr/openwifi/discussions/341); [LiteX issue #1930](https://github.com/enjoy-digital/litex/issues/1930)
- Docker packaging of Vivado ML Standard 2025.1: headless batch install using an `install_config.txt` generated by the installer in batch config-gen mode (`xsetup -b ConfigGen`), toggling `Modules=` entries; image exceeds 200 GB; some components need X11 during install; very large image archives load unreliably; multi-hour image builds. — [hdlfactory: Vivado 2025.1 in Docker](https://www.hdlfactory.com/post/2025/06/19/packaging-amd-xilinx-vivado-ml-standard-edition-2025.1-in-a-docker-container/); [filmil/vivado-docker](https://github.com/filmil/vivado-docker)
- Other Docker setups: Ubuntu 24.04-based 2025.1 container ([arthurfprecht/vivado2025.1_docker](https://github.com/arthurfprecht/vivado2025.1_docker)); WSL2 + Docker Desktop configuration with noVNC GUI ([BlommeJan/vivado-docker](https://github.com/BlommeJan/vivado-docker)); CI-oriented ([BBN-Q/vivado-docker](https://github.com/BBN-Q/vivado-docker)); Jenkins+Docker writeup ([Starware Design](https://www.starwaredesign.com/index.php/blog/64-fpga-meets-devops-xilinx-vivado-and-jenkins-with-docker)); end-to-end FPGA CI/CD journey ([petersimon.io, Oct 2025](https://petersimon.io/2025/10/21/ci-cd-for-fpgas/)).
- Ubuntu 24.04 install guide for 2025.1/2025.2 tools. — [Hackster: AMD FPGA Tools 2025.1/2025.2 on Ubuntu 24.04](https://www.hackster.io/whitney-knitter/amd-fpga-tools-2025-1-2025-2-install-on-ubuntu-24-04-4f5b60)

### Inferences
- For a laptop user on Windows (the user's machine is Windows 11), the configurator should support native Windows Vivado (`vivado.bat`, `v++.bat`) as first-class and treat WSL2/Docker as optional. Limiting the install to Vivado+Vitis HLS with only Zynq UltraScale+ device support keeps the install far below 200 GB.
- Reproducibility levers: pin tool version (check `vivado -version` at preflight and refuse mismatches), commit generated Tcl/cfg, store `.dcp` checkpoints and HLS IP zips in a content-addressed cache keyed by hash(params header + sources + tool version), use Vivado IP cache (`config_ip_cache`) for PS/IP OOC runs (training knowledge).
- Path pitfalls on Windows: spaces/long paths in work dirs (the user's paths include spaces, e.g. "Emmanuel Roy") are a known source of Tcl/HLS failures; configurator should build under a short space-free path (inference, consistent with common AMD guidance but not sourced this session).

### Gaps
- Could not fetch UG973 directly from docs.amd.com (scribd mirror + search summary only).
- No official AMD statement on WSL found either way beyond its absence from the list.

## Q5. Terminal UI frameworks for a Claude-Code-like CLI

### Takeaway
Claude Code itself is TypeScript + React + Ink (Yoga flexbox layout), built/packaged with Bun, with a heavily customised Ink renderer. For Ouroboros (a Python-friendly ML/FPGA tool driving long subprocesses), Python Rich (+ prompt_toolkit or Textual) is the pragmatic fit; Go Bubble Tea gives the best single-binary distribution; Ink gives the closest Claude Code look.

### Cited Findings
- Claude Code stack: TypeScript, React with Ink for the UI, Yoga for layout, Bun for build/packaging; chosen to be "on distribution" for the model. — [Pragmatic Engineer: How Claude Code is built](https://newsletter.pragmaticengineer.com/p/how-claude-code-is-built)
- Analyses of Claude Code's (leaked) source describe a heavily customised Ink fork: custom React reconciler, TypeScript Yoga port, cell-based screen buffer with differential rendering (only changed cells emitted), credited with large flicker reduction. — [Kotrotsos: Claude Code Internals Part 11 Terminal UI](https://kotrotsos.medium.com/claude-code-internals-part-11-terminal-ui-542fe17db016); [DeepWiki: Ink renderer & custom TUI engine](https://deepwiki.com/alesha-pro/claude-code/7.1-ink-renderer-and-custom-tui-engine) (secondary/unofficial; treat details as unverified)
- claude-code-kit: open-source extraction of Claude-Code-style Ink components (25+ React components) for building similar CLIs. — [Minnzen/claude-code-kit](https://github.com/Minnzen/claude-code-kit)
- Paradigms: Bubble Tea = Elm architecture (Model/Update/View), works inline, full-screen or mixed; Bubble Tea v2 shipped Feb 2026 (first breaking change); Ratatui = immediate-mode with buffer diffing; Ink/Textual = retained tree with reconciliation; Ink uses Yoga flexbox, Textual uses CSS-like styling and supports Linux/macOS/Windows. Recommendation from that guide: Bubble Tea for single-binary dev tools, Ratatui for performant full-screen apps, Textual for Python/data tools, Ink for Node CLIs. — [LabHub: Terminal UI Development Guide (Jul 2026)](https://labhub.hopto.org/blog/2026-07-31-terminal-ui-development-guide?lang=en); [Rost Glukhov: Bubble Tea vs Ratatui](https://www.glukhov.org/developer-tools/comparisons/tui-frameworks-bubbletea-go-vs-ratatui-rust/); [melker TUI comparison](https://github.com/wistrand/melker/blob/main/agent_docs/tui-comparison.md)
- GitHub stars (2026, per guide): Bubble Tea ~40.7k, Ink ~35.6k, Textual ~34.9k, Ratatui ~19.1k. — [LabHub guide](https://labhub.hopto.org/blog/2026-07-31-terminal-ui-development-guide?lang=en)
- Framework capabilities relevant to Ouroboros (training knowledge, not re-verified this session): Rich has `Live`, `Progress` (multiple tasks, spinners, elapsed/ETA columns), `Status` spinners, `Console.log`, Markdown/syntax/table rendering, works on Windows Terminal and legacy conhost; prompt_toolkit gives completions/history/validated prompts; Textual (same author, Textualize) adds full-screen apps, `Log`/`RichLog` widgets and async workers that can stream subprocess output, and `textual-serve`/web mode; Bubble Tea's companion libs are Bubbles (spinner, progress, viewport, textinput, list) and Lip Gloss (styling), plus Huh (forms); Ratatui is paired with crossterm (Windows-capable backend); Ink provides `<Static>` for scrolled-out log lines plus `ink-spinner`, `ink-text-input` etc., distributed via npm or a Bun/`pkg`-compiled binary.

### Inferences
- Claude-Code-like pattern = inline (not alt-screen) rendering: completed steps print once into scrollback (Ink `<Static>` / Rich `console.print` above a `Live` region), while a small live region at the bottom shows the current step, spinner, elapsed time, and the last N log lines of the running Vivado/HLS subprocess. Rich `Live` + a reader thread/asyncio on `subprocess` stdout implements this directly; Bubble Tea's `tea.Println` + inline program does the same in Go.
- "Where it may fail and why": tail logs through a regex classifier of known AMD message IDs (e.g. `ERROR: [Place 30-640]`, `CRITICAL WARNING: [Timing 38-282]` style IDs, `[HLS 200-...]`) mapped to human explanations; Vivado's `[Tool ID-Num]` message format makes this tractable.
- Python is the best fit if Ouroboros already parses GGUF in Python (gguf-py exists in llama.cpp) and needs numpy-based estimators; packaging via `uv tool install`/pipx or PyInstaller. Choose Go/Bubble Tea if single static binary on Windows is a priority. Ink only if the team wants to literally reuse Claude-Code-style components.

### Gaps
- No official Anthropic documentation page specifying Claude Code's UI internals beyond the Pragmatic Engineer interview; renderer details come from unofficial source analyses.
- Did not benchmark Windows-terminal behaviour (e.g., conhost vs Windows Terminal flicker) for each framework.

## Q6. Open-source FPGA build orchestrators/configurators to reuse

### Takeaway
Edalize (FuseSoC's backend) is the most directly reusable piece: it turns a tool-agnostic EDAM description into Vivado Tcl/Makefiles and has a Vitis HLS backend; LiteX shows a Python-first "generate everything, call Vivado in batch" pattern; hls4ml/FINN show the model -> HLS C++ -> IP -> bitstream pipeline closest to Ouroboros.

### Cited Findings
- FuseSoC uses Edalize to configure/run EDA tools; Edalize exposes a legacy "tool API" and a newer "flow API" (multi-tool flows such as synth -> P&R -> bitstream). — [FuseSoC docs 2.4.7: Understanding FuseSoC](https://fusesoc.readthedocs.io/en/stable/user/overview.html); [FuseSoC docs PDF](https://fusesoc.readthedocs.io/_/downloads/en/stable/pdf/)
- Edalize's Vivado backend translates EDAM into Vivado Tcl scripts and Makefiles; it is part of the legacy tool API being deprecated in favour of the flow API. — [edalize/vivado.py](https://github.com/olofk/edalize/blob/main/edalize/vivado.py); [DeepWiki: Edalize Vivado backend](https://deepwiki.com/olofk/edalize/4.2-vivado-backend); [EDAM API](https://edalize.readthedocs.io/en/stable/edam/api.html)
- Known Edalize Vivado limitation: VHDL generics not supported in the Vivado flow (issue). — [edalize issue #515](https://github.com/olofk/edalize/issues/515)
- hls4ml has Vivado (legacy Vivado HLS) and Vitis (Vitis HLS) backends; it generates projects + build scripts from model configs. — [hls4ml Vivado/Vitis backend](https://fastmachinelearning.org/hls4ml/backend/vitis.html); end-to-end FPGA-ML codesign example: [Fermilab MLPerf Tiny paper](https://lss.fnal.gov/archive/2022/conf/fermilab-conf-22-479-scd.pdf)
- FINN builds require Vivado/Vitis tools in its Docker environment (discussion of required "Xilinx Tools"). — [FINN discussion #1240](https://github.com/Xilinx/finn/discussions/1240)
- LiteX Windows/WSL2 + Vivado toolchain pitfalls. — [LiteX issue #1930](https://github.com/enjoy-digital/litex/issues/1930)

### Inferences
- Reuse plan: (a) borrow Edalize's idea of a declarative build description (EDAM-like YAML/TOML emitted by the configurator), (b) generate Vivado Tcl from Jinja templates (as Edalize/LiteX do) rather than string-concatenation, (c) borrow hls4ml's per-layer config (precision/reuse) concept for HLS parameter files, (d) borrow FINN's "build steps with checkpoints and resumability" structure, which maps naturally onto a step list in the TUI.
- hdlmake, Chipyard config system, F4PGA, tclstore were not researched in this session; F4PGA does not target Zynq UltraScale+ bitstreams in production (training knowledge), so it is not a substitute for Vivado on K26.

### Gaps
- No sources fetched for LiteX build internals, hdlmake, Chipyard's Scala config system, F4PGA, or tclstore; the writer should mark these as unresearched.
- Did not confirm whether Edalize currently ships a `vitis_hls`/`v++`-based HLS tool (vs only Vivado/Vivado HLS); verify in repo before planning reuse.
