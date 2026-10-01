# Toolchain smoke component

**Test infrastructure, not Ouroboros hardware.** A deliberately trivial HLS
kernel -- a pipelined multiply-accumulate over a stream -- with a C++
testbench. It exists so `scripts/pipeline.py` can prove its Vitis stages
(HLS synthesis, C simulation, co-simulation, out-of-context implementation)
and its report parsers against what the pinned AMD release actually produces,
before any real component exists. It is never part of a bitstream.

```
python scripts/pipeline.py run --components smoke --stages hls,csim,cosim,impl
```
