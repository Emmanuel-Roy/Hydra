# Working on Ouroboros

Rules for anyone -- person or agent (Claude Code, Codex) -- changing this repo.
The README says what Ouroboros is; this says how to work on it.

## Phase

**Research and setup. No code yet.** Research notes, reports, designs and
repository structure only, until the owner says otherwise.

## Targets

- **The stock Kria KV260 (its own carrier board) is the first target, and the
  design must stay as portable as possible.** No custom carrier board.
- **No board-specific code is written by hand.** Everything that depends on
  the target -- pins, clocks, memory map, DDR ports, PS configuration, boot
  image, device tree, resource budgets -- is *generated* from the platform
  specification Vivado and Vitis provide for that target (the board files,
  the exported hardware platform, the part's data). Supporting a board means
  pointing the generator at its platform, not writing files for it.
  `FPGA-Hardware/boards/<board>/` holds generated output, never hand edits.
  The core, the accelerator and the tools take the platform as input.
- **No software on the FPGA's hard CPU cores.** The RISC-V core is the only
  processor the system uses. Where a vendor platform cannot come up without
  its hard cores doing something (memory controller bring-up, configuration),
  that is generated from the platform too, kept as small as it can be, and
  ends before the RISC-V starts.
- **One hart, RVA23S64.** Simple pipeline, stalls for hazards. V with
  VLEN=128 and a configurable datapath width.
- **All hardware is C++ HLS.** The core, the accelerator and everything else
  in the FPGA are written in C++ for Vitis HLS, and the RTL is what Vitis and
  Vivado generate from it. No hand-written Verilog/VHDL/SystemVerilog, and no
  other HDL. Where HLS makes something hard (pipeline control, variable-latency
  memory), the answer is an HLS coding pattern, not a drop to RTL.

## Verification

- **Lock-step with DoomV is the target.** The core must run in lock-step with
  DoomV (`Tools/Verification/DoomV`), instruction by instruction; DoomV in turn
  matches Sail, the reference of record. Where the specification
  leaves a choice open and Sail makes one, the core makes the same one.
- **Deterministic.** Same inputs, same trace, every run, in simulation and on
  the board.
- Suites and how to get them: [`Tools/Verification/README.md`](Tools/Verification/README.md).

## Where things go

| what | where |
|---|---|
| research notes (raw, sourced) | `agentic/research_notes/<topic>/` |
| research reports (synthesised) | `agentic/reports/` |
| every bug found, and how it was resolved | `agentic/bugs/` |
| designs and decisions | `docs/` |
| generated per-board output (never hand-edited) | `FPGA-Hardware/boards/<board>/` |
| owner decisions | `docs/decisions.md` |
| laptop physical hardware | `Hardware/` |
| software (configurator, tools) | `Source/` |
| measured runs | `Performance/` |
| models for the accelerator | `gguf/` |

## Submodules

Pinned, never vendored. `git submodule update --init` gets them; DoomV's own
submodules (Sail, Linux, ...) are fetched only as needed -- see
`Tools/Verification/README.md`. Bump a pin in its own commit, saying why.
