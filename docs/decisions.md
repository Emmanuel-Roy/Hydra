# Decisions

The owner's decisions, newest first. Where one overrides a research report in
`agentic/reports/`, it says so; the report itself is left as written.

## 2026-09-30

**Stock KV260 carrier board, no custom carrier.** Overrides the feasibility
report's recommendation of a custom K26 carrier as the long-term route for
peripherals and the laptop build ("Off-the-shelf parts make a $460-650
laptop"; phase 7). Peripherals come from the stock board.

**No board-specific code written by hand; it is generated from the platform
specification Vivado and Vitis provide.** Overrides the report's board layer of
hand-written files in `FPGA-Hardware/boards/kv260/` ("The PS is unavoidable
plumbing, so confine it to one folder"; phase 2). The board contract the report
describes -- memory-request streams, an MMIO window, interrupt lines, clock and
reset, a trace stream -- still stands; what changes is that everything behind it
(block design, constraints, memory map and DDR ports, PS configuration, boot
image and its FSBL, device tree, resource budgets) is produced by a generator
from the target's board files, exported hardware platform and part data. A new
target is a new platform given to the generator.

**Lock-step with DoomV is the verification target.** The core runs in
lock-step with DoomV, which matches Sail.

**All hardware is C++ for Vitis HLS; Vivado produces the RTL.** No hand-written
HDL. The report's HLS risks are to be met with HLS coding patterns.

**No code yet.** Research and repository setup only, until the owner says
otherwise.

**The KV260 is the first target, and everything must be as portable as
possible.**

## Open

- **riscv-formal.** It checks the core's retirement port through a
  SystemVerilog wrapper. The report reads that wrapper as test bench, not
  hardware, and so allowed under the all-HLS rule. Not yet confirmed.
