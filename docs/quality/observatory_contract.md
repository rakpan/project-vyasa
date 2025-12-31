# Vyasa Observatory API Contract

The observatory response is the single source of truth for the KPI dashboard. The backend **must** conform to this contract; the frontend consumes it without additional shaping.

## Response Shape

- Object keyed by panel:
  - `quality`, `context`, `performance`, `hardware`, `volume`
- Each panel object:
  - `status`: `"online" | "warning" | "critical"` (panel health)
  - `summary`: object of primary KPI point-in-time values (latest)
  - `series`: object of KPI sparkline series
    - Each series is an array of **exactly 60** points ordered oldest → newest
    - Point shape: `{ "timestamp": ISO-8601 string, "value": number }`

### Panel KPIs and Units

**Quality**
- `conflict_rate`: conflicts / vetted_claims (0–1 ratio)
- `unsupported_rate`: unsupported findings / vetted_claims (0–1 ratio)

**Context**
- `tokens_per_claim`: average tokens consumed per vetted claim (number)
- `retrieval_hit_rate_at_5`: fraction of claims where the correct source is in top-5 retrieval results (0–1 ratio)

**Performance**
- `p95_latency_ms`: end-to-end p95 latency in milliseconds (number)
- `tokens_per_sec`: throughput split by phase:
  - `prefill`: tokens/sec during prompt ingestion
  - `decode`: tokens/sec during generation

**Hardware**
- `uma_utilization_pct`: unified memory utilization percent (0–128 range maps to 0–128GB)
- `kv_cache_fill_pct`: KV cache fill level percent (0–100)

**Volume**
- `minted_claims_24h`: vetted claims minted in the last 24h (integer, verified by expert)

### Example (abbreviated)

```json
{
  "quality": {
    "status": "online",
    "summary": {
      "conflict_rate": 0.03,
      "unsupported_rate": 0.07
    },
    "series": {
      "conflict_rate": [
        { "timestamp": "2025-02-20T10:00:00Z", "value": 0.04 },
        { "timestamp": "2025-02-20T10:05:00Z", "value": 0.03 }
      ],
      "unsupported_rate": [
        { "timestamp": "2025-02-20T10:00:00Z", "value": 0.08 },
        { "timestamp": "2025-02-20T10:05:00Z", "value": 0.07 }
      ]
    }
  }
}
```

Refer to `schemas/observatory_response.schema.json` for the authoritative machine-readable schema.***
