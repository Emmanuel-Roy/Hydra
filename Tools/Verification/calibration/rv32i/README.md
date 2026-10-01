# Calibration core: RV32I in the coding standard's style

**Test infrastructure, not Ouroboros hardware.** A five-stage RV32I pipeline
written as [`docs/hls-coding-standard.md`](../../../../docs/hls-coding-standard.md)
asks -- one loop at II=1 whose body is a clock cycle, explicit stage
registers, write-back evaluated first, a stall computed before any stage
register updates, forwarding by register index, a two-cycle flush on a taken
branch, byte-lane data memory.

It answers one question before the real core is designed: **what does this
style cost in HLS on the target** -- does II=1 hold, how many LUTs and
flip-flops, what Fmax. The measured answers are recorded in
`agentic/observations/`; this folder holds only the test.

```
python scripts/pipeline.py run --components calibration-rv32i --stages hls,csim,cosim,impl
```

The testbench assembles a small program (loops, stores then loads, a call and
return, byte and halfword accesses back to back, LUI) and checks what it
stores; co-simulation runs the same program on the generated RTL.
