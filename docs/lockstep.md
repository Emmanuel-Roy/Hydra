# Lock-step with DoomV

Status: **draft for review** (Phase 0). Decisions marked **[decide]** need the
owner.

The core runs in lock-step with DoomV: every instruction it retires, and every
trap it takes, is compared with DoomV's, one at a time, and the first
difference stops the run with both sides' state. DoomV matches Sail, so a core
that matches DoomV matches the reference of record. This document fixes what
the core reports, how it reaches DoomV at each level of the project, and what
DoomV needs that it does not have yet.

## The record is Sail's trace format

DoomV already lock-steps against a trace in **Sail's format** -- the one
`sail_riscv_sim --trace-instr --trace-gpr --trace-fpr --trace-vreg --trace-csr
--trace-mem --trace-exception --trace-interrupt` writes, and which DoomV's
`-lockstep=<trace>` reads ("Sail's, or an RTL testbench's in the same shape",
`src/lockstep.cpp`). Ouroboros adopts it unchanged. There is no Ouroboros
format to design, to keep in step with DoomV, or to translate: the core's
retirements are rendered as Sail trace records, and DoomV checks them exactly
as it checks Sail.

One record per retired instruction or trap, a header line and one line per
effect:

```
[83] [U]: 0x00000000800001BC (0x00113023)
mem[W,0x0000000080002000] <- 0x00AA00AA00AA00AA
x1 <- 0x0000000000000004
CSR mstatus (0x300) <- 0x8000000A00006080
```

What the core must therefore expose per retirement, at the top of its
retirement stage -- the RVFI set, plus what Sail prints that RVFI leaves out:

| field | from | notes |
|---|---|---|
| step number | a retirement counter | Sail's `[n]`; also the order check |
| privilege and V | the privilege register at retirement | `[M]`, `[S]`, `[U]`, `[VS]`, `[VU]` |
| pc, instruction bits | the retiring instruction | 16-bit encodings as fetched |
| X, F and V register writes | the write-back stage | every register written, with its new value; a vector write as the whole register |
| CSR writes | the CSR file | every CSR whose value the instruction changed, including the ones trap entry writes |
| stores | the store unit | physical address, width and data, one entry per store as Sail splits them (a page-crossing store is two) |
| trap | the trap unit | cause, tval, tval2 and tinst, the mode trapped from and to |
| interrupt | the trap unit | which interrupt, taken before which instruction |

Loads are not in Sail's trace and are not compared directly; a wrong load
shows up as a wrong register write. Device loads matter for the event log
below.

## What cannot be predicted, and the two modes

Two things decide values the instruction set does not: the **clock** (time
and counter reads, when a timer interrupt becomes pending) and **devices**
(what a UART or disk load returns, when a device raises an interrupt). DoomV
handles them in one of two modes, both already implemented:

- **Strict** (`-lockstep-strict`): everything is compared and nothing is taken
  from the other side. DoomV is held to Sail this way, by adopting Sail's
  platform: Sail's configuration (`rva23s64.json`), its clock (one `mtime`
  tick every two instructions, the WFI wait limit), its devices. A core run
  this way is deterministic and comparable to Sail directly.
- **Lenient** (default): counter and time reads, pending-interrupt state
  (`mip`, `sip`, the `topi`/`topei` registers, `hgeip`, `seed`), and loads from
  anything that is not RAM are taken from the core's record, and interrupts
  are taken where the core took them, checking that they were enabled there.
  The run reports how many values it took. This is how hardware with its own
  real-time timer and real devices is stepped.

**The core's clock** (decisions, 2026-10-01): the core runs on the FPGA's
clock, defined the same way in Vitis software emulation, hardware emulation
and on the physical FPGA. `mcycle` counts the core's clock cycles; `mtime` is
derived from that clock; the timebase in the device tree comes from the
platform's clock frequency. Since the core's pipeline is one loop iteration
per clock cycle ([hls-coding-standard.md](hls-coding-standard.md)), even
software emulation counts real cycles.

DoomV follows Sail's clock instead (one `mtime` tick per two instructions),
so the two disagree on what the clock decides, by design. Ouroboros's
lock-step is therefore **strict on everything except clock-decided values**:
counter and time reads, pending timer interrupts, and where interrupts are
taken come from the core's record, checked for being enabled there; every
other register, CSR, store and trap is compared strictly. That is DoomV's
lenient mode, restricted to the clock -- device loads are compared too
wherever the device is modelled on both sides.

**Where the modes can differ.** The cycle count of a run depends on memory
timing. Software and hardware emulation see the latencies their memory
models give; the physical board sees the PS DDR controller's, which can vary
between runs. So the same program can take a timer interrupt at a different
instruction on the board than in emulation. Each run is still reproducible:
the clock-decided values are logged (below) and DoomV replays them.

## Three levels, one record

| level | the core is | DoomV is | speed (report's estimates) | used for |
|---|---|---|---|---|
| **C simulation** (Vitis software emulation) | the HLS C++, compiled natively | linked into the same process | about 10^6-10^7 instructions/s | every change: riscv-tests, riscv-vector-tests, arch-test, riscv-dv seeds, Linux and Ubuntu boots |
| **RTL simulation** (Vitis hardware emulation) | the Verilog Vitis/Vivado generate, in XSim or Verilator | reading the trace the testbench writes | kHz | short directed tests on every synthesis: does the generated RTL do what the C++ did |
| **on the board** (hardware) | the bitstream on the FPGA | offline, replaying a recorded log | full speed; comparison offline | milestone boots; bisecting a divergence |

**C simulation is the main level**, and the reason the all-HLS rule helps
verification: the C++ that becomes the hardware can be stepped against DoomV
through a whole Ubuntu boot at software speed. Its limit is that it proves
only the C++; scheduling, stream depths and free-running behaviour are
checked by the RTL level, which is therefore mandatory on every synthesis.

**On the board**, the host link (the KV260's USB-UART/JTAG) cannot carry a
record per instruction. The core writes instead, into a ring buffer in DDR:

1. a running hash of its records, emitted every N instructions;
2. in full, every value lenient mode would take from it -- time and counter
   reads, device loads, interrupts with the instruction they came before.

DoomV replays the log offline: it takes the logged values where the core took
them and checks the hashes. A mismatching interval is re-run, from a
snapshot, with full records around it. No published project has lock-stepped
a full Linux boot over a link like this, so this part is a design to prove in
Phase 2, not a known technique.

## Starting points: snapshots

Both sides start from the same machine state, not from a program loaded
through a debug path (Dromajo's experience: loading through the debug module
caused false mismatches). DoomV's snapshots (`-snapshot`, `-restore`) are that
format already. A run can start at reset, or from a snapshot taken by DoomV --
for example, Ubuntu booted to its desktop -- loaded into the core's memory
and registers.

## What DoomV needs

DoomV's lock-step reads a trace file, which suits the RTL level. The others
need more:

| need | for | status |
|---|---|---|
| Sail-format trace reader, strict and lenient | RTL level | **exists** |
| snapshots | common starting points | **exists** |
| an in-process API: reset or restore, then compare one record at a time | C simulation at full speed (no text, no file) | to build |
| replay of a value log: take this time/counter value, this device load, this interrupt before step N | board level, and lenient runs being reproducible | partly: lenient mode does this from a full trace; a compact log format is to build |
| hash checkpoints every N steps | board level | to build |
| loading a snapshot into the core | starting the core from a booted state | to design with the board contract |

These are DoomV changes, made in the DoomV repository and pinned here.

## Open

- Whether the board's memory latency can be made run-to-run constant (for
  example a fixed-latency adapter), which would make board runs repeat
  cycle-for-cycle and not only replayably.
- A DoomV mode that is lenient on clock-decided values only, rather than on
  devices and pending-interrupt state as well.
- The record's binary form inside the core and on the trace stream (the
  rendering to Sail text happens outside the hardware).
- Vector register writes are 128 bits each; whether the stream carries whole
  registers or only changed ones is a stream-width question for the board
  contract.
