# FPGAs

The targets Ouroboros can build for, one folder each. The configurator lists
them when it asks for a target ([docs/ouroboros-flow.md](../docs/ouroboros-flow.md)).

A target folder holds a `target.toml` that **names the target's platform
specification** -- entries in Vivado's board store, or an exported hardware
platform (`.xsa`) -- and nothing else. Everything Ouroboros needs about the
board (part, resources, interfaces, memory, clocks) is read from that
specification and generated from it; no board-specific code is written by hand.

Any board or platform in the library installed with the pinned Vivado and Vitis
can be picked; picking one saves it here. From the command line:

```sh
python scripts/pipeline.py targets                      # saved targets, then the library
python scripts/pipeline.py targets --search zcu         # search the library
python scripts/pipeline.py targets --save xilinx.com:zcu104 --as zcu104
```
