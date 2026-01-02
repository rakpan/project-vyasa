# 05 Telemetry and Observability

Content merged from `05-performance-and-observability.md` and `opik-observability.md`.

## Performance Baselines
- Throughput and latency benchmarks for core services
- GPU/CPU utilization patterns and recommended alerts

## Telemetry Stack
- Structured logging for Orchestrator and Console
- Metrics collection (Prometheus/OpenMetrics)
- Tracing/Opik integration (non-blocking)

## Opik Observability
- Advisory traces for node execution
- Handling trace failures (must not block workflow)
- Tagging jobs/projects for drill-down

## Dashboards and Alerting
- Recommended panels for queue depth, node latency, GPU/CPU use
- Alert thresholds for backpressure and failures
