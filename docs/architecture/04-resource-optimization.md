# 04 Resource Optimization

## Memory and KV Cache

Content merged from `memory-optimization.md` and `04-kv-cache-and-long-context.md`.

- Guidance on KV cache sizing and eviction
- Long-context handling strategies
- Practical memory tuning tips for Project Vyasa services

## Long Context and Sliding Windows

- Managing extended prompts and documents
- Sliding window and chunking strategies
- Trade-offs between recall and compute

## Operational Tips

- Monitor GPU and system memory utilization
- Align model selection with available memory
- Prefer deterministic chunk sizes for reproducibility
