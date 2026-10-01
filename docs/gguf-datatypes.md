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

## The datapath is optimised for the `.gguf`

Supporting every type is the floor; the design goal is the chosen model
(decisions, 2026-10-01). Ouroboros reads the type of every tensor in the
`.gguf` header, weighs each type by how many bytes of weights it accounts for,
and shapes the accelerator around that mix:

- **Multiplier widths.** llama.cpp quantises activations to 8 bits for its dot
  products (Q8_K, Q8_0, Q8_1), so a multiply is an 8-bit activation times a
  weight of the model's width. The PEs are sized for the widths the model
  actually uses, with narrow weights packed several to a DSP (for example four
  4-bit multiplies per DSP48E2, two 8-bit) -- so a 4-bit model gets twice the
  multiplies per DSP that a generic 8-bit design would.
- **The arithmetic itself, where the model calls for it.** A ternary model
  (TQ1_0, TQ2_0) gets PEs with no multipliers -- add, subtract or skip. An FP4
  model (MXFP4, NVFP4) gets FP4 PEs with their scale formats. An F16 or BF16
  model gets a floating-point datapath of that format.
- **Unpacker throughput in proportion.** Decode streams every weight once per
  token, so each type's unpacker gets the lanes it needs to keep up with DDR
  for its share of the model's bytes -- a Q4_K_M file, mostly Q4_K with some
  Q5_K and Q6_K, gets a wide Q4_K unpacker and narrower ones beside it.
- **Scales and accumulators** sized for the model's block structure (fp16 `d`
  per block, K-quant sub-block scales, E8M0/E4M3 for FP4) and its dimensions.

**The recommended configuration is optimised for just the supplied `.gguf`**
-- its types and nothing else; every LUT the recommendation spends on the
accelerator goes to the model in hand (decisions, 2026-10-01).

**The user can spend LUTs on other datatypes.** Beyond the recommendation,
any share of the accelerator's budget can be allocated to processing elements
of other datatypes -- dedicated PEs and unpackers for, say, Q8_0 or MXFP4, to
run other models on the same bitstream at speed. The configurator shows the
split as a budget: how many LUTs, DSPs and BRAMs go to the model's own PEs and
how many to each added datatype, with the estimate for each (tokens/s for the
model, and for a model of each added type). Taking budget from the model's PEs
lowers its prefill speed, and the estimate says by how much; decode is held by
DDR bandwidth and changes little.

Optimising never means approximating: every PE, of whatever datatype,
produces exactly what ggml produces.

## How the hardware supports all of them

**One unpacker per family, in front of the datapath.** Each family above has
its own HLS unpacker that turns a block into small integers (or, for the plain
floating-point types, floats) and the scales they are multiplied by, feeding
the multiply-accumulate datapath sized for the model (above) and then a scale
stage. Keeping the type-specific work in the unpackers is what makes
supporting every type affordable.

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
- **more**: PEs and unpackers for other datatypes, with a share of the LUT
  budget the user allocates to each (above);
- **all**: every family's unpacker, with the budget split as the user chooses.

Each unpacker's resource cost is measured when it is first built and stored
with it, so the configurator can show what each one costs.

## The KV cache

Treated like the PEs (decisions, 2026-10-01): **recommended for the supplied
`.gguf`, and adjustable in every respect.**

**Recommended, from the `.gguf`.** The file stores no KV type, so Ouroboros
derives one from the model:

| what | recommended from |
|---|---|
| K type, V type | the model's precision: an F32/F16/BF16 model keeps its own floating-point format; a quantised model gets Q8_0, the KV format closest to its 8-bit activations |
| layout and size per token | the model's attention shape: `block_count`, `head_count_kv`, key and value head dimensions (grouped-query attention shrinks it) |
| context length | the model's `context_length`, capped by what fits in DDR beside Ubuntu and the weights, and by how much a full context may slow decode |
| attention hardware | sized for that K/V type and the model's head dimensions, flash-style so quantised V works (llama.cpp requires flash attention for a quantised V cache) |

**Adjustable, like the PE units.** Every one of these can be changed:

- the **K and V types separately**, from every type llama.cpp allows for the
  cache: F32, F16, BF16, Q8_0, Q4_0, Q4_1, IQ4_NL, Q5_0, Q5_1 (`common/arg.cpp`,
  `kv_cache_types`);
- the **context length**, and with it the **share of DDR** the cache takes;
- **dedicated attention hardware for other KV types**, from the LUT budget
  exactly as PEs of other weight types are (above), so one bitstream can run
  caches of several types;
- where the cache lives, if the target offers a choice (DDR, or on-chip memory
  for the most recent tokens on parts with enough of it -- the KV260 has not:
  its URAM holds tens of tokens for a 1.5B model).

The configurator shows each choice's cost and effect: DDR used, the longest
context that fits, decode speed at a full context, and the LUTs the attention
hardware takes. Every KV type is verified bit-exact against ggml like the
weight types.

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
