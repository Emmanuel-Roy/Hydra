# Ouroboros: from a model to a bitstream

Status: **draft for review** (Phase 0). The owner's flow (decisions,
2026-10-01); the options asked in step 4 are the subject of
[`agentic/reports/Ouroboros configurator options.md`](../agentic/reports/) and,
once settled, `configurator.md`.

## The flow

You run Ouroboros. A full-screen terminal UI opens -- in the style of Claude Code:
rich text, a live task list, progress bars, the current step always visible.

| step | what happens | what you see |
|---|---|---|
| **1. Model** | Ouroboros looks in `gguf/` for `.gguf` files. One: it is proposed. Several: you pick. None: it asks you to open one. It reads only the header -- architecture, dimensions, context length, the quantization type of every tensor -- not the weights. | the model's name, size, parameter count, quantization mix, context length |
| **2. Target** | Ouroboros lists the targets saved in `FPGAs/` and, below them, every board and platform in the library installed with Vivado and Vitis (the pinned 2026.1 has 45 boards and 8 Vitis platforms), searchable. Picking one from the library saves it to `FPGAs/`. If the board is attached and identifiable, it is preselected. | each target's part, resources (LUT, FF, DSP, BRAM, URAM), memory and bandwidth, and its interfaces |
| **3. Recommendation** | From the model and the target, Ouroboros computes a recommended configuration: core profile, vector width, accelerator size and datatypes (built around the `.gguf`'s quantization), KV cache and context, I/O, clocks. | the configuration, why each choice was made, and its estimates: resources with headroom, decode and prefill tokens/s, memory left for Linux, build time |
| **4. Configuration** | Ouroboros walks you through the choices: the questions always asked (faster CPU or faster array, RVA23 or less, wide vector unit, big KV cache, many PEs, decode or prefill, which I/O, rebuild Linux/OpenSBI or not), then, if you want them, the expanded and full selections. Every change re-runs the estimates and the compatibility checks at once; an impossible combination says why. | the recommended value and yours, side by side; estimates updating live |
| **5. Plan** | Before anything long starts: what will be built, what changed from the recommendation, the estimates, and how long the build should take. You confirm. The configuration is saved, so the same build can be re-run without the questions. | a summary to accept, edit or cancel |
| **6. Generate** | Ouroboros generates every file the build needs: the HLS sources' parameters, the platform files from the target's specification (block design, constraints, memory map, boot image description, device tree), and, if chosen, the OpenSBI/Linux configuration. | a checklist of generated files |
| **7. Synthesise and implement** | Vitis HLS synthesises each component; Vivado builds the block design, synthesises, places, routes, and writes the bitstream; then the boot image. Lock-step accuracy runs alongside when asked for. | a live task list with a progress bar per stage, elapsed and remaining time, the current phase of each tool, warnings as they appear; a failure says which stage, why, and which choice most likely caused it |
| **8. Result** | The bitstream and boot image, and a report: resources used against the estimate, achieved clock, timing, accuracy results. | where everything is, and the next command to run |

## Where things go

### `FPGAs/` -- the targets

The targets you have used, one folder each; any board or platform in the
Vivado/Vitis library can be picked and is saved here when it is. A target folder holds the target's **platform
specification** as Vivado and Vitis provide it, or a pointer to it -- never
hand-written board code (decisions, 2026-09-30):

```
FPGAs/
  kv260/
    target.toml        which board-store entries (the KV260's kv260_som and
                       kv260_carrier ship with Vivado), or which exported
                       hardware platform (.xsa), describe this target
```

Ouroboros reads everything else -- part, resources, interfaces, memory, clocks --
from that specification. Adding a target is adding a folder that names its
platform.

### `build/` -- every build

Each build gets its own folder, named for the target and when it started:

```
build/
  KV260-2026-10-01_14-32-05/
    config.toml        the configuration, as chosen; re-runs this build exactly
    plan.md            what step 5 showed
    report.md          what step 8 showed, plus report.json
    logs/              every tool's full output
    generated/         every generated source: HLS parameters, block-design Tcl,
                       device tree, boot image description
    vitis/             each HLS component's synthesis, simulation and packaged IP
    vivado/            the project, checkpoints, and utilization and timing reports
    xdc/               the generated constraints
    boot/              FSBL, boot image description, BOOT.BIN (where the target needs one)
    software/          OpenSBI and Linux builds, when chosen
    bitstreams/        the final bitstream (and .bin for flash)
```

Nothing in `build/` is committed; the folder name and `config.toml` are enough
to reproduce a build.

## Progress

Long stages report progress the tools themselves expose:

- **Vitis HLS**: its synthesis steps (C compile, scheduling, binding, RTL
  generation, packaging), one bar per component; components run in parallel.
- **Vivado**: synthesis, then implementation's phases (opt, place, phys-opt,
  route), then bitstream -- each a sub-bar, from the phase markers in the log.
- **Lock-step**: tests done of tests total, per suite.

Every bar shows elapsed time and an estimate of what remains, from the last
comparable build when there is one. The full log of every tool is always in
`logs/`, so the screen can stay readable.

## Built on

- the pipeline in `scripts/pipeline.py` -- the same stages, reports and
  regression checks, driven by Ouroboros's configuration instead of
  `pipeline.toml`;
- the platform generator ([platform-generator.md](platform-generator.md));
- the I/O catalogue ([io-catalog.md](io-catalog.md)) for step 4's I/O list;
- lock-step with DoomV ([lockstep.md](lockstep.md)) for accuracy.

## Open

- The UI toolkit (the earlier research recommends Python with Rich or Textual,
  matching the pipeline's language).
- How Ouroboros identifies an attached board (step 2).
- Whether the `.gguf` folder is `gguf/` only, or also other folders the user
  points at.
