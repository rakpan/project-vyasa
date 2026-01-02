# 07 Agent Orchestration API

Content consolidated from `agent-workflow.md` and `api-spec.md`.

## Workflow Overview
- LangGraph-based orchestrator
- Node roles: Cartographer, Critic, Reframer, Synthesizer, Tone/Precision guards, Saver
- Interrupts and resume semantics (thread_id)

## API Surface
- Job submission and status endpoints
- Event stream (`astream_events` v2) for UI heartbeat and interrupts
- Manifest download endpoints

## Contracts and Rigor
- Artifact manifest contract (claims, citations, density)
- Tone/Precision contracts and conservative vs exploratory behavior

## Integration Notes
- Proxy expectations for Console
- SSE/event stream consumption patterns
