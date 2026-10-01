# GGUF datatypes

Status: **draft for review** (Phase 0).

**Ouroboros supports every datatype a `.gguf` can hold** (decisions,
2026-10-01). Not only the common ones: every type in llama.cpp's `ggml_type`,
in hardware, with none left to a CPU fallback. This supersedes the
configurator report's proposal to warn on the IQ2/IQ3 types and fall back to
the CPU.

## The 35 types

Taken from the llama.cpp checkout in `Tools/llama.cpp` (2026-09-30): the
`ggml_type` enumeration in `ggml.h`, and each type's block size and bytes per
block from the `type_traits` table in `ggml.c`, with `sizeof` of every block
struct computed by compiling `ggml-common.h` -- not transcribed. Removed types
(Q4_2, Q4_3, the Q4_0_x_y and IQ4_NL_x_y repacks) are no longer valid in GGUF
files and are not listed. When the llama.cpp pin moves, this table is
regenerated and any new type gets a row before the pin is accepted.

| family | type | block (values) | bytes / block | bits / weight | what a block holds |
|---|---|---:|---:|---:|---|
| **plain** | F64 | 1 | 8 | 64 | IEEE double |
| | F32 | 1 | 4 | 32 | IEEE single |
| | F16 | 1 | 2 | 16 | IEEE half |
| | BF16 | 1 | 2 | 16 | bfloat16 |
| | I8 / I16 / I32 / I64 | 1 | 1 / 2 / 4 / 8 | 8-64 | integers (indices and the like, not weights) |
| **simple block** | Q8_0 | 32 | 34 | 8.5 | fp16 scale d; 32 int8 |
| | Q8_1 | 32 | 36 | 9.0 | d and the block's sum; 32 int8 (an activation format) |
| | Q5_0 | 32 | 22 | 5.5 | d; 5-bit values (high bits packed apart), offset -16 |
| | Q5_1 | 32 | 24 | 6.0 | d and a minimum m; 5-bit values |
| | Q4_0 | 32 | 18 | 4.5 | d; 4-bit values, offset -8 |
| | Q4_1 | 32 | 20 | 5.0 | d and m; 4-bit values |
| | Q2_0 | 64 | 18 | 2.25 | d; 2-bit values |
| | Q1_0 | 128 | 18 | 1.125 | d; 1-bit values |
| **FP4 microscaling** | MXFP4 | 32 | 17 | 4.25 | one E8M0 shared exponent; 32 E2M1 values |
| | NVFP4 | 64 | 36 | 4.5 | four UE4M3 scales, one per 16 values; 64 E2M1 values |
| **K-quants** (256-value superblocks of sub-blocks) | Q8_K | 256 | 292 | 9.125 | fp32 d; int8 values; sub-block sums (an activation format) |
| | Q6_K | 256 | 210 | 6.5625 | d; 8-bit sub-block scales; 6-bit values |
| | Q5_K | 256 | 176 | 5.5 | d, dmin; 6-bit sub-block scales and mins; 5-bit values |
| | Q4_K | 256 | 144 | 4.5 | d, dmin; 6-bit sub-block scales and mins; 4-bit values |
| | Q3_K | 256 | 110 | 3.4375 | d; 6-bit sub-block scales; 3-bit values |
| | Q2_K | 256 | 84 | 2.625 | d, dmin; 4-bit sub-block scales and mins; 2-bit values |
| **non-linear lookup** | IQ4_NL | 32 | 18 | 4.5 | d; 4-bit indices into a 16-entry int8 table |
| | IQ4_XS | 256 | 136 | 4.25 | d; 6-bit sub-block scales; 4-bit indices into the same table |
| **lattice codebook** | IQ3_S | 256 | 110 | 3.4375 | d; 9-bit indices into a 512-entry grid of 4 values; sign bits; sub-block scales |
| | IQ3_XXS | 256 | 98 | 3.0625 | d; 8-bit indices into a 256-entry grid of 4 values; packed signs and scales |
| | IQ2_S | 256 | 82 | 2.5625 | d; 10-bit indices into a 1024-entry grid of 8 values; sign bits; scales |
| | IQ2_XS | 256 | 74 | 2.3125 | d; 9-bit indices into a 512-entry grid of 8 values; packed signs; scales |
| | IQ2_XXS | 256 | 66 | 2.0625 | d; 8-bit indices into a 256-entry grid of 8 values; sign patterns from a 128-entry table |
| | IQ1_M | 256 | 56 | 1.75 | no d (packed in the scales); 11-bit indices into a 2048-entry grid; shifts |
| | IQ1_S | 256 | 50 | 1.5625 | d; 11-bit indices into a 2048-entry grid; shifts |
| **ternary** | TQ2_0 | 256 | 66 | 2.0625 | d; values in {-1, 0, 1}, 2 bits each |
| | TQ1_0 | 256 | 54 | 1.6875 | d; values in {-1, 0, 1}, five per byte in base 3 |

## How the hardware supports all of them

**One unpacker per family, one arithmetic core.** Each family above has its
own HLS unpacker that turns a block into small integers (or, for the plain
floating-point types, floats) and the scales they are multiplied by. Behind
the unpackers sits the shared multiply-accumulate core, then a scale stage.
The unpacker is where the types differ; the arithmetic is common, which is
what makes supporting every type affordable.

| family | unpacker does | needs |
|---|---|---|
| plain | passes floats to a floating-point path; integers to an integer path | an FP16/BF16/FP32 path; F64 through a multi-cycle sequencer (rare in files; correct, not fast) |
| simple block | unpacks 1-8-bit fields, applies the offset or minimum | shifts and masks |
| FP4 microscaling | decodes E2M1 through a 16-entry table, applies the E8M0 or E4M3 scale | a 16-entry table; exponent arithmetic |
| K-quants | unpacks the sub-block scales and mins, then the values | per-sub-block scale stage |
| non-linear lookup | maps 4-bit indices through a 16-entry int8 table | a 16-entry table |
| lattice codebook | looks each index up in its grid, applies signs and scales | grid ROMs in block RAM: 1-16 KB each, about 33 KB for all six, roughly 8 BRAM36 |
| ternary | decodes base-3 or 2-bit fields to {-1, 0, 1} | no multiplier at all: add, subtract or skip |

**Which unpackers a build includes** is a configurator choice
([configurator report](../agentic/reports/Ouroboros%20configurator%20options.md)):

- **recommended**: exactly the types present in the chosen `.gguf` -- read
  per tensor from its header, not from the file name (a "Q4_K_M" file also
  holds Q5_K and Q6_K tensors) -- plus the KV cache's type;
- **more**: add any others, to run other models on the same bitstream;
- **all**: every family's unpacker.

Each unpacker's resource cost is measured when it is first built and stored
with it, so the configurator can show what each one costs.

**The KV cache** can use every type llama.cpp allows for it: F32, F16, BF16,
Q8_0, Q4_0, Q4_1, IQ4_NL, Q5_0, Q5_1 (`common/arg.cpp`, `kv_cache_types`).
Quantized V needs a flash-attention path in llama.cpp, and so in the
accelerator.

## Verification

Every type is checked bit for bit against llama.cpp's own reference code --
the `dequantize_row_*` and `vec_dot_*` functions in `Tools/llama.cpp` -- in C
simulation, on random blocks and on real tensors from `.gguf` files: the
unpacker's output and the dot product must equal ggml's exactly (or, for the
floating-point paths, within ggml's own rounding). That suite runs in
`scripts/pipeline.py` alongside the core's lock-step suites.

## Open

- Per-family resource costs: unmeasured until the unpackers exist.
- Whether the F64 and I64 paths are ever exercised by real models; they are
  supported regardless.
