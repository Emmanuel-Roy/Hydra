# GGUF-driven FPGA LLM accelerator generator ("Hydra") for small FPGAs (Kria KV260 / XCK26)

Scope note: research done 2026-09-30 with a limited tool budget (about 16 fetches/searches). Measured numbers come from the cited papers and repos. Every roofline number is **estimated** by my own arithmetic, with the inputs shown. Where I state something from background knowledge that I did not re-verify this session, I say so and put it under Gaps.

---

## 1. GGUF format and quantization block formats

### Takeaway
GGUF v3 is easy to parse: a fixed header, typed key/value metadata, a tensor-info table, and then aligned tensor data (32 bytes by default). Everything Hydra needs (architecture, dimensions, per-tensor ggml_type) is in the metadata and the tensor-info table, so Hydra never has to read the weights to size a design. Quantized types are fixed-size blocks: 32-weight blocks (Q4_0, Q8_0, IQ4_NL, MXFP4) or 256-weight "super-blocks" (K-quants, IQ*, TQ*). Each block carries an fp16 scale (K-quants also carry an fp16 min), so the datapath has to dequantize per block with an fp16 or fixed-point scale multiply.

### Cited Findings
- Header: `uint32 magic` = "GGUF" (0x47 0x47 0x55 0x46), `uint32 version` = 3, `uint64 tensor_count`, `uint64 metadata_kv_count`. — [ggml gguf.md](https://github.com/ggml-org/ggml/blob/master/docs/gguf.md)
- There are 13 metadata value types (uint32 enum): UINT8, INT8, UINT16, INT16, UINT32, INT32, FLOAT32, BOOL, STRING, ARRAY, UINT64, INT64, FLOAT64. A string is UTF-8 with its length prepended and no null terminator. An array has its type and length prepended and can be nested. — [ggml gguf.md](https://github.com/ggml-org/ggml/blob/master/docs/gguf.md)
- Required keys: `general.architecture` (lowercase `[a-z0-9]+`) and `general.quantization_version` (must be present if any tensor is quantized). `general.alignment` is a uint32 that must be a multiple of 8. If it is absent, assume 32. — [ggml gguf.md](https://github.com/ggml-org/ggml/blob/master/docs/gguf.md)
- Tensor info: `gguf_string name` (max 64 bytes), `uint32 n_dimensions` (at most 4), `uint64 dimensions[n]`, `ggml_type type`, and `uint64 offset`. The offset is relative to the start of tensor_data and must be a multiple of ALIGNMENT. Tensors are padded to ALIGNMENT. — [ggml gguf.md](https://github.com/ggml-org/ggml/blob/master/docs/gguf.md)
- The same spec defines the per-architecture LLM keys Hydra needs: `[arch].context_length`, `.embedding_length`, `.block_count`, `.feed_forward_length`, `.attention.head_count`, `.attention.head_count_kv`, `.rope.dimension_count`, `.rope.freq_base`, `.attention.layer_norm_rms_epsilon`, plus `general.file_type`. I asked for these, but the fetched summary did not quote them back verbatim, so treat the exact spellings as "per gguf.md" and re-check against [gguf.md](https://github.com/ggml-org/ggml/blob/master/docs/gguf.md) or the `gguf-py` constants (`gguf-py/gguf/constants.py` in llama.cpp).
- Block struct layouts, from `ggml-common.h` ([source](https://raw.githubusercontent.com/ggml-org/llama.cpp/master/ggml/src/ggml-common.h)). bpw is computed as bytes×8/weights:

| type | weights/block | fields | bytes | bpw |
|---|---|---|---|---|
| Q4_0 | 32 | fp16 d; u8 qs[16] | 18 | 4.5 |
| Q4_1 | 32 | fp16 d, m; u8 qs[16] | 20 | 5.0 |
| Q5_0 | 32 | fp16 d; u8 qh[4]; u8 qs[16] | 22 | 5.5 |
| Q8_0 | 32 | fp16 d; i8 qs[32] | 34 | 8.5 |
| Q2_K | 256 | u8 scales[16]; u8 qs[64]; fp16 d, dmin | 84 | 2.625 |
| Q3_K | 256 | u8 hmask[32]; u8 qs[64]; u8 scales[12]; fp16 d | 110 | 3.4375 |
| Q4_K | 256 | fp16 d, dmin; u8 scales[12] (K_SCALE_SIZE=12); u8 qs[128] | 144 | 4.5 |
| Q5_K | 256 | fp16 d, dmin; u8 scales[12]; u8 qh[32]; u8 qs[128] | 176 | 5.5 |
| Q6_K | 256 | u8 ql[128]; u8 qh[64]; i8 scales[16]; fp16 d | 210 | 6.5625 |
| Q8_K (activation-side) | 256 | f32 d; i8 qs[256]; i16 bsums[16] | 292 | 9.125 |
| IQ2_XXS | 256 | fp16 d; u16 qs[32] | 66 | 2.0625 |
| IQ2_XS | 256 | fp16 d; u16 qs[32]; u8 scales[8] | 74 | 2.3125 |
| IQ3_XXS | 256 | fp16 d; u8 qs[96] | 98 | 3.0625 |
| IQ4_NL | 32 | fp16 d; u8 qs[16] | 18 | 4.5 |
| IQ4_XS | 256 | fp16 d; u16 scales_h; u8 scales_l[4]; u8 qs[128] | 136 | 4.25 |
| TQ1_0 (ternary) | 256 | u8 qs[52]; u8 qh[4]; fp16 d | 58 | 1.6875 |
| TQ2_0 (ternary) | 256 | u8 qs[64]; fp16 d | 66 | 2.0625 |
| MXFP4 | 32 | u8 e (shared E8M0 exponent); u8 qs[16] | 17 | 4.25 |

### Inferences
- **Hydra's parser can be metadata-only.** Read the header, the KVs, and the tensor infos, and stop before tensor_data. A per-tensor histogram of ggml_type gives the PE datatype mix. "Q4_K_M" files are mixed: typically Q4_K plus Q6_K for some tensors, such as attn_v, ffn_down, and output/token_embd. So the PE design must handle **each** type that appears, not only the type the filename names.
- **Dequant cost by family:**
  - Q4_0, Q8_0, and IQ4_NL are the simplest: one fp16 scale per 32 weights, symmetric. IQ4_NL adds a 16-entry non-linear lookup table, which is just a LUT.
  - Q4_K and Q5_K are asymmetric. The value is roughly `d·sc_j·q − dmin·m_j`, with 8 sub-blocks of 32 weights, each with 6-bit sc and 6-bit m packed into 12 bytes. This semantic comes from the k-quants design; I did not re-fetch it this session. A dot product therefore needs Σq·x plus a "min" correction term m_j·Σx per sub-block. That maps naturally onto an integer MAC array plus one per-sub-block scale-and-accumulate stage.
  - Q6_K uses signed 8-bit sub-scales over 16 groups of 16 weights.
  - IQ2/IQ3 use codebook (grid) lookups. They are costly in LUTs or BRAM and are probably out of scope for a first Hydra.
- Bytes per weight (Q4_0 0.5625, Q4_K 0.5625, Q6_K 0.82, Q8_0 1.0625, F16 2) feed straight into the decode roofline in section 3.

### Gaps
- I found no authoritative statistic on which GGUF quant types are most downloaded for small models. From background knowledge (unverified), Q4_K_M and Q8_0 are the de facto defaults for 0.5–3B models on HF repos such as bartowski/unsloth/Qwen official, with Q5_K_M and Q6_K next.
- I did not re-fetch the exact bit-packing of Q4_K `scales[12]` (6-bit sc/m packing) or the IQ grids. Before writing RTL, re-check `dequantize_row_q4_K` in `ggml-quants.c`.
- BF16 and F16 are plain 2-byte element types (no blocks). I did not fetch a separate source for this.

---

## 2. Prior FPGA LLM accelerators: measured results

### Takeaway
On KV260-class parts, the measured state of the art is about **4.8–5 tok/s decode for 7–8B 4-bit models**, with **84–94% of the 19.2 GB/s DDR bandwidth** used. It reaches **about 25–28 tok/s for a 0.73B ternary model** at about 5 W. Every top design is decode-specialized and bandwidth-bound, with modest DSP use (179–750 DSPs). Prefill on these edge designs is weak, at roughly 30–143 tok/s.

### Cited Findings (all **measured** as reported by the authors)
- **Hummingbird (ICCAD'25), KV260:**
  - Model: LLaMA3-8B, 4-bit GPTQ weights, 8-bit KV cache, 300 MHz.
  - Speed: **4.8 tok/s decode**, **93–94% bandwidth utilization** (up from 84% in the prior work), context up to 4096.
  - Resources: **26K LUT, 179 DSP, 59 BRAM, 18 URAM, 3.81 W**.
  - Techniques: DSP-optimized compute engine; column-aligned memory access to fix an AXI port-arbitration bottleneck; embedding table offloaded to external flash to free DRAM; GQA dataflow. — [arXiv 2507.03308](https://arxiv.org/html/2507.03308v1)
- **Li et al. (DATE'25), "Pushing up to the limit of memory bandwidth and capacity utilization for efficient LLM decoding on embedded FPGA", KV260:**
  - **LLaMA2-7B 4-bit: 4.9 tok/s at 84% bandwidth utilization.** — [Hummingbird paper](https://arxiv.org/html/2507.03308v1)
  - The open-source repo reports about 5 tok/s on KV260, about 4 tok/s on ZCU104 PL-only, about 8–9 tok/s on ZCU104 PS+PL, and about 18–19 tok/s on Alveo U250.
  - Max context is 1024, and prefill runs token by token.
  - The design is "tightly coupled to the internal structure of LLaMA2-7B", and adapting it to another model needs RTL changes. — [adamgallas/llama-fpga](https://github.com/adamgallas/llama-fpga)
- **TeLLMe v2, KV260:**
  - Model: BitNet 0.73B (W1.58-A8), 250 MHz, table-lookup ternary matmul.
  - Speed: **25 tok/s decode, up to 143 tok/s prefill, TTFT 0.45–0.96 s for 64–128-token prompts, 4.8 W**.
  - Resources: **98,303 LUT (84%), 136,721 FF, 610 DSP (49%), 98.5 BRAM (68%), 60 URAM (94%)**.
  - The paper states 17.1 GB/s as the theoretical max memory bandwidth. — [arXiv 2510.15926v2](https://arxiv.org/html/2510.15926v2)
  - TeLLMe v1: up to 9 tok/s decode over 1024-token contexts, prefill 0.55–1.15 s for 64–128 tokens, at 7 W. — [arXiv 2504.16266](https://arxiv.org/abs/2504.16266)
- **PD-Swap, KV260:**
  - Model: BitNet 0.73B W1.58-A8.
  - Speed: **27.8 tok/s decode** (1.3–2.1× TeLLMe), >10 tok/s at 2048-token sequence length, TTFT 4.9 s at baseline, prefill 30.2 tok/s.
  - Resources: **102,102 LUT (87%), 176,440 FF, 124.5 BRAM, 62 URAM, 750 DSP; 4.9 W; 5.67 tok/J**.
  - Uses dynamic partial reconfiguration to swap prefill-optimized and decode-optimized attention logic. — [arXiv 2512.11550](https://arxiv.org/html/2512.11550)
- **On-Device Qwen2.5, KV260:**
  - Model: Qwen2.5-0.5B, AWQ INT4 with group size 64 (988 MB → 443.81 MB).
  - Speed: **5.1 tok/s** (vs 2.8 baseline).
  - FPGA side: 4 parallel MAC units on 4 AXI channels, an 8×8 PE array, and pipelined unpack/dequant at 200 MHz.
  - ARM A53 side: RoPE, RMSNorm, and SiLU.
  - Resources: 384 DSP, 96,553 LUT (82%).
  - Matmul is 91.6% of latency. — [arXiv 2504.17376](https://arxiv.org/html/2504.17376v1)
  - Note: 5.1 tok/s for a 0.44 GB model is about 2.3 GB/s effective, far below the roofline (see section 3). The design is poorly balanced, which makes it a useful negative example.
- **bitnet-kv260 (hobby/open project), KV260:**
  - Model: 2B ternary model (BitNet), every ternary matmul streamed through the PL, 200 MHz, Ubuntu 22.04.
  - Speed: **16.29 tok/s vs 2.77 tok/s for bitnet.cpp on the A53s**, at about 1/5 the energy per token.
  - Resource figures were not in the README. — [MerlijnW70/bitnet-kv260](https://github.com/MerlijnW70/bitnet-kv260)
- **LlamaF, ZCU102:**
  - Model: TinyLlama 1.1B, W8A8 group-wise quantized GEMV, fully pipelined, with compute overlapped with weight transfer.
  - Speed: **1.5 tok/s**, 14.3–15.8× faster than the ZCU102 PS alone, 6.1× better power efficiency. — [arXiv 2409.11424](https://arxiv.org/html/2409.11424v1)
  - TeLLMe v2 lists LlamaF at 5.1 W. — [TeLLMe v2](https://arxiv.org/html/2510.15926v2)
- **SECDA-LLM:**
  - llama.cpp-integrated platform that offloads quantized MatMul from GGML to the FPGA through an AXI-API, using block-floating-point MatMul.
  - Speed: **0.588 tok/s for TinyLlama 1.1B on PYNQ-Z1 (W3A8)**.
  - The papers mention AMD Kria as a target. — [arXiv 2408.00462](https://arxiv.org/pdf/2408.00462)
  - The 2026 follow-up SECDA-DSE uses an LLM to guide design-space exploration. It was evaluated only on Zynq-7020 kernels, with no tok/s numbers. — [arXiv 2606.11117](https://arxiv.org/html/2606.11117v1)
- **MEADOW, ZCU102:**
  - OPT-1.3B W8A8, about 2 tok/s decode. — [TeLLMe v2 table](https://arxiv.org/html/2510.15926v2)
  - Prefill is reported as **100 tok/s** in TeLLMe v2's table but **10 tok/s** in [PD-Swap's table](https://arxiv.org/html/2512.11550). These conflict.
- **FlightLLM (FPGA'24, datacenter-class, for scale):**
  - LLaMA2-7B on Alveo U280: 6.0× energy efficiency and 1.8× cost efficiency vs V100S at batch 1.
  - On Versal VHK158: **92.5 tok/s**, 1.2× A100 throughput.
  - Uses sparse DSP chains, always-on-chip decode, and a length-adaptive compilation flow. — [arXiv 2401.03868](https://arxiv.org/pdf/2401.03868); [HF paper page](https://huggingface.co/papers/2401.03868)
- **Non-FPGA reference points**, as quoted in the papers:
  - Jetson Orin Nano, TinyLlama 1.1B W4A16: 67.6 tok/s decode.
  - Raspberry Pi 5, Qwen 0.6B W4A16: 16.6 tok/s decode.
  - Jetson prefill is listed as 324.9 tok/s in TeLLMe v2 but 25 tok/s in PD-Swap. These conflict. — [TeLLMe v2](https://arxiv.org/html/2510.15926v2); [PD-Swap](https://arxiv.org/html/2512.11550)
- **Conflict on TeLLMe prefill:** its own paper says up to 143 tok/s, while PD-Swap's comparison table lists TeLLMe prefill as 29.8 tok/s at 5.2 W. The two papers probably define prefill differently (prompt length, or whether TTFT includes overheads). — [TeLLMe v2](https://arxiv.org/html/2510.15926v2) vs [PD-Swap](https://arxiv.org/html/2512.11550)

### Inferences
- The two KV260 4-bit 7–8B designs land within about 5% of the bandwidth roofline: 4.8–4.9 tok/s measured vs about 4.6–5 estimated. This confirms the decode model in section 3 is correct and that **84–94% PL→DDR efficiency is achievable**, but only with a bare PL datapath, careful use of multiple AXI ports, and no competing CPU traffic.
- Hydra's environment is different. A soft RISC-V running Ubuntu shares the same DDR controller, and its fetch and cache misses compete for bandwidth. Plan on 60–80% efficiency, as the brief says, and treat about 90% as a stretch goal.
- Resources needed for a bandwidth-bound decoder are small: Hummingbird uses 26K LUT and 179 DSP. Most of the XCK26 can therefore go to the soft RISC-V, a prefill array, or attention.
- None of the prior designs is model-generic. Each is hand-tuned RTL or HLS for one model. A GGUF→config generator would be novel. The closest is SECDA-LLM's llama.cpp integration, which is generic in software but slow.

### Gaps
- I found no published KV260 result for Qwen2.5-1.5B, Llama-3.2-1B, or SmolLM2 with standard GGUF Q4_K/Q8_0 blocks. Everything published uses AWQ/GPTQ or ternary formats.
- I did not fetch EdgeLLM, Allo/StreamTensor, AMD Vitis AI / Ryzen AI, or the AMD Hackster KV260 LLM projects (tool budget). Background, unverified: Allo (PLDI'24) showed HLS-composed GPT-2 on an Alveo U280. EdgeLLM (2024) is a CPU-FPGA heterogeneous accelerator on VCU128. These still need numbers.
- I found no result with a **soft** RISC-V host. Every KV260 design uses the hard A53s for non-linear ops or orchestration.

---

## 3. Roofline for KV260-class platform (all ESTIMATES unless marked)

### Takeaway
Decode tok/s ≈ (effective DDR bandwidth) / (bytes of weights + KV read per token). At 11.5–15.4 GB/s effective, the estimates are:
- Q4 (4.5 bpw): about **41–55 tok/s for 0.5B**, **20–27 for 1B**, **14–18 for 1.5B**, **7–9 for 3B**, **3–4 for 7B**.
- Q8: about half of that.
- F16 decode: only usable for models of 1.5B and below.

Prefill on about 1000 DSPs at 250 MHz with INT8 packing (about 1 TOPS peak) is at most **about 330 tok/s for a 1.5B model**. Decode needs only **about 30–60 DSPs** of MAC throughput to keep up with DDR.

### Cited Findings
- KV260 DDR4: 4 GB at **19.2 GB/s**, per [Qwen2.5-on-KV260](https://arxiv.org/html/2504.17376v1) and [Hummingbird](https://arxiv.org/html/2507.03308v1). TeLLMe v2 instead says **17.1 GB/s** theoretical max ([arXiv 2510.15926v2](https://arxiv.org/html/2510.15926v2)). This conflict is unresolved: possibly a different DDR speed grade assumption, or a measured or achievable rather than nameplate figure.
- Measured effective utilization: 84% for LLaMA2-7B in DATE'25, and 93–94% in Hummingbird. — [Hummingbird](https://arxiv.org/html/2507.03308v1)
- Qwen2.5-1.5B config: 28 layers, hidden 1536, 12 heads, **2 KV heads**, FFN 8960, vocab 151,936, tied embeddings, max positions 131,072. — [HF config](https://huggingface.co/Qwen/Qwen2.5-1.5B/raw/main/config.json)
- SmolLM2-1.7B config: 24 layers, hidden 2048, 32 heads, **32 KV heads (no GQA)**, FFN 8192, vocab 49,152, tied, max positions 8192. — [HF config](https://huggingface.co/HuggingFaceTB/SmolLM2-1.7B/raw/main/config.json)

### Calculations (ESTIMATES)

**Decode bytes per token** ≈ N_params × bytes/weight. This holds because every weight matrix, including the tied lm_head (the full vocab×d embedding), is streamed once per token. The token-embedding lookup reads only one row, but when embeddings are tied the same matrix is streamed for lm_head anyway.

Bytes/weight values used: Q4 (Q4_0/Q4_K) = 4.5/8 = **0.5625**; Q8_0 = 8.5/8 = **1.0625**; F16 = **2.0**.

Effective bandwidth values used: 60% × 19.2 = **11.52 GB/s**; 80% × 19.2 = **15.36 GB/s** (Hummingbird-level 93% = 17.9 GB/s).

| model (nominal params) | Q4 GB | Q4 tok/s @11.52 / @15.36 | Q8 GB | Q8 tok/s @11.52 / @15.36 | F16 GB | F16 tok/s @11.52 / @15.36 |
|---|---|---|---|---|---|---|
| 0.5B | 0.281 | 41.0 / 54.6 | 0.531 | 21.7 / 28.9 | 1.0 | 11.5 / 15.4 |
| 1B | 0.563 | 20.5 / 27.3 | 1.063 | 10.8 / 14.5 | 2.0 | 5.8 / 7.7 |
| 1.5B | 0.844 | 13.7 / 18.2 | 1.594 | 7.2 / 9.6 | 3.0 | 3.8 / 5.1 (but 3 GB does not fit alongside Ubuntu) |
| 3B | 1.688 | 6.8 / 9.1 | 3.188 | 3.6 / 4.8 (tight fit) | 6.0 | does not fit in 4 GB |
| 7B | 3.938 | 2.9 / 3.9 (barely fits only with no OS; Ubuntu makes this infeasible) | 7.44 | does not fit | 14 | does not fit |

Example: 15.36 GB/s ÷ 0.84375 GB = 18.2 tok/s.

- Q4_K_M files are a bit larger than pure 4.5 bpw because some tensors are Q6_K. Expect about 5–10% lower tok/s than the Q4 column. This is an estimate; I did not fetch a measured bpw for Q4_K_M.
- **Sanity check against measured results:** LLaMA2-7B (6.7B params × 0.5–0.56 B/w ≈ 3.4–3.8 GB) at 84% × 19.2 = 16.1 GB/s gives ≈ 4.3–4.7 tok/s, vs **4.9 measured**. LLaMA3-8B with the embedding offloaded to flash (about 7.5B streamed × about 0.5 B/w ≈ 3.75 GB) at 17.9 GB/s gives ≈ 4.8 tok/s, vs **4.8 measured**. The model holds.

**KV-cache bytes per token** (F16 K and V) = 2 × n_layers × n_kv_heads × head_dim × 2 B:
- Qwen2.5-0.5B (24 layers, 2 KV heads, head_dim 64; config not fetched, from background): 2×24×2×64×2 = **12,288 B (12 KiB)**.
- Qwen2.5-1.5B (28 layers, 2 KV heads, head_dim 1536/12 = 128; [config](https://huggingface.co/Qwen/Qwen2.5-1.5B/raw/main/config.json)): 2×28×2×128×2 = **28,672 B (28 KiB)**.
- Llama-3.2-1B (16 layers, 8 KV heads, head_dim 64; config from background, unverified): 2×16×8×64×2 = **32,768 B (32 KiB)**.
- TinyLlama-1.1B (22 layers, 4 KV heads, head_dim 64; from background, unverified): 2×22×4×64×2 = **22,528 B (22 KiB)**.
- SmolLM2-1.7B (24 layers, 32 KV heads, head_dim 64; [config](https://huggingface.co/HuggingFaceTB/SmolLM2-1.7B/raw/main/config.json)): 2×24×32×64×2 = **196,608 B (192 KiB)**. This is 7× Qwen2.5-1.5B because the model has no GQA.

**Context capacity in 4 GB** (ESTIMATE). Assume about 1.0–1.5 GB is reserved for kernel, Ubuntu userspace, llama.cpp runtime, and buffers. This is an assumption, not measured. A Qwen2.5-1.5B Q4 model (about 0.9 GB) then leaves about 1.6–2.1 GB for KV:
- Qwen2.5-1.5B: 1.6 GiB / 28 KiB ≈ 60K tokens, so the 32K usable context fits (32K × 28 KiB = 896 MiB).
- SmolLM2-1.7B: 1.6 GiB / 192 KiB ≈ 8.7K tokens, so its 8K max fits only barely (8192 × 192 KiB = 1.5 GiB).
- Llama-3.2-1B: 32K × 32 KiB = 1 GiB.
- An 8-bit KV cache (as in Hummingbird) halves all of these.

**KV traffic during decode** adds L × KV-bytes per token. For Qwen2.5-1.5B at L = 4096: 4096 × 28 KiB = 112 MiB per token, vs about 0.84 GB of weights (+13%, so about 12% lower tok/s). At L = 32K it adds 896 MiB, which roughly **halves** decode speed. For SmolLM2-1.7B at 8K it adds 1.5 GiB per token, which more than halves decode. Hydra's estimator must include this term: tok/s(L) = BW / (W + L·kv_bytes).

**PL→PS port bandwidth** (ESTIMATE; port widths from background knowledge of Zynq US+, not re-verified this session). Each S_AXI_HP/HPC port is up to 128 bits wide. At 250 MHz that is 4 GB/s per port, and at 300 MHz it is 4.8 GB/s. Reaching about 15–18 GB/s therefore needs **at least 4 ports in parallel at 250–300 MHz**. This agrees with the Qwen2.5 design using 4 AXI channels and Hummingbird's fix for AXI port arbitration.

**Decode compute requirement.** At 15.36 GB/s with Q4, the array consumes 15.36e9 / 0.5625 = 27.3 G weights/s, which is 27.3 GMAC/s. At 250 MHz that is 109 MAC/cycle. With 4 INT4×INT8 MACs per DSP (packing), that is about 28 DSPs. With 2 MACs per DSP (INT8 packing), it is about 55 DSPs. With Q8 weights it is about 14.5 GMAC/s, or 58 MAC/cycle. Measured designs use 179–750 DSPs, mostly for prefill or attention.

**Prefill compute** ≈ 2 × N_params ops per token (plus attention, about 4·L·d·layers, which is small at short L):
- Qwen2.5-1.5B: about 3.08 GOP per token. A 512-token prompt is 1.58 TOP.
- An array of 1024 DSPs × 2 INT8 MAC × 2 op × 250 MHz = **1.02 TOPS peak**, giving at most about 332 tok/s. At 50–70% utilization that is about 170–230 tok/s, so a 512-token prompt takes about 2.2–3 s.
- With INT4×INT4 packing (4 MAC/DSP), the peak is 2.05 TOPS. But activations are usually 8-bit (Q8_K-style in llama.cpp), so INT4×INT8 packing is the relevant case. Its packing factor is not established here (see section 4 gaps).

**Prefill ridge point.** Compute peak / bandwidth = 1.02e12 / 15.36e9 ≈ **67 ops/byte**. A prefill tile of T tokens reuses each weight T times, giving an arithmetic intensity of 2T / (bytes per weight):
- Q4: 3.56T, so the array is compute-bound when T ≥ 19 tokens.
- Q8: 1.88T, so T ≥ 36.
- F16: T, so T ≥ 67.

The on-chip activation buffer must therefore hold T × d_model × 1 byte. For T = 64 and d = 1536 that is about 98 KB, which is trivial versus 144 BRAM36 (about 648 KB) plus 64 URAM (about 2.3 MB). Those capacity figures come from my knowledge of standard block sizes (36 Kb BRAM, 288 Kb URAM), not from a source.

### Inferences
- **Hydra should treat decode and prefill as separate sizing problems:**
  - Decode: choose the number of AXI ports, the burst width, and a dequant pipeline wide enough to sustain about 0.8 × BW. The MAC count follows from that, at roughly 30–120 DSPs.
  - Prefill: size the PE array by DSP budget, with T ≥ ridge tokens of on-chip activation reuse.
  - Since decode dominates chat workloads, the useful sweet spot on KV260 is **0.5–1.5B models at Q4/Q8**, for about 14–55 tok/s estimated.
- For the default model target, prefer GQA models with few KV heads (the Qwen2.5 family). Flag non-GQA models such as SmolLM2-1.7B as KV-heavy.

### Gaps
- I have no measured figure for PL→DDR efficiency while a soft RISC-V running Ubuntu shares the controller. The 60–80% range is the brief's assumption, not data.
- I have no measured Ubuntu memory footprint on a soft RISC-V. The 1.0–1.5 GB reservation is a guess.
- The 17.1 vs 19.2 GB/s nameplate conflict is unresolved.

---

## 4. Systolic array vs. other architectures; dequant; DSP packing

### Takeaway
Decode is GEMV, with batch 1 and no weight reuse. A large 2-D systolic array therefore idles in decode, and the winning edge designs are bandwidth-matched GEMV/streaming engines with on-the-fly dequant. For ternary models, table-lookup engines win. A sensible Hydra template is a **wide 1-D (or short 2-D) array**: one dimension streams weight blocks at DDR rate, and the other dimension only grows to buy prefill throughput. Group scales are applied once per block, after the integer dot product.

### Cited Findings
- LlamaF uses a fully pipelined accelerator for **group-wise quantized matrix-vector multiplication (GQMV)** and overlaps FPGA compute with weight transfer within each layer. — [LlamaF](https://arxiv.org/html/2409.11424v1)
- The Qwen2.5 KV260 design uses an 8×8 PE array with pipelined weight unpacking and dequantization feeding 4 MAC units on 4 AXI channels. — [arXiv 2504.17376](https://arxiv.org/html/2504.17376v1)
- TeLLMe v2 uses a **table-lookup matmul (TLMM)** for 1.58-bit weights × 8-bit activations, plus fused attention for prefill and decode. — [TeLLMe v2](https://arxiv.org/html/2510.15926v2)
- PD-Swap time-multiplexes prefill-optimized (compute) and decode-optimized (memory) attention logic using DPR, instead of a static compromise. — [PD-Swap](https://arxiv.org/html/2512.11550)
- Hummingbird uses a "DSP-optimized" hybrid compute engine that saves LUTs (66%), DSPs (39%), and power (42%) vs its predecessor. — [Hummingbird](https://arxiv.org/html/2507.03308v1)
- **DSP48E2 packing:** AMD WP521 ("Convolutional Neural Network with INT4 Optimization on Xilinx Devices", 2020) packs **two INT4 values into each DSP48E2 input**, giving **four independent INT4 multiplies per DSP**. — [AMD WP521](https://docs.amd.com/api/khub/documents/SDFn1nGbW4R1ag1QuXRHRg/content); [DSP-Packing paper](https://arxiv.org/html/2203.11028)
- AMD's INT8 white paper (WP486) describes packing **two INT8 multiplies sharing one operand** into one DSP48E2. — [AMD INT8 WP](https://docs.amd.com/api/khub/documents/z7yAy_aweTmRYkGaTVyhbw/content)
- Newer generalizations exist: "DSP-Packing: Squeezing Low-precision Arithmetic into FPGA DSP Blocks" ([arXiv 2203.11028](https://arxiv.org/html/2203.11028)), UDP, "A Universal DSP Packing Framework for Low-bitwidth MAC" ([ACM](https://dl.acm.org/doi/10.1145/3748173.3779194)), and "Arithmetic Packing on Wide Integer Datapaths in DSP Primitives" ([arXiv 2606.11065](https://arxiv.org/html/2606.11065)).

### Inferences
- **Mapping Q4_K into PEs:**
  - The PE computes a raw int dot product of 4-bit weights (0..15) with int8 activations over 32-weight sub-blocks.
  - A per-sub-block post-stage multiplies by `d·sc_j` (fp16 × 6-bit) and subtracts `dmin·m_j·Σx_subblock`. The activation sums Σx can be precomputed once per activation vector, as llama.cpp's Q8_K does with its `bsums`.
  - The result is one fixed/fp multiply-add per 32 MACs, so the scale path costs about 1/32 of the MAC path.
  - Q4_0 and Q8_0 are simpler: one scale per 32 weights, symmetric. Q6_K uses 16-weight groups with int8 scales.
- **Unsigned vs signed packing:** WP521-style packing assumes particular signedness and operand widths. Q4_K quants are unsigned 0..15, while Q4_0 is effectively q−8. INT4×INT8 packing therefore needs a separate correction-term analysis. Use LUT-based MACs for 4×8 if DSP packing proves awkward. Decode needs few MACs anyway.
- **LUT cost check:** a 4×8-bit multiplier is about 20–30 LUTs (background estimate, not sourced). 109 MAC/cycle for decode is about 3K LUTs, which is cheap. LUTs are a reasonable choice for decode, with DSPs reserved for prefill and attention.
- **Bit-serial / LUT-table engines** (TLMM-style) pay off mainly for ≤2-bit or ternary weights (TQ1_0/TQ2_0). For Q4/Q8 GGUF, a byte-parallel integer MAC with a block-scale post-stage is simpler.

### Gaps
- I did not find a published FPGA engine that consumes **native GGUF K-quant blocks** directly. All published designs re-quantize (AWQ/GPTQ/ternary) into custom layouts. Whether Hydra should re-layout the GGUF into an accelerator-friendly order offline (likely yes, for burst-aligned weight streams) is a design decision with no data behind it yet.
- The exact LUT/FF cost of a Q4_K dequant pipeline is unmeasured.

---

## 5. Integration with a soft RISC-V host and llama.cpp

### Takeaway
The cleanest software path is a **new ggml backend** (device plus buffer type) that claims MUL_MAT (and optionally attention) through `supports_op`/`offload_op`, driven by an MMIO+DMA accelerator. The ggml scheduler already splits graphs between the CPU (RVV kernels) and device backends. SECDA-LLM shows exactly this pattern for FPGA matmul offload. Because the host is a slow soft core, **more ops should move to the PL than on the ARM-hosted KV260 designs**, which kept RoPE, RMSNorm, and SiLU on the A53s.

### Cited Findings
- ggml backend API key types: `ggml_backend_t` (stream), `ggml_backend_buffer_t`, `ggml_backend_dev_t`, and `ggml_backend_reg_t` (plugin registry).
  - Devices report props and type (CPU/GPU/IGPU/ACCEL) and answer `ggml_backend_dev_supports_op` and `ggml_backend_dev_offload_op`.
  - Execution goes through `ggml_backend_graph_compute` (with async variants).
  - Backends can be dynamically loaded with `ggml_backend_load`.
  - `ggml_backend_sched_t` assigns ops to devices by support and tensor locality and inserts copies. — [ggml-backend.h](https://raw.githubusercontent.com/ggml-org/llama.cpp/master/ggml/include/ggml-backend.h)
- SECDA-LLM offloads quantized MatMul kernels from GGML to the FPGA (PYNQ-Z1, Kria), with "context handlers" for tensor and quantization-parameter transfer over an AXI-API. — [arXiv 2408.00462](https://arxiv.org/pdf/2408.00462); [survey 2410.04466](https://arxiv.org/pdf/2410.04466)
- In the Qwen2.5 KV260 design, matmul is 91.6% of latency, and RoPE, RMSNorm, and SiLU stay on the A53 with NEON/VFP. — [arXiv 2504.17376](https://arxiv.org/html/2504.17376v1)
- TeLLMe and PD-Swap put attention (prefill and decode) in the PL as well. — [TeLLMe v2](https://arxiv.org/html/2510.15926v2), [PD-Swap](https://arxiv.org/html/2512.11550)

### Inferences
- **Op split by host speed (estimate):** a single-hart soft RISC-V at roughly 100–200 MHz (assumed; not researched here) is perhaps 5–20× slower than a 1.3 GHz A53 cluster. Even the roughly 8% non-matmul share from the Qwen2.5 profile would then dominate. Hydra should therefore offload **MUL_MAT plus RMSNorm, RoPE, SiLU/GELU·mul, softmax/attention, and the KV-cache append** for decode, leaving the CPU only sampling, tokenization, and control. An alternative is a fused per-layer "graph" command that runs a whole transformer block in the PL.
- **Interface choices:**
  - **MMIO+DMA (recommended):** the accelerator is an AXI master on the HP ports, reading weights from DDR directly, with a descriptor/command queue in MMIO. It fits a ggml backend and Linux (UIO/VFIO or a small kernel driver, with CMA or hugepage-backed buffers for weights and KV).
  - **Custom instructions / RoCC-like:** this ties the accelerator to CPU pipeline state. That buys little for multi-millisecond GEMVs and requires a custom core.
  - **RVV offload:** it is bounded by the soft core's memory port, which is likely far below 15 GB/s, so it is unsuitable for weight streaming.
- **Memory placement:** weights must sit in physically contiguous (or SMMU-mapped) DDR so the PL can burst-read them. llama.cpp normally mmaps the GGUF. The backend's buffer type should allocate device-visible buffers and copy or re-layout weights at load time. KV cache placement: DDR is unavoidable for any context of practical length (see section 3). On-chip URAM (about 2.3 MB) can hold only scratch, activations, and perhaps a short KV window.

### Gaps
- I did not verify the current state of llama.cpp's RISC-V Vector kernels (`ggml/src/ggml-cpu/arch/riscv/`) or how its CPU "extra buffer types" (repack) mechanism might host an accelerator. These need a code read.
- I found no data on soft RISC-V (e.g., CVA6 or a VexRiscv-class core with RVV) running Ubuntu on a K26, including clock speed, memory bandwidth, or LUT cost. That LUT cost directly eats into the 117K LUTs.
- The XCK26 has hard A53 cores. If the project nonetheless uses only a soft core, the hard PS DDR controller is still the only path to the 4 GB. This should be confirmed with the platform researcher.

---

## 6. Existing generators/tools and their estimation models

### Takeaway
Within the budget, I could only confirm SECDA (LLM-guided DSE, llama.cpp-integrated LLM flow). The classic generators (hls4ml, FINN, Allo, Gemmini, AutoSA, DNNWeaver) were not researched this session. Hydra's estimator can be built analytically from the section 3 formulas, calibrated on the measured KV260 designs above.

### Cited Findings
- SECDA-DSE (2026) integrates an LLM into SECDA to guide design-space exploration, generating accelerators (vector multiply, conv2d, transpose) from natural-language specs on a Zynq-7020. It reports utilization (e.g., 21.8% DSP for vector multiply) but **no performance-estimation model and no tok/s**. — [arXiv 2606.11117](https://arxiv.org/html/2606.11117v1)
- The SECDA-LLM platform provides an AXI-API and a profiler for co-design within llama.cpp. — [arXiv 2408.00462](https://arxiv.org/pdf/2408.00462)

### Inferences
- A defensible Hydra estimator, calibrated against the measured KV260 points (DATE'25 at 84% and 4.9 tok/s, Hummingbird at 93% and 4.8 tok/s, TeLLMe at 25 tok/s), has four parts:
  - **Decode:** tok/s = η·BW / (W_bytes + L·kv_bytes) + overhead per layer.
  - **Prefill:** tok/s = min(η_c · DSP·pack·2·f / (2·N), η·BW·T / W_bytes).
  - **Resources:** DSP = PE count / pack factor. LUT = PE count × LUT/MAC + dequant + AXI + soft-CPU. BRAM/URAM = activation tile + weight double-buffers + scale buffers.
  - **Memory:** DDR = W_bytes + ctx·kv_bytes + OS reserve ≤ 4 GB.

### Gaps
- hls4ml, FINN, Allo, Gemmini, AutoSA, and DNNWeaver were not fetched. Background knowledge, unverified this session:
  - FINN and hls4ml target dataflow and streaming CNN/MLP layers with per-layer resource models, and are not suited to multi-GB LLM weights.
  - Gemmini generates a parameterized systolic array plus a RoCC interface for Rocket/BOOM, with analytical and FireSim-based evaluation.
  - AutoSA compiles polyhedral loop nests to systolic arrays with a DSE using analytical latency/resource models.
  - DNNWeaver uses templated accelerators sized by an analytical optimizer.
  - Allo composes HLS kernels and has been used for LLM layers (GPT-2) on Alveo.
  
  All of these need citations before use in the report.
