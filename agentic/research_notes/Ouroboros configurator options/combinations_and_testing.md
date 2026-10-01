# Making every Hydra option combination build and work together: constraint modelling, validation, combinatorial testing

Scope: how Ouroboros' configurator "Hydra" (RISC-V core profile/vector/caches/FPU/H, LLM systolic accelerator, per-interface I/O, multiple AMD FPGAs, Linux/OpenSBI options; Vitis HLS C++; lock-step against an ISS) can make a large option space build and work together when one build takes hours. Evidence and recommendations are kept apart: "Cited Findings" lists sourced facts only, and "Inferences" holds recommendations for Ouroboros. Research date: 2026-10-01. About 20 tool calls were used, so some areas are under-sourced; see the Gaps sections.

## 1. Modelling the option space (feature models, Kconfig, solvers, explanations)

### Takeaway
Kconfig-style `select` is a known trap: it forces values and skips dependency checks. A declarative constraint model (SAT/SMT/CP-SAT), where every rule is guarded by a named literal, gives sound validation and readable "impossible because..." explanations through unsat cores and assumptions. Hydra's ISA side already has an authoritative dependency source in the ratified RVA23 profile.

### Cited Findings
- Kconfig `select` "will force a symbol to a value without visiting the dependencies". Misusing it lets you select FOO even when FOO depends on an unset BAR. Guidance: use select only for non-visible symbols with no dependencies — [Linux Kconfig Language docs](https://www.kernel.org/doc/html/latest/kbuild/kconfig-language.html); [Zephyr Kconfig tips](https://docs.zephyrproject.org/latest/build/kconfig/tips.html)
- When a symbol's dependencies change, every symbol that selects it (directly or indirectly) needs updating too. Liberal `select` hides how symbols get enabled because it acts non-locally — [Zephyr Kconfig tips](https://docs.zephyrproject.org/latest/build/kconfig/tips.html)
- `imply` is a weak reverse dependency. Like select it sets a lower bound, but the user or an unmet dependency can still set the implied symbol to n — [Linux Kconfig Language docs](https://www.kernel.org/doc/html/latest/kbuild/kconfig-language.html)
- Known pitfall: `imply` can produce an unmet direct dependency when the implied symbol depends on m, and Kconfig never prints the "unmet direct dependencies" warning in that case — [linux-kbuild patch discussion "kconfig: make 'imply' obey the direct dependency"](https://www.spinics.net/lists/linux-kbuild/msg24741.html)
- The kernel keeps a document on select breaking dependencies — [Kconfig.select-break](https://www.kernel.org/doc/Documentation/kbuild/Kconfig.select-break)
- Abal, Brabrand & Wąsowski (ASE 2014) studied 42 variability bugs from Linux bug-fix commits. Variability bugs were not tied to specific bug types, error-prone features or code locations, but variability significantly increased bug complexity — [Semantic Scholar entry](https://www.semanticscholar.org/paper/42-variability-bugs-in-the-linux-kernel:-a-analysis-Abal-Brabrand/d2c4575fcfb45cd3a261b5895d2f8f2be02474f0)
- In a 135-fault corpus, Medeiros et al. found that configuration constraints are "rarely documented". When constraints are present, sample sets are often larger and precomputed covering-array tables cannot be used. Taking constraints into account "increases the time of analysis significantly", which ruled out some algorithms such as three-wise — [Medeiros et al., ICSE 2016, arXiv:1602.02052](https://arxiv.org/pdf/1602.02052)
- CP-SAT finds the root cause of infeasibility through assumptions: add enforcement literals to constraints (`OnlyEnforceIf(b)`) and pass them as assumptions. On infeasibility, `sufficient_assumptions_for_infeasibility` returns a subset of the assumptions, which identifies the conflicting constraints — [CP-SAT Primer, parameters](https://d-krupke.github.io/cpsat-primer/parameters.html); [OR-Tools troubleshooting doc](https://fossies.org/linux/or-tools/ortools/sat/docs/troubleshooting.md)
- Limitations: objectives and assumptions are incompatible in CP-SAT. In settings that are not fully supported, the returned core may contain all the assumptions, so it is not minimal — [CP-SAT Primer](https://d-krupke.github.io/cpsat-primer/parameters.html); [or-tools-discuss "Assumptions"](https://groups.google.com/g/or-tools-discuss/c/qlVv2uSq1uo)
- In SAT-based configuration, an UNSAT core (an unsatisfiable subset of CNF clauses) identifies which restrictions cause an illegal combination. A patent covers explaining illegal combinations in combinatorial models — [USPTO 8914757](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/8914757); research on producing minimal, human-friendly explanations through unsatisfiable-subset optimisation: [Gamba/Bogaerts/Guns, arXiv:2105.11763](https://arxiv.org/pdf/2105.11763)
- RVA23 (ratified profile v1.0, 2024-10-17) makes V mandatory in RVA23U64, along with Zvfhmin, Zvbb and Zvkt. H is mandatory in RVA23S64, and Sha captures the full set of features required with H. Zicsr is mandatory, although F implies it. RVA23U64 has 39 mandatory extensions — [RVA23 Profiles (RISC-V ratified library)](https://docs.riscv.org/reference/rva23/v1.0/rva23-profiles.html); [riscv-profiles source](https://github.com/riscv/riscv-profiles/blob/main/src/rva23-profile.adoc)
- The RISC-V Unified DB publishes machine-readable profile and extension data, including RVA23 release PDFs generated from it — [riscv-unified-db RVA23 release](https://riscv-software-src.github.io/riscv-unified-db/pdfs/RVA23ProfileRelease.pdf)
- Numeric features: Munoz, Oh, Pinto, Fuentes & Batory (SPLC 2019) treat uniform random sampling over feature models that have numerical features, which is relevant to PE counts, cache sizes and VLEN — [UT Austin PDF](https://www.cs.utexas.edu/ftp/predator/19SPLC.pdf)
- BDDs are used for variability analysis, including counting and uniform sampling — [bdd4va](https://github.com/rheradio/bdd4va)

### Inferences
- Recommendation: model Hydra as a typed constraint model in CP-SAT or Z3 instead of Kconfig. Use booleans for extensions and interfaces, bounded integers for VLEN, PE count, cache KiB, KV-cache size and clock, and linear constraints for resource budgets (sum of LUT/FF/DSP/BRAM/URAM estimates <= board capacity × headroom). Give every rule its own enforcement literal carrying a human-readable message. When a user's choices make the model infeasible, solve with the user's choices as assumptions and map the returned core to "X is impossible because rule R1 (RVA23 requires V) and rule R2 (V with VLEN=512 exceeds KV260 DSP budget)". Because assumptions and objectives conflict in CP-SAT, run a separate feasibility-only solve for explanations.
- If Kconfig is kept for the Linux/OpenSBI parts (it is native there), keep Hydra's own options out of Kconfig. Generate the kernel `.config` fragment from the Hydra model so the `select`/`imply` pitfalls never reach the hardware layer. Then run `make olddefconfig` and check that the requested symbols survived, because Kconfig silently drops unmet ones.
- Encode ISA implications (F→Zicsr, D→F, V→Zve*, H→S-mode, RVA23→{V, H, ...}) from the RVA23 spec or the Unified DB, not by hand, so the model follows the ratified source.

### Gaps
- I did not fetch primary sources on FeatureIDE, the KconfigReader/Kclause semantics studies, eCos CDL, or answer set programming (clingo) for configuration. Their claims are not sourced here.
- No source found that compares CP-SAT and Z3 on interactive configuration latency at Hydra's scale (about 50–200 options).

## 2. Validation before building (static checks, analytic estimation, C-sim, proxies)

### Takeaway
Mature FPGA ML flows (FINN, hls4ml) reject or reshape configurations with analytic or fitted cost models before synthesis, then refine with HLS estimates and full synthesis. That three-tier estimate → HLS → synth ladder is the documented pattern.

### Cited Findings
- FINN's `AnnotateResources` annotates per-node FPGA resources in three modes: "estimate" (analytic), "hls" (HLS report) and "synth" (post-synthesis). `AnnotateCycles` annotates estimated cycles per node — [FINN fpgadataflow transformations](https://finn.readthedocs.io/en/latest/source_code/finn.transformation.fpgadataflow.html)
- FINN's LUT/BRAM/DSP cost models are empirically fitted to hardware implementations and feed its design-space search — [FINN-R, arXiv:1809.04570](https://arxiv.org/pdf/1809.04570)
- FINN `DeriveCharacteristic` runs per-node RTL simulation to get I/O characteristic functions, and `DeriveFIFOSizes` uses them to size FIFOs. Interface buffering is derived by simulation rather than guessed — [FINN fpgadataflow transformations](https://finn.readthedocs.io/en/latest/source_code/finn.transformation.fpgadataflow.html)
- FINN added a builder check that folding is configured before hardware build outputs are produced, so invalid configs fail early — [Xilinx/finn PR #1665](https://github.com/Xilinx/finn/pull/1665)
- Chipyard builds the RTL simulator once and runs the riscv-tests ISA suites and benchmarks against that binary, so test changes do not retrigger the simulator build — [Chipyard docs / Software RTL Simulation](https://github.com/ucb-bar/chipyard/blob/main/docs/Simulation/Software-RTL-Simulation.rst)
- Variability-aware analysis such as TypeChef can cover the whole configuration space without sampling for some fault classes, mostly syntax and type errors. Setup difficulty and narrow fault classes limit it — [Medeiros et al. 2016](https://arxiv.org/pdf/1602.02052)

### Inferences
- Recommendation: use a validation ladder ordered by cost, with each stage gating the next.
  1. Constraint-model check (ms).
  2. Analytic resource/II/Fmax model per component, fitted from past builds as FINN does (ms).
  3. Generate the HLS C++ and compile it with g++/clang under every `constexpr` configuration. Template instantiation errors and `static_assert`s catch interface mismatches (seconds).
  4. HLS C-simulation of each component against golden vectors, plus a short ISA lock-step run against the emulator on a C++ model of the core (minutes).
  5. `csynth` only, reading HLS resource/latency estimates (tens of minutes).
  6. Full Vivado implementation (hours), only for configurations that pass 1–5.
  
  Feed the results of steps 5 and 6 back to recalibrate step 2's coefficients.
- Because Hydra generates HLS C++, C-sim plus lock-step is the cheap functional proxy for "works together". Synthesis is only needed for the "fits and meets timing" question.

### Gaps
- I found no published accuracy figures for FINN or hls4ml analytic resource estimates against post-place-and-route results, and no figures on how well Vitis HLS csynth estimates predict post-implementation utilisation and timing.
- No primary source fetched on Vitis HLS C-sim/co-sim cost.

## 3. Testing configurable hardware and software: industrial practice and sampling evidence

### Takeaway
Real projects do not test the whole space. They test a curated set of supported configurations (CVA6's "viable IP configurations", Chipyard's example configs, OpenTitan's single top) and add random sampling (Linux randconfig). Research evidence: pairwise coverage catches most interaction faults (about 92% of 135 faults; 97% of failures in NIST studies when combined with 1-way), cheap heuristics such as most-enabled/most-disabled are the most efficient, and 4- to 6-way coverage is needed to approach 100%.

### Cited Findings
- **Medeiros, Kästner, Ribeiro, Gheyi, Apel (ICSE 2016)**: 10 sampling algorithms compared on 135 known configuration-related faults in 24 open-source C systems. Faults detected (of 135) and samples per file:

  | Algorithm | Faults found | Samples/file |
  |---|---|---|
  | statement-coverage | 90 | 1.3 |
  | most-enabled-disabled | 105 | 1.3 |
  | one-enabled | 107 | 1.7 |
  | one-disabled | 108 | 1.7 |
  | random | 124 | 2.6 |
  | pairwise | 125 | 1.8 |
  | 3-wise | 129 | 2.5 |
  | 4-wise | 132 | 3.7 |
  | 5-wise | 135 | 6.0 |
  | 6-wise | 135 | 10.0 |

  6-wise sampled more than 500K configurations across all projects. About 84% of faults are triggered by enabling or disabling one or two options, but some need up to seven. Simple small-sample algorithms such as most-enabled-disabled were the most efficient in many scenarios, and some combinations of algorithms gave a good balance. These are results under favourable assumptions (no constraints, per-file). Adding constraints, header files, build-system information and global analysis changed rankings substantially and made some algorithms impractical — [arXiv:1602.02052](https://arxiv.org/pdf/1602.02052); [ACM DL](https://dl.acm.org/doi/10.1145/2884781.2884793)
- Corpus fault types: syntax errors 34%, memory leaks 22%, null-pointer dereferences 17%, uninitialised variables 13%, and smaller shares of others — [Medeiros et al.](https://arxiv.org/pdf/1602.02052)
- **NIST interaction rule (Kuhn et al.)**: most failures come from one or two parameters, with progressively fewer needing 3 or more. In the cited datasets, 66% of failures were triggered by a single value, 97% by 1- or 2-way combinations and 99% by up to 3-way. Pairwise finds 50% to more than 90% of faults depending on the system. Detection reached 100% at 4- to 6-way interactions. The most complex FDA medical-device failure needed a 4-way interaction — [Kuhn, "Combinatorial Testing: Rationale and Impact" (NIST)](https://csrc.nist.gov/CSRC/media/Presentations/Combinatorial-Testing-Rationale-and-Impact-Presen/images-media/kuhn-icst-14.pdf); [Kuhn/Wallace/Gallo TSE preprint](https://csrc.nist.gov/CSRC/media/Projects/automated-combinatorial-testing-for-software/documents/kuhn-wallace-gallo-tse-preprint.pdf); [Estimating Fault Detection Effectiveness](https://tsapps.nist.gov/publication/get_pdf.cfm?pub_id=915440)
- **Tools**: NIST ACTS is based on the IPOG algorithm (the generalisation of IPO to t>2), has built-in constraint support, and reports more than 4000 users. Microsoft PICT is a greedy mixed covering array generator with logic-expression constraints, sub-models (different strengths for subsets of parameters), invalid values, weights and aliases. CoverTable is PICT-format compatible. NIST publishes precomputed covering-array tables, but they do not handle constraints — [Dagstuhl CP 2021 paper on covering arrays with constraints](https://drops.dagstuhl.de/storage/00lipics/lipics-vol210-cp2021/LIPIcs.CP.2021.12/LIPIcs.CP.2021.12.pdf); [NIST covering array tables](https://www.nist.gov/itl/math/nist-covering-array-tables); [covertable](https://github.com/walkframe/covertable); [Medeiros et al.](https://arxiv.org/pdf/1602.02052)
- **YASA** (Krieter, Thüm, Schulze, Saake, Leich, VaMoS 2020) is a scalable, configurable t-wise sampling algorithm with an open-source implementation in FeatureIDE. IncLing (Al-Hajjaji et al. 2016) is incremental pairwise sampling — [YASA paper](https://wwwiti.cs.uni-magdeburg.de/iti_db/publikationen/ps/auto/KrieterTS+20.pdf). A community-wide evaluation of t-wise strategies (Ferreira et al., JSS 2021) is a further comparison source — [JSS 2021 PDF](https://homepages.dcc.ufmg.br/~figueiredo/publications/jss2021ferreira.pdf)
- **Uniform random sampling**: Smarch (Oh, Gazzillo, Batory) aims to sample each valid configuration with equal probability so that standard statistics apply. Baital uses adaptive weighted sampling to improve t-wise coverage — [Munoz et al. SPLC 2019](https://www.cs.utexas.edu/ftp/predator/19SPLC.pdf); [Baital FSE 2020](https://www.cs.toronto.edu/~meel/Papers/fse20blm.pdf). Sample stability in CI is studied separately — [Stability of Product-Line Sampling in CI](https://dx.doi.org/10.1145/3442391.3442410)
- **Linux 0-day (Intel LKP / kernel test robot)**: from Oct 2019 to Aug 2022, 63% of its build-test configurations were `randconfig` (22,702), 15% allyesconfig, 7% defconfig and 7% allmodconfig. One random config reaches only 29.2% patch coverage on average, and ten random configs plateau at about 74.6%. `krepair` (Yıldıran et al., FSE 2024) repairs fast-building configs to cover the patch: 98.5% average patch coverage, builds 10.5× faster than allyesconfig, and changes fewer than 1.53% of settings for 99% of patches — [arXiv:2404.17966](https://arxiv.org/html/2404.17966v1). 0-day code: [intel/lkp-tests](https://github.com/intel/lkp-tests). Public BUILD SUCCESS reports list 130+ configs per tree across architectures — [LKML example](https://ratatoskr.run/lkml/2026/08/17355947)
- **CVA6**: highly configurable through SystemVerilog parameters. Because documenting and verifying every parameter combination is impractical, the project defines a set of "viable IP configurations" (for example `cv64a6_imafdc_sv39`), each a config package used as a CI regression target — [CVA6 requirements spec](https://cva6.readthedocs.io/en/latest/02_cva6_requirements/cva6_requirements_specification.html); [config_pkg example](https://github.com/openhwgroup/cva6/blob/master/core/include/cv64a6_imafdc_sv39_hpdcache_config_pkg.sv)
- **Chipyard**: example Rocket configs are kept in `RocketConfigs.scala`. CI moved from CircleCI to GitHub Actions and runs riscv-tests on prebuilt simulators — [Chipyard CHANGELOG](https://github.com/ucb-bar/chipyard/blob/main/CHANGELOG.md); [Rocket docs](https://chipyard.readthedocs.io/en/latest/generators/rocket/)
- **OpenTitan**: `topgen` expands a top-level Hjson description (for example top_earlgrey) into a top module, crossbars and templated peripherals. `ipgen` expands IP templates from Hjson parameters — [topgen docs](https://opentitan.org/book/util/topgen/index.html); [Top Earlgrey](https://opentitan.org/book/hw/top_earlgrey/index.html). A secondary source (not verified against primary) claims more than 40,000 nightly regression tests with coverage above 90% and a public DV dashboard — [DeepWiki lowRISC/opentitan](https://deepwiki.com/lowRISC/opentitan). Treat the number as unverified.

### Inferences
- Recommendation: use a three-tier test regime.
  - **Golden presets**: about 5–10 named configs, for example "KV260-RV64GC-minimal", "KV260-RVA23-full" and "KV260-LLM-balanced". Fully implement them, boot Linux on them and lock-step them on every release. This mirrors CVA6's viable configurations.
  - **Per-commit cheap sampling**: most-enabled and most-disabled, plus one-enabled/one-disabled, run only through validation ladder steps 1–4. Medeiros et al. found these the most efficient per sample.
  - **Nightly t-wise**: a constrained pairwise (later 3-wise) covering array from PICT or ACTS. Use PICT sub-models for higher strength inside tightly coupled groups, such as ISA extensions × vector width × FPU, and pairwise across groups. Run it through C-sim and lock-step every night. Rotate a small subset, for example 1–2 configs per night, through full implementation, plus one uniform random valid sample per night to catch faults that t-wise misses.
- Patch-targeted sampling in the style of krepair maps directly onto Hydra. When a commit touches the generator for option X, repair the nearest golden preset so that X is enabled and test that config, instead of relying on random configs. Random configs covered only about 29% of patches in Linux.
- The NIST and Medeiros evidence is for software. No source quantified interaction degree for hardware-generator faults, so treat the "pairwise catches about 90%" figure as a prior, not a guarantee.

### Gaps
- I did not fetch LiteX CI, KernelCI, OpenWrt buildbot or Rocket Chip regression practice from primary sources. The exact Chipyard CI config matrix was not retrieved.
- I found no published study that measures interaction-fault degree in parameterised hardware generators.
- OpenTitan's nightly-regression numbers come only from a secondary source.

## 4. Making builds compose (parameterised HLS, contracts, schemas, content-addressed caching, presets)

### Takeaway
The cited generators (OpenTitan ipgen/topgen, CVA6 config packages, Chipyard configs, FINN) treat a configuration as a versioned, declarative description that generates parameterised components. CVA6 explicitly pairs this with a small set of supported presets. I found no primary evidence on content-addressed caching keyed by configuration hash, so that part is a recommendation.

### Cited Findings
- OpenTitan describes each top in Hjson. `topgen` and `ipgen` expand parameterised IP templates from top-specific parameters, so a single declarative file drives generation — [topgen docs](https://opentitan.org/book/util/topgen/index.html)
- CVA6 captures each supported configuration as a SystemVerilog config package of localparams (RVF, RVD, A/B/C, AXI widths and others) selected at compile time — [cv64a6 config_pkg](https://github.com/openhwgroup/cva6/blob/master/core/include/cv64a6_imafdc_sv39_hpdcache_config_pkg.sv); [CVA6 requirements](https://cva6.readthedocs.io/en/latest/02_cva6_requirements/cva6_requirements_specification.html)
- In FINN, interface FIFO depths between dataflow components are derived (`InsertFIFO`, `DeriveFIFOSizes`), so components with different folding compose without deadlock or stalls — [FINN transformations](https://finn.readthedocs.io/en/latest/source_code/finn.transformation.fpgadataflow.html)

### Inferences
- Recommendation: one versioned configuration schema (JSON Schema or similar) with a `schema_version` field and migration functions. Canonicalise a configuration by sorting keys, filling defaults and normalising units. Hash the canonical config together with generator commit, Vitis/Vivado versions and part number. Then cache each HLS IP under `hash(component-relevant config subset + tool version)`, so a change to the I/O options does not re-synthesise the systolic array. Cache the Vivado block-design/implementation under the hash of the whole config. This is the Bazel/Nix content-addressing idea applied per IP.
- Express interface contracts as C++ types. Use AXI-Stream widths, datatypes and the PE tile shape as template parameters, with `static_assert`s at block boundaries, for example "accelerator datatype ∈ GGUF types supported by this PE build" and "AXI data width divides VLEN". Composition errors then show up in a seconds-long g++ compile rather than in hours-long synthesis.
- Recommended presets should be exactly the golden configurations from section 3, kept "always green". Sampled configurations are best-effort, and the UI should label them that way.

### Gaps
- I found no primary sources on HLS IP caching keyed by configuration hash, on Vivado incremental-implementation effectiveness, or on how far Vitis HLS reuse of unchanged IP across Vivado runs (out-of-context synthesis) cuts build time.

## 5. Failure handling and automatic fallback (timing or fit failures, DSE and auto-tuning)

### Takeaway
Existing tools fall back along known axes. FINN/hls4ml increase folding or reuse factor (fewer PEs, more cycles) until the design fits a target. Vivado tries several implementation strategies, guided by ML, to close timing. Hydra can chain both: re-fold first, then try strategies, then lower the clock.

### Cited Findings
- FINN `SetFolding` sets per-node parallelism (PE, SIMD) to meet a throughput target given as `target_cycles_per_frame`. Users can give `target_fps` in the build config instead of an explicit folding config. Folding trades frame rate against resources — [FINN docs / emergentmind summary](https://finn.readthedocs.io/en/latest/source_code/finn.transformation.fpgadataflow.html); [FINN-R](https://arxiv.org/pdf/1809.04570)
- hls4ml's per-layer `reuse_factor` sets how many times each multiplier is reused. A higher value folds computation in time to fit tighter resource budgets at the cost of latency and throughput. The "Latency" and "Resource" strategies choose between minimum latency and minimum resources. Configurations are given in Python/YAML globally or per layer, which allows sweeps — [hls4ml paper arXiv:2103.05579](https://arxiv.org/pdf/2103.05579); [hls4ml transformer paper arXiv:2409.05207](https://arxiv.org/pdf/2409.05207)
- Vivado has automated timing closure. Intelligent Design Runs (IDR) apply staged implementation strategies chosen by ML models, analyse the results and carry the most promising candidates forward. The flow is fully automated. ML strategy runs (up to 3 in parallel) follow QoR suggestions (`report_qor_suggestions`; the `AUTO_RQS` property) — [AMD Vivado implementation page](https://www.amd.com/en/products/software/adaptive-socs-and-fpgas/vivado/implementation.html); [Xilinx Adapt 2021 "Automated Timing Closure"](https://china.xilinx.com/publications/presentations/c_D2_03_Design_Closure_Automated_Timing_Closure.pdf); [BLT on IDR](https://bltinc.com/2025/04/16/timing-closure-vivado-intelligent-design-runs/)
- Third-party tools such as Plunify InTime search Vivado strategies and settings with ML across many runs — [InTime methodology whitepaper](https://www.plunify.com/en/wp-content/uploads/sites/8/2018/05/InTime-Timing-Closure-Methodology-for-Vivado-WP04.pdf)

### Inferences
- Recommendation: run the fallback as a constraint-model re-solve, not ad-hoc retries. After a failure, add the observed fact as a learned constraint, for example "PE=64 at 300 MHz fails on xck26", or recalibrate the estimator coefficients. Then ask CP-SAT for the nearest feasible configuration by minimising a weighted distance from the user's request. Order the fallbacks so that functional choices (ISA profile, datatypes) are never changed silently:
  1. Vivado strategy sweep or IDR at the same config.
  2. Reduce the accelerator PE count or re-fold (FINN/hls4ml style).
  3. Lower the clock target.
  4. Shrink caches or the KV cache.
  5. Ask the user.
  
  Report every substitution explicitly ("requested 64 PEs, built 48 because ...").
- Persist every build outcome (config hash → fit/timing/WNS/utilisation) as a dataset. It recalibrates the analytic estimator in section 2 and can eventually serve as a learned feasibility predictor, as FINN's fitted cost models do.

### Gaps
- I did not retrieve published success rates for Vivado IDR or ML strategies, or FINN SetFolding's exact search algorithm and parameters. The docs page fetched lacked them.
- No source found for an open tool that closes the loop from implementation failure back to automatic re-folding across a whole SoC (core plus accelerator). This appears to be a gap Hydra would fill.
