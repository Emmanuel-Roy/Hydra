# Hydra configurator levers: accelerator and model/runtime choices derived from a GGUF + FPGA target (first target: Kria KV260 / XCK26)

Scope note: research done 2026-10-01. This builds on `..\Ouroboros FPGA laptop feasibility\gguf_llm_accelerator.md` (called "prior notes" below). It does not redo that file's roofline tables, GGUF block-layout table, or the measured KV260 accelerator list. Formulas here reuse the prior notes' symbols.
- Facts carry a URL.
- Anything computed by me is marked **(EST)**.
- Anything from background knowledge that I did not re-verify this session is marked **(BG, unverified)** and repeated under Gaps.

Symbols used throughout:

| Symbol | Meaning |
|---|---|
| BW | DDR peak = 19.2 GB/s (prior notes; conflicts with 17.1 GB/s in TeLLMe v2) |
| η | achieved PL→DDR efficiency |
| W | streamed weight bytes per token |
| b_w | average bytes/weight |
| f | accelerator clock |
| L | current context length |
| kv_tok | KV bytes per token |
| N | parameter count |
| d | embedding_length |
| n_l | block_count |
| n_h | head_count |
| n_kv | head_count_kv |
| d_h | head dim |
| V | vocab size |
| d_ff | feed_forward_length |

---

## 1. Array / datapath levers (PE count, shape, datatypes, dequant, DSP vs LUT, accumulators, memory ports, buffers, clocks, tiles, GEMV vs systolic, offloaded ops, parallel engines)

### Takeaway
Two separate sizing problems should drive the datapath:
- **Decode GEMV width** is fixed by DDR bandwidth. It is the MACs/cycle needed to consume η·BW of weights, which on KV260 is roughly 30–120 DSP-equivalents. Adding PEs beyond that does not raise decode tok/s.
- **Prefill array size** is a free "spend the leftover DSP/LUT" choice. Its tile size must be at least the roofline ridge point.

Datatypes should come from a per-tensor ggml_type histogram of the GGUF, not from the filename. llama.cpp's own Q4_K_M recipe mixes Q4_K, Q5_K and Q6_K, so the dequant front-end must cover every type present. Behind the dequant front-end, a single INT8-activation integer MAC core with a per-block scale post-stage can serve all of them.

### Cited Findings

**Commercial array parameterization (AMD DPU)**
- The AMD DPU (DPUCZDX8G, the MPSoC CNN engine) parameterizes its array as three parallelism dimensions: PP (pixel), ICP (input channel), OCP (output channel). Peak ops/cycle = PP·ICP·OCP·2. B512 = 4×8×8 and B4096 = 8×16×16. Sizes offered: B512, B800, B1024, B1152, B1600, B2304, B3136, B4096. Up to 4 cores per IP. — [PG338 summary (readkong mirror)](https://www.readkong.com/page/dpuczdx8g-for-zynq-ultrascale-mpsocs-product-guide-6779141); [Vitis AI 1.4 DPU config page (search snippet)](https://japan.xilinx.com/html_docs/vitis_ai/1_4/dpu_config.html)
- PG338 single-core resource table (ZCU102):

| Size | LUT | DSP | BRAM |
|---|---|---|---|
| B512 | 26,922 | 118 | 72 |
| B800 | 29,721 | 166 | 90 |
| B1024 | 34,074 | 230 | 104 |
| B1152 | 32,169 | 222 | 121 |
| B1600 | 38,418 | 326 | 126 |
| B2304 | 42,127 | 438 | 165 |
| B3136 | 46,714 | 566 | 208 |
| B4096 | 52,161 | 710 | 255 |

  — [PG338 (readkong mirror)](https://www.readkong.com/page/dpuczdx8g-for-zynq-ultrascale-mpsocs-product-guide-6779141)
- **Conflict:** another version of the same table lists **B512 at 27,893 LUT, 78 DSP, 73.5 BRAM** and **B4096 at 53,540 LUT, 562 DSP, 257 BRAM**. A URAM variant moves BRAM to URAM: B512 uses 1.5 BRAM + 18 URAM, B4096 uses 2 BRAM + 68 URAM. — [search snippet of PG338/manual mirror](https://manualzz.com/doc/56156092/xilinx-b1024--b1152--b1600--b2304--b3136--b4096--b512--b8...)
  - The difference is probably DSP-usage mode or IP version. The guide states that "High DSP usage" uses more DSPs but fewer LUTs than "low".
- The DPU's other levers:
  - "RAM usage high/low": a larger on-chip buffer "allowing more flexibility in handling intermediate data".
  - DSP usage high/low: the DSP vs LUT trade.
  - URAM usage.
  - Optional op units: channel augmentation, depthwise conv with ALU parallelism, softmax, argmax.
  
  — [PG338 (readkong mirror)](https://www.readkong.com/page/dpuczdx8g-for-zynq-ultrascale-mpsocs-product-guide-6779141)

**Gemmini generator parameters**
- Array shape is a 2-level hierarchy: `tileRows/tileColumns` (combinational tiles) inside `meshRows/meshColumns` (pipelined mesh).
- `dataflow` is OS, WS, or BOTH (selectable at runtime).
- Datatypes are `inputType`/`accType`/`outputType`, for example 8-bit input with a 32-bit accumulator.
- Scratchpad and accumulator sizes are `sp_banks`, `sp_capacity`, `acc_capacity` (KiB).
- DMA is `dma_maxbytes`, `dma_buswidth`, `mem_pipeline`.
- Decoupling queue depths are `ld/st/ex_queue_length` and `rob_entries`.

  — [Gemmini README](https://raw.githubusercontent.com/ucb-bar/gemmini/master/README.md)

**FlightLLM**
- A configurable sparse DSP chain: long DSP cascades are split into groups with configurable cascade paths for N:M sparsity, giving 1.6× compute efficiency.
- Mixed-precision weights at 2/3/4/8 bit (3.5-bit average) with 8-bit activations. A dedicated **dequantization unit converts 2/3/4-bit multiplies into INT8 multiplies** "to avoid excessive LUT overhead".
- "Always-on-chip decode": activations stay on-chip between the matrix engine and the special-function unit, and per-token ops are fused. This raised HBM bandwidth utilization in decode from about 35.6% to 65.9% on U280.
- U280 build: 6,345 DSP, 1,252 BRAM, 792 URAM at 225 MHz.

  — [FlightLLM arXiv 2401.03868](https://arxiv.org/html/2401.03868)

**PD-Swap: what lives where, and memory ports per stream**
- Static region: projections, RMSNorm, element-wise ops, and the table-lookup matmul engine.
- Reconfigurable region: attention only, with a prefill module and a decode module.
- The decode attention engine "allocates two high-performance DDR ports each to K and V cache streams".

  — [PD-Swap arXiv 2512.11550](https://arxiv.org/html/2512.11550)

**DSP packing:** WP521 packs 4 INT4 multiplies per DSP48E2, and WP486 packs 2 INT8 multiplies sharing an operand (prior notes, [WP521](https://docs.amd.com/api/khub/documents/SDFn1nGbW4R1ag1QuXRHRg/content), [WP486](https://docs.amd.com/api/khub/documents/z7yAy_aweTmRYkGaTVyhbw/content)).

**GGUF tensor types are mixed inside one file.** llama.cpp's `llama-quant.cpp` assigns per-tensor types for `LLAMA_FTYPE_MOSTLY_Q4_K_M` (ftype id 15):
- The base type is Q4_K.
- `attn_v` is upgraded to **Q6_K** on layers where `use_more_bits(i, n)` is true.
- `ffn_down` is **Q6_K for i < n_layer/16**, **Q5_K where use_more_bits**, otherwise Q4_K (the exact branch depends on the arch).
- `use_more_bits(i,n) = i < n/8 || i >= 7n/8 || (i − n/8) % 3 == 2`.
- Other ftypes inject Q4_1/Q5_1, IQ3_S, MXFP4 (MoE experts) and Q8_0.

  — [llama.cpp src/llama-quant.cpp](https://raw.githubusercontent.com/ggml-org/llama.cpp/master/src/llama-quant.cpp)

**GGUF key spellings** (verified this session in `gguf-py/gguf/constants.py`; this closes a gap in the prior notes):
- `general.file_type`, `general.quantization_version`
- `{arch}.vocab_size`, `{arch}.context_length`, `{arch}.embedding_length`, `{arch}.block_count`, `{arch}.feed_forward_length`
- `{arch}.expert_count`, `{arch}.expert_used_count`
- `{arch}.attention.head_count`, `{arch}.attention.head_count_kv`, `{arch}.attention.key_length`, `{arch}.attention.value_length`, `{arch}.attention.layer_norm_rms_epsilon`, `{arch}.attention.sliding_window`
- `{arch}.rope.dimension_count`, `{arch}.rope.freq_base`, `{arch}.rope.scaling.type`

  — [gguf-py constants.py](https://raw.githubusercontent.com/ggml-org/llama.cpp/master/gguf-py/gguf/constants.py)

### Inferences — lever catalogue with recommendation formulas

On-chip memory on the XCK26 is **(BG, unverified)**: 144 BRAM36 × 36 Kb ≈ 648 KB and 64 URAM × 288 Kb ≈ 2.25 MiB (about 2.9 MB in total).

**L1. Decode GEMV width (MACs/cycle, M_dec)** **(EST)**
- What it is: the lanes that consume the weight stream.
- Range: 16–256 MAC/cycle.
- Formula: `M_dec = ceil(η·BW / (b_w · f))`, rounded up to a power of two and to a multiple of the block width (32).
  - Example: Q4_K_M has b_w ≈ 0.57–0.61 B (EST, the mix above). With η = 0.8, BW = 19.2 GB/s and f = 250 MHz: 15.36e9 / (0.6·250e6) ≈ 102, so recommend **128 MAC/cycle**.
  - Q8_0 (b_w = 1.0625) gives 58, so **64**. F16 gives 31, so **32**.
- Cost: 128 INT4×INT8 MACs is about 32 DSPs with 4-way packing, or about 3K LUTs as LUT multipliers (prior notes, EST).
- Effect: below M_dec, decode is compute-bound and tok/s scales linearly with M. Above M_dec there is no gain.
- Let the user override η. Show "PE beyond this point does not help decode".

**L2. Prefill array (rows × cols, M_pre)**
- What it is: a 2-D weight-stationary (or output-stationary) array.
- Shape: rows = the reduction (K) lanes, which should equal the dequant output width, so a multiple of 32, the GGUF block size. Cols = output channels or tokens.
- Peak: `P = M_pre · 2 · f` ops/s.
- Prefill tok/s ≈ `min(η_c·P / (2N), η·BW·T / W)`, where T is the token tile (prior notes).
- Recommendation: `M_pre = floor(DSP_budget_pre · pack)` where pack = 2 (INT8×INT8) or 4 (INT4×INT4); INT4×INT8 packing is unproven. Choose rows × cols with rows = 32·k.
- DPU-style named tiers keep it legible: "H512 / H1024 / H2048" = MAC/cycle × 2 ops, mirroring B512–B4096.
- Constraint: M_pre's DSPs + M_dec's DSPs ≤ 1248 minus attention/SFU DSPs.

**L3. Token tile T (prefill)**
- Recommendation: `T_min = ceil(P · b_w / (2 · η·BW))`, the ridge point (prior notes: Q4 about 19, Q8 about 36, F16 about 67 at about 1 TOPS).
- Recommend `T = next_pow2(1.5·T_min)`, capped by the activation buffer (L6) and matching llama.cpp `--ubatch-size` (default 512, see section 6).

**L4. Datatypes and arithmetic (default = "follow the GGUF")**
- Build the set S = {ggml_type of every 2-D tensor that will be offloaded}.
- Per type:
  - **Q4_0/Q4_1/Q5_0/Q5_1/Q8_0/IQ4_NL** (32-blocks): unpack → int4/5/8 (IQ4_NL via a 16-entry LUT) → INT MAC with INT8 activations. Then apply one fp16 scale (plus min for _1 variants) per 32.
  - **Q4_K/Q5_K** (256-superblocks, 8 sub-blocks with 6-bit scale and min): INT MAC per 32, then `d·sc_j·Σqx − dmin·m_j·Σx`.
  - **Q6_K** (16×16 groups, int8 scales): INT MAC per 16, then scale.
  - **Q2_K/Q3_K:** similar, smaller.
  - **IQ2/IQ3** (codebook grids): need grid ROMs in BRAM. Flag as "slow path or CPU fallback".
  - **TQ1_0/TQ2_0** (ternary): use a TLMM/LUT engine (TeLLMe/PD-Swap style) instead of MACs.
  - **MXFP4:** E2M1 values with a shared E8M0 exponent per 32, so INT/LUT MAC plus a power-of-two shift.
  - **F16/BF16** tensors (norms, sometimes embeddings or output): fp16 MAC or CPU.
- Activation precision lever: **INT8 (default, matches llama.cpp's Q8 activation quantization, (BG))**, FP16 (accuracy override), or INT4 (aggressive, not recommended).
- FlightLLM's "dequantize low-bit weights to INT8 then use INT8 MACs" is the published precedent for one INT8 core serving 2/3/4/8-bit weights.
- Recommendation rule:
  - If S ⊆ {32-block, K-quant}, generate an INT8×INT8 core plus per-type unpackers. The unpackers are LUT cost, and only the types in S are generated.
  - If S contains ternary types, add a TLMM engine.
  - If S contains IQ2/IQ3, warn and offer "re-quantize to Q4_K" or a CPU fallback.
- User override: force a datapath type (for example FP16 everywhere for debugging, or INT4×INT4 for speed with re-quantization).

**L5. DSP vs LUT multipliers** **(EST)**
- Decode MACs fit in LUTs: about 20–30 LUT per 4×8 MAC (BG). That reserves DSPs for the prefill array.
- The DPU exposes exactly this switch as "DSP usage high/low".
- Recommendation:
  - If the LUT budget remaining after CPU + infrastructure is greater than 1.5 × M_dec × 30, use LUT MACs for decode.
  - Otherwise use DSP packing.
- The prefill array always uses DSPs.

**L6. On-chip buffers**
- Activation tile: `T · d · 1 B` (INT8), double-buffered. Example: T = 64, d = 1536 gives 2 × 98 KB.
- Weight stream FIFO/double buffer: `2 · burst · ports`. Example: 4 ports × 4 KB × 2 = 32 KB.
- Scale/min buffers: `rows/32 · 4 B`.
- Accumulators: `T · cols · 4 B`.
- Attention scratch: `T · L_tile · 2 B` for flash-style blocking.
- Norm/RoPE tables: RoPE sin/cos for `rope.dimension_count/2` frequencies × L is computed on the fly. Precomputing for L = 4096 × 64 freqs × 2 × 2 B = 1 MiB is too large for BRAM, so use a CORDIC or a small recurrence (EST).
- Recommendation: fill URAM first with the activation and accumulator tiles, and use BRAM for FIFOs and scales. Leave ≥ 20% headroom for the soft CPU caches.

**L7. Accumulator width** **(EST)**
- Integer accumulation within a block: `bits = b_wt + b_act + ceil(log2(block))`.
  - Q8_0×Q8: 8 + 8 + 5 = 21 bits.
  - Q4_K sub-block: 4 + 8 + 5 = 17 bits.
- Across blocks, accumulate in **FP32** or **≥ 32-bit fixed** after scaling. K can reach d_ff (8960 for Qwen2.5-1.5B), which adds up to 14 bits.
- DSP48E2 has a 48-bit accumulator (BG), which is ample.
- Recommendation: a 24-bit integer block accumulator, then an FP32 (or 32.16 fixed) cross-block accumulator. Expose "FP32 / fixed32" as an advanced override.

**L8. Memory ports and burst** **(EST)**
- Ports: `n_ports = ceil(η·BW / (port_width_B · f · η_port))` with 16 B (128-bit) HP ports. At 250 MHz with η_port = 0.9 this gives 4 ports.
- Add +2 dedicated ports for K/V streams if attention is offloaded (PD-Swap precedent).
- Burst: AXI 256-beat INCR maximum (BG) × 16 B = 4 KB. Lay the weights out offline so each port streams contiguous 4 KB runs. Hummingbird's "column-aligned access" fix is the cited precedent (prior notes).
- The XCK26 has a limited number of PL→PS HP/HPC ports (BG). The soft RISC-V's own DDR port competes for them, so the configurator must reserve one.

**L9. Clocks**
- Recommend separate domains: accelerator f_acc at 250–300 MHz, matching the measured KV260 designs at 200–300 MHz (prior notes), and a soft CPU at its own (lower) clock.
- The DPU runs its DSP array at 2× the general clock (BG, unverified). That is an option for the prefill array.
- f only matters for decode until M_dec·f ≥ η·BW/b_w.

**L10. Which ops to offload** (levels; recommendation depends on CPU speed, see section 4)

| Level | Ops on the accelerator | Notes |
|---|---|---|
| 0 | MUL_MAT only | SECDA-LLM style |
| 1 | + RMSNorm, RoPE, SiLU·mul, residual add | Qwen-on-KV260 kept these on the A53, but a soft CPU cannot |
| 2 | + attention (QKᵀ, softmax, ·V) + KV append | TeLLMe/PD-Swap |
| 3 | Fused whole-layer command | FlightLLM "always-on-chip decode" |
| 4 | + final norm, lm_head, top-k/argmax | DPU offers argmax/softmax units |

**L11. Parallel engines / heads**
- Attention engines: `n_attn_eng = min(n_kv, DSP_left / DSP_per_engine)`.
  - Each engine processes one KV head's group of `n_h/n_kv` query heads, so GQA reuse is free: one K/V read serves n_h/n_kv queries.
  - Decode attention is bandwidth-bound (PD-Swap), so 1–2 engines suffice. Prefill attention benefits from more.
- Multiple GEMV engines (DPU "cores") only help if they share bandwidth on separate ports, so default to 1.

**L12. GEMV vs systolic vs both vs reconfigurable** (presented in section 3)

### Gaps
- PG338's table conflict (78 vs 118 DSP for B512) is not resolved. I could not open docs.amd.com PG338 pages; the Vitis AI 1.4 config page returned HTTP 500.
- INT4×INT8 DSP packing factor and correction terms are still unverified.
- Exact HP-port count and AXI burst limits on XCK26 were not re-verified (BG).
- LUT cost of each GGUF unpacker (Q4_K scale unpacking, Q6_K, IQ4_NL LUT) is unmeasured.
- I did not confirm which ggml_type llama.cpp chooses for `output.weight` under Q4_K_M. My belief is Q6_K (BG); `token_embd` follows `--token-embedding-type`, or a per-ftype default.

---

## 2. KV cache levers (context length, precision, placement, GQA, memory split; llama.cpp exposure)

### Takeaway
KV size per token is exactly computable from GGUF metadata. With DDR shared by Ubuntu, n_ctx is the dominant memory knob and also a decode-speed knob, because KV is re-read every token.
- On-chip KV is pointless for KV260-scale models except as a per-tile staging buffer. 2.25 MiB of URAM holds only about 80 tokens of Qwen2.5-1.5B F16 KV (EST).
- llama.cpp exposes `-c/--ctx-size`, `--cache-type-k/v` (f32/f16/bf16/q8_0/q4_0/q4_1/iq4_nl/q5_0/q5_1), and `--flash-attn`. A quantized V cache **requires flash attention**, so hardware that supports Q8_0/Q4_0 KV must implement a flash-style (online-softmax, blockwise V) attention path.

### Cited Findings
- llama.cpp server flags:
  - `--ctx-size`: "size of the prompt context (default: 0, 0 = loaded from model)".
  - `--cache-type-k` / `--cache-type-v`: allowed `f32, f16, bf16, q8_0, q4_0, q4_1, iq4_nl, q5_0, q5_1` (default f16).
  - `--flash-attn on|off|auto` (default auto).
  - `--kv-offload/--no-kv-offload`, `--kv-unified`.
  - `--swa-full`: "use full-size SWA cache (default: false)".
  - `--cache-ram` (MiB, default 8192): the host-side prompt cache.
  - `--fit on|off`: "adjust unset arguments to fit in device memory", default on.

  — [llama.cpp server README](https://raw.githubusercontent.com/ggml-org/llama.cpp/master/tools/server/README.md)
- llama.cpp source: `throw std::runtime_error("quantized V cache was requested, but this requires Flash Attention")`. In auto mode it logs "enabling flash_attn since it is required for quantized V cache". — [llama-context.cpp](https://raw.githubusercontent.com/ggml-org/llama.cpp/master/src/llama-context.cpp)
- Ollama:
  - `OLLAMA_KV_CACHE_TYPE` = `f16` (default), `q8_0` ("approximately 1/2 the memory of f16 with a very small loss in precision"), or `q4_0` ("approximately 1/4 … small-medium loss").
  - "models with higher GQA counts may experience more precision loss".
  - Default context is 4,096, overridable via `OLLAMA_CONTEXT_LENGTH` or `num_ctx`.
  - Flash attention is auto-enabled where supported.

  — [Ollama FAQ](https://raw.githubusercontent.com/ollama/ollama/main/docs/faq.mdx)
- PD-Swap keeps Q/K/V in FP16. KV "often exceeds on-chip URAM/BRAM capacity", so the accumulated KV lives in DDR. Its decode advantage grows with context: 1.11× at 64 tokens, 2.02× at 2048, because decode attention becomes KV-bandwidth-bound. — [PD-Swap](https://arxiv.org/html/2512.11550)
- Hummingbird uses an 8-bit KV cache with context up to 4096 on KV260 (prior notes, [arXiv 2507.03308](https://arxiv.org/html/2507.03308v1)).
- GGUF provides `attention.key_length`/`value_length` (when the head dim ≠ d/n_h) and `attention.sliding_window` (SWA). — [constants.py](https://raw.githubusercontent.com/ggml-org/llama.cpp/master/gguf-py/gguf/constants.py)

### Inferences — formulas **(EST)**

**KV bytes per token**
- `d_k = key_length or d/n_h`; `d_v = value_length or d/n_h`.
- `kv_tok = Σ_layers n_kv · (d_k·s_K + d_v·s_V)`, where s is bytes/element: f16 = 2, bf16 = 2, q8_0 = 34/32 = 1.0625, q5_0 = 22/32, q4_0 = 18/32 = 0.5625.
- For SWA layers, cap the layer's contribution at `sliding_window` tokens unless `swa_full`.

**DDR budget (user-overridable reserves)**
- `KV_max_bytes = DDR_total − R_os − W_total − R_runtime − R_compute`.
  - R_os: Ubuntu + soft-CPU userspace. Default 1.0–1.5 GiB (assumption carried from the prior notes; unmeasured).
  - R_runtime: llama.cpp + backend about 100–200 MiB (EST).
  - R_compute: logits `V·4 B` per output token + `ubatch·(d + d_ff)·4 B` scratch. For V = 151,936 the logits alone are 0.6 MB per token (EST).
  - W_total: sum the tensor-info sizes exactly. Weights must also be physically contiguous or CMA-allocated for PL access, so add CMA-alignment slack.

**Recommended context**
- `n_ctx_rec = min(context_length_GGUF, floor_to_256(KV_max_bytes / kv_tok), n_ctx_speed)`.
- The speed cap comes from the user's tolerated slowdown σ at full context. Since `tok/s(L) = η·BW/(W + L·kv_tok)`, set `n_ctx_speed = σ·W / kv_tok`.
  - σ = 0.25 means at most 20% slower at a full window.
  - Example: Qwen2.5-1.5B Q4 has W ≈ 0.9 GB and kv_tok (f16) = 28 KiB. With σ = 0.25 that gives about 7.8K tokens. With q8_0 KV (14.9 KiB) it gives about 15K.
- Default tiers: 2K / 4K (Ollama's default) / 8K / max-that-fits.

**KV precision recommendation**
- Default **q8_0 K and V** when the hardware has a flash-attention path; otherwise f16. This halves kv_tok, doubles n_ctx_speed, and has a precedent in Hummingbird (8-bit KV).
- Use q4_0 only as an override, with a warning. Ollama itself warns that high-GQA models lose more precision.
- Hardware must match the runtime choice. The K path needs a Q8_0 dot product (same core as the weights). The V path needs blockwise dequant inside the online-softmax accumulate.

**Placement**
- DDR always.
- On-chip only a K/V tile: `T_kv · n_kv · (d_k + d_v) · s` per layer, e.g. 64 tokens × 2 × 256 × 2 B = 64 KiB.
- A "recent-tokens on-chip" cache would have to hold all layers to save DDR reads. URAM capacity / kv_tok gives about 80 tokens for Qwen2.5-1.5B f16 and about 190 for Qwen2.5-0.5B: negligible versus a 4K context. **Do not offer it as a lever for KV260**; mention it only for parts with ≥ 30 MB URAM.

**GQA effect**
- kv_tok ∝ n_kv. Attention arithmetic intensity in decode ≈ `2·(n_h/n_kv)/s` ops/byte, so GQA groups of 6 (Qwen2.5-1.5B: 12/2) give 6× reuse per K/V byte.
- Flag models with n_kv = n_h (e.g., SmolLM2-1.7B; prior notes) as "KV-heavy". For them, recommend smaller n_ctx and q8_0 KV.

### Gaps
- No measured Ubuntu-on-soft-RISC-V memory footprint (R_os).
- No published perplexity numbers were fetched for KV q8_0/q4_0 on small GQA models. Third-party blogs claim a perplexity delta of about 0.002–0.05 for q8_0, but these are not primary sources, so I did not use them.
- The CMA size limit and fragmentation on a KV260 Ubuntu kernel were not researched.

---

## 3. Decode vs prefill optimization (what changes, balanced designs, mode-switching designs, how to present it as a user choice)

### Takeaway
Decode is a bandwidth-bound GEMV. Its levers are ports, burst layout, dequant throughput, KV precision, and op fusion; PE count is nearly irrelevant above M_dec. Prefill is a compute-bound GEMM. Its levers are DSP count, tile T, and on-chip activation buffers.
- Published KV260 designs are decode-specialized (Hummingbird uses 179 DSP).
- PD-Swap shows that DPR can swap phase-specific attention engines in about 45 ms with about 75% of the cost hidden.

For Hydra, a single slider "decode ↔ prefill" maps naturally to "fraction of the post-decode-floor DSP/LUT budget given to the prefill array", with three to four named presets.

### Cited Findings
- PD-Swap:
  - "Prefill is compute-bound and dominated by dense matrix–matrix operations". Decoding "is memory-bandwidth-bound and dominated by KV-cache traffic".
  - The prefill attention engine is token-parallel and Flash-Attention-style blocked, with Q reuse across KV blocks. The decode engine is memory-centric, with 2 DDR ports each for K and V.
  - Reconfiguration takes about 45 ms on KV260. The swap starts after the last layer's attention and overlaps the remaining projection/FFN (about 31 ms for 128 tokens), hiding about 75% of the overhead.
  - Its DSE "jointly optimizes parallelism degree (PE count) under area constraints".

  — [PD-Swap](https://arxiv.org/html/2512.11550)
- FlightLLM: decode uses matrix-vector ops with fused MISC ops. Prefill uses matrix-matrix ops with blocked sparse attention. Instruction sets are compiled per token-length range ("length-adaptive compilation", e.g. tokens 1–16 share one instruction set), cutting instruction storage from about 1.67 TB to 3.25 GB. — [FlightLLM](https://arxiv.org/html/2401.03868)
- Measured KV260 phase numbers (prior notes):
  - TeLLMe v2: 25 tok/s decode, up to 143 tok/s prefill, 610 DSP.
  - PD-Swap: 27.8 tok/s decode, 30.2 tok/s prefill (its own definition), 750 DSP.
  - Hummingbird: decode-only focus, 179 DSP.

  — [TeLLMe v2](https://arxiv.org/html/2510.15926v2), [PD-Swap](https://arxiv.org/html/2512.11550), [Hummingbird](https://arxiv.org/html/2507.03308v1)

### Inferences **(EST)**

**What changes per mode**

| Lever | Decode-optimized | Prefill-optimized |
|---|---|---|
| MAC lanes | M_dec (about 64–128), LUT MACs OK | as many DSPs as possible (M_pre 512–2048) |
| Array shape | 1-D (K-lanes × 1–4 outputs) | 2-D (32k × c), weight-stationary over T tokens |
| On-chip buffers | small FIFOs; activations of 1 token (d B) | T·d activation tile, accumulators T·cols·4 B |
| DDR ports | all for weights + 2 for K/V | fewer needed, since compute-bound when T ≥ T_min |
| Attention | streaming KV, online softmax, GQA broadcast | blocked flash attention, Q-tile reuse |
| KV precision | q8_0 strongly helps | minor effect |
| Fusion | whole-layer fusion is critical (dispatch overhead, see section 4) | less critical |

**Option set for the "engine topology" lever**
- (a) GEMV-only: smallest. Prefill runs as T sequential GEMVs, so prefill tok/s ≈ decode tok/s, roughly the adamgallas design's "token by token" prefill.
- (b) GEMV + small systolic array, statically shared dequant front-end: the balanced default.
- (c) One reconfigurable-shape array in which the same DSPs act as 1-D lanes in decode and 2-D in prefill. Logic is more complex, but no DSP sits idle.
- (d) DPR swap (PD-Swap). This needs a static/dynamic floorplan and adds about 45 ms per phase switch. It is worth it only when the area of both engines does not fit at once; mark it "advanced".

**Slider mapping** (p ∈ [0, 100], "prefill emphasis")
- `DSP_pre = p/100 · (DSP_total − DSP_dec − DSP_attn − DSP_reserve)`.
- `T = next_pow2(max(T_min, p/100 · T_max))`.
- `URAM_act = T·d·2 + T·cols·4`.
- p = 0 gives topology (a), and p ≥ 20 gives (b).
- Presets:
  - **"Chat / decode-first" (p = 15).**
  - **"Balanced" (p = 50).**
  - **"Long prompts / RAG" (p = 85).**
  - **"Max context"**: q8_0 KV with the n_ctx cap from the memory budget.
- Show the estimated decode tok/s, prefill tok/s, and TTFT for a 512-token prompt beside each preset. Decode tok/s should barely change across the slider. That is the honest message ("prefill buys TTFT, not tok/s").

**Example (EST)** for Qwen2.5-1.5B Q4_K_M at 250 MHz, η = 0.7:
- Decode ≈ 13.44e9 / 0.94e9 ≈ 14 tok/s at every slider position.
- Prefill:
  - p = 0: ≈ 14 tok/s (GEMV-only), so TTFT for 512 tokens ≈ 36 s.
  - p = 50 (about 500 DSP × 2 MAC): ≈ 500·2·2·250e6 / 3.08e9 × 0.6 ≈ 97 tok/s, TTFT ≈ 5.3 s.
  - p = 100 (about 1000 DSP): ≈ 195 tok/s, TTFT ≈ 2.6 s.

### Gaps
- No published KV260 design with a 2-D GEMM prefill array for standard (non-ternary) 1–2B models, so the prefill estimates are uncalibrated.
- The TeLLMe/PD-Swap prefill definitions conflict (prior notes).
- The DPR floorplan constraints on XCK26 (pblock sizes, bitstream size → load time) were not researched beyond PD-Swap's 45 ms.

---

## 4. CPU vs accelerator resource split (LUTs to soft CPU/vector unit vs PEs; honest effect on tok/s and boot/CPU speed)

### Takeaway
On a 117K-LUT part the soft CPU is the largest LUT consumer:
- A Linux-capable 64-bit CVA6-class SoC was reported at about 79K LUTs on Kintex-7 (attribution uncertain, see Gaps).
- A DPU-like engine costs 27–53K LUTs.
- The KV260 decode engine Hummingbird costs 26K LUT / 179 DSP.

Decode tok/s is set by DDR bandwidth once the accelerator covers all per-token ops. CPU speed then affects tok/s only through un-offloaded work: sampling over the vocab, graph dispatch, and the non-offloaded ops. CPU speed dominates boot time and general responsiveness.

The honest model therefore has two regimes:
- If offload level ≥ 3 with fused layer commands, a faster CPU barely changes tok/s and mostly improves boot and UI.
- If offload level ≤ 1, a slow soft CPU can cap tok/s well below the DDR roofline.

### Cited Findings
- CVA6 is a parameterizable 6-stage in-order RV64 Linux-capable core with optional FPU and 32/64-bit configuration. — [CVA6 docs](https://docs.openhwgroup.org/projects/cva6-user-manual/01_cva6_user/Introduction.html)
- A search-result snippet states that "the entire [CVA6] SoC occupied 79,142 LUTs and 58,086 flip-flops on a Kintex 7 (Genesys 2)". The originating paper among [arXiv 2510.12277](https://arxiv.org/pdf/2510.12277) / [arXiv 2305.06946](https://arxiv.org/pdf/2305.06946) was not confirmed, so treat it as indicative only.
- DPU single core: 27–52K LUT for B512–B4096 (section 1). Hummingbird: 26K LUT, 179 DSP. TeLLMe v2: 98K LUT (84%). PD-Swap: 102K LUT (87%). — prior notes and sources therein.
- The Qwen2.5-on-KV260 design profiles matmul at 91.6% of latency, with the remaining approximately 8% (RoPE/RMSNorm/SiLU) on 1.3 GHz-class hard A53s (prior notes, [arXiv 2504.17376](https://arxiv.org/html/2504.17376v1)).

### Inferences — model **(EST)**

**Per-token time**
- `t_tok = max(t_mem, t_acc_compute) + t_cpu + t_sync`.
  - `t_mem = (W + L·kv_tok)/(η·BW)`.
  - `t_cpu = (C_sample + C_ops_on_cpu)/f_cpu/IPC`.
  - `t_sync = n_cmds · t_dispatch`.
- Sampling cost: `C_sample ≈ V · c_s`, with c_s ≈ 5–20 cycles/logit (softmax/top-k/top-p, scalar). For V = 151,936 at 100 MHz and IPC 0.5 that is about 15–60 ms per token, which caps tok/s at about 17–66.
  - That is comparable to the 14–55 tok/s DDR roofline.
  - So **offload argmax/top-k (level 4) or partial-sort on the accelerator** whenever V·c_s/f_cpu > 0.2·t_mem.
  - The DPU's optional argmax/softmax units are the hardware precedent.
- Dispatch cost: `t_sync ≈ n_l · ops_per_layer · t_dispatch`. With 28 layers × about 12 ggml ops × 10–50 µs (MMIO + cache flush on a slow core), that is about 3–17 ms per token, so it must be fused (level 3).
- Non-offloaded vector ops: RMSNorm + RoPE + SiLU are about 10·d + 3·d_ff FLOPs per layer, i.e. about 28 × (15K + 27K) ≈ 1.2 MFLOP per token for Qwen2.5-1.5B. On a 100 MHz soft FPU at about 0.25 FLOP/cycle this is about 47 ms per token, which **would halve or third decode**. So offload level ≥ 1 is mandatory with a soft CPU.

**Trade presentation ("faster CPU or faster array")**
- LUT budget: `LUT_total (117K) × 0.85 utilization ceiling (EST) = LUT_cpu + LUT_dec + LUT_pre + LUT_attn + LUT_infra`.
  - LUT_infra (AXI, DMA, interconnect): about 8–12K (EST).
  - LUT_dec: about 10–26K, with Hummingbird as the upper anchor.
- CPU tiers, each with an estimated LUT cost to be measured:
  - "minimal RV64GC, no FPU-heavy extensions"
  - "RV64GC + FPU + larger caches"
  - "RV64GCV (vector)"
- Offload level must rise as the CPU tier falls; the configurator enforces `offload ≥ f(CPU tier)`.
- Displayed effects:
  1. Decode tok/s: computed by the t_tok model. It is usually flat across CPU tiers once offload is level ≥ 3.
  2. Prefill tok/s / TTFT: driven by LUT_pre/DSP_pre (section 3).
  3. Boot time and general "CPU speed": a relative index ∝ f_cpu·IPC. Do not promise absolute boot seconds without measurement.
- Guardrail: if `LUT_cpu + LUT_dec + LUT_infra > 0.85·LUT_total`, refuse (or drop prefill to p = 0). DSPs are nearly free for the CPU, so DSP mostly goes to the array regardless.

### Gaps
- No measured LUT/FF cost of a Linux-capable soft RV64 on UltraScale+ (XCK26) was found. The 79K figure is Kintex-7 and its attribution is unconfirmed.
- No measured soft-core sampling or dispatch latency. The c_s and t_dispatch ranges are guesses.
- The prior notes flag an open question: whether the hard A53s can be used at all. If they can, this whole section changes, and offload level 1 suffices.

---

## 5. Recommendation logic: how existing generators derive configurations, and which GGUF fields drive each recommendation

### Takeaway
Every mature generator exposes a small number of parallelism knobs with divisibility constraints, plus precision, and derives them either from a throughput target or from a resource budget:
- hls4ml: ReuseFactor + Precision + Strategy.
- FINN: PE/SIMD, set from `target_fps` by SetFolding.
- DPU: a discrete B-size menu + RAM/DSP usage switches + core count.
- Intel FPGA AI Suite: `c_vector`/`k_vector` in a `.arch` file with an optimizer.
- Gemmini: mesh/tile dims, dataflow, datatypes, scratchpad sizes.
- AutoSA: polyhedral DSE over array partitioning and latency hiding.

Hydra should copy that pattern: constraint-checked integer knobs, a throughput-target solver (FINN-style "target tok/s"), and a named-tier menu (DPU-style).

### Cited Findings
- **hls4ml:**
  - `ReuseFactor` is the pipeline initiation interval. Higher values mean fewer resources and more latency.
  - `Precision` is `fixed<X,Y>`/`ap_fixed`, settable at Model, LayerType, or LayerName granularity, with layer settings overriding. Per-layer precision defaults to `'auto'` (inferred) with name granularity.
  - `Strategy` is Latency, Resource, or distributed_arithmetic. `IOType` is io_parallel or io_stream.

  — [hls4ml configuration docs](https://fastmachinelearning.org/hls4ml/api/configuration.html)
- **FINN:**
  - MVAU folding constraints: `MH % PE == 0` and `MW % SIMD == 0`. Total folding = (MH/PE)·(MW/SIMD), the cycles per output.
  - Users either give a folding config or a `target_fps`. `SetFolding` then "first increases SIMD while weight stream width per PE is within limits, then increases PE until the target is met or max PE is reached".
  - PE and SIMD default to 1 (maximum folding).

  — [FINN internals / search excerpt](https://finn.readthedocs.io/en/latest/internals.html); [FINN fpgadataflow transforms](https://finn.readthedocs.io/en/latest/source_code/finn.transformation.fpgadataflow.html); [FINN nw_prep](https://finn.readthedocs.io/en/latest/nw_prep.html)
- **AMD DPU:** the discrete size menu B512–B4096 (named by peak ops/clock), 1–4 cores, RAM high/low, DSP high/low, URAM, and optional softmax/argmax/depthwise units, with published per-size resource tables (section 1). — [PG338 mirror](https://www.readkong.com/page/dpuczdx8g-for-zynq-ultrascale-mpsocs-product-guide-6779141)
- **Intel/Altera FPGA AI Suite:**
  - Instances are configured by a protobuf `.arch` file.
  - `c_vector` (dot-product width per PE) takes values 4/8/16/32.
  - `k_vector` (number of PEs) ranges 4–128 and must be a multiple of c_vector.
  - The compiler can generate an optimized architecture. Hand-editing "requires a deep knowledge … and is not recommended".

  — [FPGA AI Suite arch file format](https://www.intel.com/content/www/us/en/docs/programmable/768974/2024-3/architecture-description-file-format.html); [IP block configuration](https://www.intel.com/content/www/us/en/docs/programmable/768974/2023-3/ip-block-configuration.html)
- **Gemmini:** parameters in section 1. — [Gemmini README](https://raw.githubusercontent.com/ucb-bar/gemmini/master/README.md)
- **AutoSA:** a polyhedral compiler from C loop nests to systolic arrays. It exposes "a set of tuning knobs that can either be changed manually or set by an auto-tuner" (Odyssey), and has HLS C, Intel OpenCL, Catapult and TAPA backends. — [AutoSA FPGA'21](https://dl.acm.org/doi/10.1145/3431920.3439292); [Odyssey arXiv 2111.14252](https://arxiv.org/pdf/2111.14252)
- **PD-Swap:** DSE over PE parallelism under LUT/URAM/BRAM constraints. **SECDA-DSE:** LLM-guided DSE, no perf model (prior notes). — [PD-Swap](https://arxiv.org/html/2512.11550)
- Not fetched this session: DNNWeaver and Allo (see Gaps).

### Inferences — Hydra recommendation pipeline **(EST)**

1. **Parse** the GGUF header, KVs and tensor infos only (prior notes). Compute:
   - `W_total` = Σ tensor bytes.
   - `W_stream` = Σ bytes of tensors read per token. Exclude `token_embd` unless tied as the output.
   - For MoE: `W_stream = W_dense + (expert_used_count/expert_count)·W_experts`.
   - The type histogram S, and `b_w = W_stream / N_stream`.
2. **Hard constraints** (fail or warn):
   - `W_total + R_os + R_runtime + n_ctx_min·kv_tok ≤ DDR`.
   - Every type in S is supported, or a fallback is chosen.
   - d, d_ff and n_h·d_h are multiples of 32 (true for all common models), so rows = 32k divides K; a FINN-style divisibility check.
3. **Decode floor:** M_dec, n_ports, offload level ≥ f(CPU tier) (sections 1 and 4).
4. **Budget the remainder** (DSP, LUT, BRAM, URAM after CPU + infra + decode + attention) and apply the slider p to size the prefill array (section 3).
5. **Memory:** n_ctx_rec, KV type (section 2).
6. **Report** an estimate with error bars and a "binding constraint" label: "DDR-bound", "LUT-bound (CPU)", "DSP-bound (prefill)", "Memory-bound (n_ctx)".

**GGUF field → lever map**

| GGUF field | Drives |
|---|---|
| tensor types (tensor-info table) + `general.file_type` | datapath unpackers (L4), b_w → M_dec (L1), ports (L8), decode tok/s |
| tensor sizes | W_total (DDR fit), W_stream (tok/s) |
| `{arch}.embedding_length` d | activation buffer T·d (L6), RMSNorm width, attention engine width, prefill tile |
| `{arch}.feed_forward_length` | largest K → accumulator bits (L7), SiLU/mul unit width, scratch |
| `{arch}.block_count` | kv_tok, dispatch count (fusion need), use_more_bits mix |
| `{arch}.attention.head_count`, `head_count_kv` | GQA ratio → attention engines (L11), kv_tok, decode attention intensity |
| `{arch}.attention.key_length`/`value_length` | d_k/d_v for kv_tok and the attention datapath |
| `{arch}.attention.sliding_window` | SWA KV cap (llama.cpp `--swa-full`) |
| `{arch}.context_length` | upper bound for n_ctx_rec |
| `{arch}.rope.dimension_count`, `freq_base`, `rope.scaling.type` | RoPE unit (partial rotary dims, CORDIC/table sizing, YaRN-type scaling support check) |
| `{arch}.attention.layer_norm_rms_epsilon` | RMSNorm constant (or LayerNorm vs RMSNorm → norm unit type) |
| `{arch}.vocab_size` (or token_embd dims) | lm_head size, sampling cost → argmax/top-k offload decision (section 4), logits buffer |
| `{arch}.expert_count`/`expert_used_count` | MoE W_stream, router/top-k unit, MXFP4 unpacker |
| `general.architecture` | op set (activation GELU vs SiLU, QK-norm, bias terms) → feature flags, or "unsupported arch" |

### Gaps
- DNNWeaver, Allo, and AMD's guidance on choosing a DPU size for a given device were not fetched. My recollection that the KV260 vision apps ship a B3136 DPU is BG and unverified.
- FINN's exact cycle and resource estimation formulas (`get_exp_cycles`, LUT/BRAM estimators) were not quoted.
- No published analytical recommender for GGUF→FPGA exists, as far as I found. That novelty is consistent with the prior notes.

---

## 6. How LLM runtimes present choices to users (UX precedent for tiers)

### Takeaway
Runtimes converge on four things:
- A few memory-driven knobs: context length, KV cache type, flash attention, and a GPU offload amount as a 0–100% / layers / max slider.
- An automatic "fit" mode that fills any unset knob from device memory.
- A pre-load memory estimate with guardrails.
- Quantization chosen implicitly by which GGUF file you pick.

Hydra can mirror this:
- Auto-fill every lever ("fit"); every lever is overridable.
- An `--estimate-only` style report before generation.
- A percent slider for the resource split, with named presets.

### Cited Findings
- llama.cpp:
  - `--fit on` (default) adjusts unset arguments to fit device memory.
  - `--n-gpu-layers` takes a number, `auto`, or `all`.
  - `--ctx-size 0` means "loaded from model".
  - `--batch-size` defaults to 2048 (logical) and `--ubatch-size` to 512 (physical).
  - `--cache-type-k/v`, `--flash-attn auto`.

  — [llama.cpp server README](https://raw.githubusercontent.com/ggml-org/llama.cpp/master/tools/server/README.md)
- LM Studio:
  - `lms load --gpu` takes `0-1`, `off`, or `max` (0.5 = "50% of layers to GPU"). `--context-length` sets context.
  - `--estimate-only` will "Print a resource (memory) estimate and exit without loading". The estimate accounts for "context length, flash attention, and whether the model is vision-enabled" and reports whether "This model may be loaded based on your resource guardrails settings".

  — [LM Studio lms load docs](https://lmstudio.ai/docs/cli/local-models/load)
  - The GUI shows a 0–100% GPU-offload slider ([third-party guide](https://herdingbots.ai/primers/lm-studio-load-settings/), secondary source).
- Ollama:
  - Automatic GPU fit ("first checks if it fits entirely on a single GPU").
  - `OLLAMA_CONTEXT_LENGTH`/`num_ctx`, default 4096.
  - `OLLAMA_KV_CACHE_TYPE` f16/q8_0/q4_0 with plain-language trade-offs ("1/2 the memory … very small loss").
  - Automatic flash attention.

  — [Ollama FAQ](https://raw.githubusercontent.com/ollama/ollama/main/docs/faq.mdx)
- AMD DPU: users pick from a discrete menu of named sizes (B512…B4096) plus on/off feature options, backed by per-size resource tables. — [PG338 mirror](https://www.readkong.com/page/dpuczdx8g-for-zynq-ultrascale-mpsocs-product-guide-6779141)
- Intel FPGA AI Suite discourages hand-editing `.arch` and prefers compiler-generated architectures. — [Intel arch file docs](https://www.intel.com/content/www/us/en/docs/programmable/768974/2024-3/architecture-description-file-format.html)

### Inferences — proposed Hydra UX **(EST)**

**Three layers of control**
1. **Presets**: Chat / Balanced / Long-prompt / Max-context / CPU-first (boot and desktop responsiveness over prefill).
2. **Sliders**:
   - "Prefill emphasis" 0–100%, mapping to DSP_pre and T.
   - "CPU share" 0–100%, mapping to the CPU tier, with the offload level auto-raised.
   - "Context" in tokens, with a live DDR bar split into OS / weights / KV / scratch.
3. **Expert table**: every lever L1–L12 plus the KV fields with recommended value, override box, constraint check, and the reason (for example "M_dec = 128 because Q4_K_M b_w = 0.60 B and η·BW = 13.4 GB/s").

**Guardrails and estimate report**
- An `--estimate-only` report (LM Studio precedent) showing:
  - Resource use vs 117K LUT / 1248 DSP / 144 BRAM / 64 URAM.
  - DDR map.
  - Decode tok/s at L = 0 and L = n_ctx.
  - Prefill tok/s and TTFT(512).
  - The binding constraint.
  - Labels that mark the numbers as estimates.
- Fit mode (llama.cpp `--fit` precedent): any lever the user leaves unset is solved, and any lever the user sets is respected or reported as infeasible with the violated constraint.
- KV type picker worded like Ollama's (f16 / q8_0 "½ memory, very small loss" / q4_0 "¼ memory, small-medium loss"). If the hardware lacks a flash-attention path, grey out quantized V, matching llama.cpp's own rule.

### Gaps
- The LM Studio GUI slider semantics (percent of layers vs memory) come only from secondary sources plus the CLI doc. Not verified against LM Studio's GUI docs.
- No precedent was found for FPGA-tool UX that exposes a "decode vs prefill" slider. This appears novel.
