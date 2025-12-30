# Memory Optimization for DGX Spark (GB10)

## Overview

This document describes the mixed precision quantization strategy for maximizing the 128GB unified memory pool on DGX Spark (GB10).

## Quantization Strategy

### Cortex-Brain (Llama 3.3 70B)
- **Quantization**: FP8
- **Rationale**: Preserves reasoning logic while reducing memory footprint
- **Memory Savings**: ~50% reduction vs FP16
- **Estimated Weight Size**: ~35GB (FP8) vs ~70GB (FP16)

### Cortex-Worker (Qwen 2.5 32B)
- **Quantization**: FP4
- **Rationale**: Maximum memory efficiency for extraction tasks (high throughput, lower precision acceptable)
- **Memory Savings**: ~75% reduction vs FP16
- **Estimated Weight Size**: ~8GB (FP4) vs ~32GB (FP16)
- **KV Cache Scaling**: 
  - `--max-running-requests 4`: Increased concurrency due to reduced weight size
  - `--context-length 16384`: Extended context window for better extraction

### Cortex-Vision (Qwen2-VL 72B)
- **Quantization**: INT8
- **Rationale**: Balanced precision/performance for vision tasks
- **Memory Savings**: ~50% reduction vs FP16
- **Estimated Weight Size**: ~36GB (INT8) vs ~72GB (FP16)

## Memory Estimate

### Total Weights (Quantized)
- Brain (FP8): ~35GB
- Worker (FP4): ~8GB
- Vision (INT8): ~36GB
- **Total Weights**: ~79GB

### Remaining for KV Cache
- **Total Memory**: 128GB
- **Model Weights**: ~79GB
- **System Overhead**: ~5GB
- **Available for KV Cache**: ~44GB

### KV Cache Allocation
- **Brain**: ~15GB (2x TP, moderate context)
- **Worker**: ~20GB (4 concurrent requests × 16K context)
- **Vision**: ~9GB (2x TP, image processing)

## Validation Logic

The `critic_node` includes FP4 failure detection to catch quantization artifacts:

1. **Repetitive Token Detection**: Identifies sequences of 3+ identical tokens
2. **Garbled Text Detection**: Checks for low alphanumeric ratio (<30%)
3. **Special Character Overload**: Detects excessive special characters (>50%)

If quantization failure is detected, the extraction is marked as `FAIL` immediately, preventing downstream processing of corrupted data.

## Performance Trade-offs

| Model | Quantization | Precision Loss | Memory Savings | Use Case |
|-------|-------------|----------------|----------------|----------|
| Brain | FP8 | Minimal | ~50% | Reasoning, routing |
| Worker | FP4 | Moderate | ~75% | High-throughput extraction |
| Vision | INT8 | Moderate | ~50% | Image understanding |

## Notes

- FP4 quantization may occasionally produce garbled text or repetitive tokens
- The validation logic in `critic_node` catches these failures early
- If FP4 kernels are not available, fallback to AWQ or GPTQ quantization formats
- Monitor extraction quality metrics to tune quantization settings

