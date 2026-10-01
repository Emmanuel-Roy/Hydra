Research and designs will go here.

## Designs (Phase 0, drafts for review)

| document | decides |
|---|---|
| [decisions.md](decisions.md) | the owner's decisions, and where they override the research |
| [board-contract.md](board-contract.md) | the only things the core and accelerator see of a board: memory-port streams, an MMIO window, interrupts, clocks, a trace stream |
| [platform-generator.md](platform-generator.md) | how everything board-specific is generated from the Vivado/Vitis platform specification, and what it produces |
| [lockstep.md](lockstep.md) | how the core is held to DoomV: Sail's trace format, strict and lenient modes, three levels from C simulation to the board |
| [hls-coding-standard.md](hls-coding-standard.md) | how a CPU is written in HLS: the hand-scheduled II=1 pipeline, stalling state machines, many small tops joined by streams |

The research behind them is in [`agentic/reports/`](../agentic/reports/).
