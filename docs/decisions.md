# Decisions

The owner's decisions, newest first. Where one overrides a research report in
`agentic/reports/`, it says so; the report itself is left as written.

## 2026-10-01

**The program is called Ouroboros.** The repository README's "Hydra" is
renamed; notes written before this may still say Hydra.

**The flow, and where things go** ([ouroboros-flow.md](ouroboros-flow.md)).
Run it; a rich terminal UI opens; it finds a `.gguf` in `gguf/` or asks for
one; it asks for the target; it walks through the configuration with a
recommendation from the `.gguf`; it generates the files, synthesises in Vitis
then Vivado and writes the bitstream, with live progress bars. Every build
goes to `build/<FPGA-name>-<date-time>/`, with folders for the Vitis files,
the Vivado files, the XDCs and the rest, and the bitstream in `bitstreams/`.

**Targets are read from Vitis, not kept in the repository.** No `FPGAs/`
folder: the program reads the families, devices, boards, memory and I/O from
the pinned Vitis installation and asks the user -- which family, which FPGA
(board or device), and so on (docs/ouroboros-flow.md). Supersedes the
`FPGAs/` folder of the flow as first written.

**Ouroboros aims to use 100% its own IP.** All logic is Ouroboros's HLS. The
silicon itself -- the PS, clock managers, I/O primitives, transceivers, hard
blocks -- is reached through the thinnest generated wrapper, with no vendor
logic around it. Vendor soft IP is allowed only as a listed stopgap with its
replacement planned (today only MIG, for DDR on boards without a PS); licensed
IP is never used. Answers the two questions `io-catalog.md` had left open.

**A variety of I/O to build around, for any FPGA.** Ouroboros supports a broad
catalogue of interface types, organised by what drives them, so the generator
finds support for most of what any board offers
([io-catalog.md](io-catalog.md)). "Any FPGA" means any AMD part the pinned
Vivado/Vitis release targets, since the toolchain is AMD's.

**Every I/O the platform shows is discovered, and each can be enabled or
disabled.** Not only the display: USB, Ethernet, SD, QSPI, the cameras (MIPI
CSI-2, the AP1302 ISP, USB cameras), Pmod and GPIO. The generator produces
each enabled interface's path from what drives it; a disabled interface
generates nothing, and its resources go to the systolic array's budget
([platform-generator.md](platform-generator.md), "Every interface is a
switch").

**The generator discovers the display and drives it.** It must see from the
platform specification that the KV260 has an HDMI output, generate the code
for it, and the system outputs through it. Since the KV260's HDMI is driven
by the PS DisplayPort controller, the generated path is: PS configuration for
that controller's fabric video input, the uncore's HLS display engine
feeding it, and the controller's set-up run on the RISC-V
([platform-generator.md](platform-generator.md)).

**Sail and DoomV use the Vitis simulation clock.** In lock-step, the
references take their clock from the simulation the core runs in: each
retirement carries the core's cycle count, and DoomV and Sail derive `mtime`
and `mcycle` from it instead of from their own instruction-counted clock (one
tick per two instructions). Time, counter reads and timer interrupts are then
compared strictly, like everything else. Refines the entry below, which had
made clock-decided values the core's to report. For Sail this changes how its
C emulator is driven, not the model; it is an exception, for Ouroboros, to
DoomV's rule of running Sail with its configuration unmodified.

**The core's clock is the FPGA's clock, in every mode.** Vitis software
emulation, hardware emulation and the physical FPGA all run the core on the
same clock definition: `mcycle` counts the core's clock cycles, `mtime` is
derived from that clock, and the timebase the device tree advertises comes
from the platform's clock frequency. Supersedes the proposal in
`lockstep.md` to give verification builds Sail's instruction-counted clock.
Consequence: lock-step against DoomV is strict on everything except values
the clock decides (counter and time reads, pending timer interrupts and where
they are taken), which come from the core's record -- DoomV's lenient mode.

## 2026-09-30

**riscv-formal's SystemVerilog wrapper is allowed, for testing only.** It checks the core's retirement port and is never part of the hardware; the all-HLS rule covers everything that is.

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
