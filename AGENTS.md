# Working on Ouroboros

Rules for anyone -- person or agent (Claude Code, Codex) -- changing this repo.
The README says what Ouroboros is; this says how to work on it.

## Phase

**Research and setup. No code yet.** Research notes, reports, designs and
repository structure only, until the owner says otherwise.

## Targets

- **The Kria KV260 is the first target, and the design must stay as portable
  as possible.** Nothing outside a board's own folder may assume the KV260:
  board specifics (pins, clocks, memory controller, boot flow, peripherals)
  live under `FPGA-Hardware/boards/<board>/`, behind interfaces the core and
  the accelerator do not see past. The core, the accelerator and the tools
  take the board as a parameter. A second board should be a new folder, not
  a fork.
- **No software on the FPGA's hard CPU cores.** The RISC-V core is the only
  processor the system uses. Where a vendor platform cannot come up without
  its hard cores doing something (memory controller bring-up, configuration),
  that is a board-layer detail, kept as small as it can be and documented in
  that board's folder.
- **One hart, RVA23S64.** Simple pipeline, stalls for hazards. V with
  VLEN=128 and a configurable datapath width.

## Verification

- **Sail is the reference of record; DoomV is how the hardware meets it.**
  DoomV (`Tools/Verification/DoomV`) matches Sail instruction by instruction.
  The core is checked against DoomV in lock-step. Where the specification
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
| board-specific hardware | `FPGA-Hardware/boards/<board>/` |
| laptop physical hardware | `Hardware/` |
| software (configurator, tools) | `Source/` |
| measured runs | `Performance/` |
| models for the accelerator | `gguf/` |

## Submodules

Pinned, never vendored. `git submodule update --init` gets them; DoomV's own
submodules (Sail, Linux, ...) are fetched only as needed -- see
`Tools/Verification/README.md`. Bump a pin in its own commit, saying why.
