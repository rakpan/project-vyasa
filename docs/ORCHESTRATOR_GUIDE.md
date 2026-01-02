# Orchestrator Guide (LangGraph 0.3.x)

## State-First Architecture
- **Canonical State**: `ResearchState` (TypedDict) with reducer semantics:
  - Control keys: `jobId`, `threadId`, `revision_count`
  - Reducers: `messages` (Annotated[list, add_messages]), `triples` (Annotated[list, operator.add]), `artifacts` (Annotated[list, operator.add])
- **Checkpointing**: `InMemorySaver` (LangGraph checkpoint.memory) is shared across `graph.compile()` to persist state per `thread_id`.
- **Execution Config**: Every invoke/stream passes `{"configurable": {"thread_id": jobId}}` to bind checkpoints and threads.

## Committee of Experts & Contracts
- **Vision**: Extracts visuals/claims, appends to `extracted_json.triples`; retries enabled.
- **Cartographer**: Extracts claims/entities, populates `extracted_json`.
- **Lead Counsel**: Routes detail/summary presentation.
- **Logician**: Validates math/logic; retries enabled; updates `critic_status`/flags.
- **Critic**: Applies rigor, sets `critic_status`, may increment `revision_count`.
- **Reframer**: Builds `ReframingProposal`, sets `needs_signoff`, triggers interrupt (human signoff).
- **Synthesizer**: Produces `synthesis`/`final_text`.
- **Artifact Registry**: Emits `manifest` artifact (word_count, table_count, citations_verified) and appends to `artifacts`.
- **Tone Validator**: Applies anti-sensation normalization using `deploy/forbidden_vocab.yaml` to rewrite `synthesis/final_text`.
- **Saver**: Persists results; terminal node.

## Interrupts & Human-in-Loop
- **Reframing Interrupt**:
  - Node configured with `interrupt_before=["reframing"]`; inside node calls `interrupt(proposal_dict)`.
  - State marks `needs_signoff=True`, `reframing_proposal_id=<id>`.
  - Console surfaces the `interrupt()` payload (proposal) for human review.
  - Resume: UI posts the approved decision; orchestrator resumes from the last checkpoint with the same `thread_id` using `workflow_app.invoke(None, config={"configurable": {"thread_id": job_id}})`, continuing to saver with updated state.

## Event Streaming (LangGraph v2)
- `astream_events(..., version="v2")` powers the Console heartbeat:
  - `on_node_start` events for Brain/Logician/Vision map to sidebar badges.
  - Stream delivered via FastAPI SSE endpoint `/events/{job_id}` (proxied to Next.js).
- Telemetry is best-effort; Opik failures are caught and never block the stream.

### API Reference: /api/jobs/stream (v2 events)
- Endpoint: `/events/{job_id}` (SSE), proxied via Next.js.
- Schema (examples):
  - `{"event": "on_node_start", "name": "vision", "state": {...}}`
  - `{"event": "on_interrupt", "name": "reframing", "state": {...}, "value": {...}}`
  - `{"event": "on_end", "state": {...}}`
- Clients should treat stream as append-only, handle reconnects, and ignore unknown fields.

## Resilience & Retries
- Per-node retry policies: Vision and Logician use `RetryPolicy(max_attempts=3)`.
- Checkpoints enable resume after interrupts or failures; state is merged via reducers to avoid loss.
