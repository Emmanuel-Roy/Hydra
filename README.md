# Ouroboros

## What is Ouroboros

Ouroboros is a FPGA Laptop created by vibe coding to vibe code more. We use a static RVA23 architecture to boot Ubuntu, alongside a reconfigurable systolic array unit based around the AI model to be run on the device. The physical hardware too, outside of the core FPGA will be vibe coded.

## High Level Overview

Ouroboros aims to be fully RVA23S64 Compliant, verified by running DoomV in Lock-step (which is Sail Compliant).

Ouroboros is more of a funny proof of concept than an actual competitive commercial tool, so for ease of development there will only be basic pipelining with no-op based hazard fixing. Additionally, only ONE hart will be supported (Hardware Thread).

Additionally, the CPU core itself is not the primary focus of optimization, it's purpose is only to boot Ubuntu and commercial software here. If I don't get bored, I'll work on optimizing it for either faster throughput or to minimize look-up tables.

The dynamic systolic array unit is the primary focus here. The goal is to feed Hydra a .gguf and an FPGA target, get the parameters from it, and get an optimized systolic array unit out of it.

## How to Generate and build!


## Technical Architecture

### Supported ISA Extensions By Core

### Pipelining and Hazards

### Generic Architecture for Systolic Array Unit

### Memory Map

### I/O

### Verification Suites

### FPGA Specifics

This program uses Vitis for compliation.

### RTL Design Overview

## Software Architecture

Run Ouroboros, it will ask for a .gguf and it will ask for an FPGA target. From that target, it reads the model parameters, and the FPGA specifications (Memory / Look-up tables). It will build an estimated requirements document (LUTS needed for the CPU and Systolic Array, number of PE's for the Systolic Array, KV Cache Requirements, Memory format in the PE units, etc) for the user, and it will warn the user if that model optimized architecture won't work for that particular FPGA. With the requirements doc, the software will adjust parameters in the Vitis C++ code, then synthesize for Vivado compilation. 

## BOM

