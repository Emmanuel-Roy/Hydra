# HLS coding standard

Status: **draft for review** (Phase 0).

All hardware is C++ for Vitis HLS; Vivado produces the RTL. No hand-written
HDL. (riscv-formal's SystemVerilog wrapper is allowed, for testing only.)
No published Linux-capable CPU has been written in HLS (feasibility report),
so these rules are the project's answer to that risk, taken from the HLS cores
that did work -- Comet, HL5, Goossens's.

## 1. The pipeline is written out, never discovered

HLS schedules for the worst case: an ISS-style `fetch; decode; execute` loop
cannot reach one instruction per cycle (II=1) because of register-file hazards
and the next-pc dependency, which force II of 3 or more.

- The core's pipeline is **one loop body at II=1** that runs every stage each
  iteration, with **explicit stage registers** (a struct per stage boundary).
- Each iteration computes **one stall vector first** -- cache miss, load-use
  hazard, busy multi-cycle unit -- then updates only the unstalled stage
  registers.
- **Forwarding** compares register indices explicitly.
- Stages are processed **in reverse order** (write-back first), so no
  dependency crosses iterations by accident.
- False dependencies the tool cannot see through (the pc written in execute
  and read in fetch) are removed by hand.

## 2. Multi-cycle work is a state machine that stalls

A `for` loop inside the pipeline makes the tool assume its worst-case latency
for the whole body. The divider, the FPU's long operations, cache refills,
page walks and the vector unit's slow sequences (vrgather, segment loads,
div/sqrt, FP64 reductions) are **state machines with one state per cycle**
that raise stall until done. RVA23 requires these to work, not to be fast.

## 3. Many small tops, joined by streams

Synthesising a core and its FPU together was slower to build and larger than
synthesising them apart (Comet). The core is therefore several HLS top
functions, each its own Vivado IP:

- the integer pipeline, with the CSR file and trap unit;
- the FPU;
- the vector unit, its datapath width a template parameter;
- the MMU and page-table walker;
- the cache and the bridge to the contract's memory ports;
- the uncore (timer, interrupt controller, UART);
- the accelerator's units.

They connect through `hls::stream` (AXI4-Stream once synthesised), in a
generated block design. Vivado writes the wrapper.

## 4. Ports

- Free-running tops (`ap_ctrl_none`), so the core runs without a host
  starting it. Co-simulation supports these only for combinational designs,
  II=1 pipelines or stream ports -- so the core's **only ports are streams**
  and level inputs (interrupts).
- **No `m_axi` inside the pipeline.** Memory is a request/response stream to
  the cache/bridge top; `m_axi` appears only there, and in generated adapters.

## 5. Parameters come from outside

Everything that varies by configuration or board is a **template parameter**
or `constexpr` from a generated header: the vector datapath width, VLEN,
cache and TLB sizes, memory windows, port counts and widths, clock source.
No board constant appears in the sources ([platform-generator.md](platform-generator.md)).

## 6. The C++ is the first simulator

- Every top must build **natively** (ordinary compiler, no HLS tool) and run
  in C simulation in lock-step with DoomV ([lockstep.md](lockstep.md)). If it
  cannot, it is not done.
- No behaviour may exist only in pragmas or only in the generated RTL; what
  the C++ does is what the hardware must do.
- **Deterministic:** no uninitialised state, no dependence on host timing or
  iteration order of unordered containers.
- Every synthesis is followed by an RTL co-simulation of short directed tests,
  because C simulation cannot see scheduling, stream depths or free-running
  behaviour.

## 7. The tools

- One pinned AMD release per project release; builds refuse any other.
- Command line only: `v++ -c --mode hls` for synthesis, `vitis-run --mode hls`
  for C-sim, co-sim and packaging, Vivado in batch mode.
- Directives that change between releases are kept in one generated config
  per top, not scattered as pragmas, so a release change is one place.

## Open

- Whether a single II=1 loop scales to an RV64 pipeline with a full CSR file,
  precise traps and two-stage translation. There is no precedent; Phase 2
  synthesises a toy RV32I pipeline in this style on the KV260 to measure HLS's
  LUT and Fmax cost before the real core is written.
