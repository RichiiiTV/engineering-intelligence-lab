# Development milestones (Codex-led)

## M1 — Synthetic data and working agent scaffold (included)
- deterministic baseline metrics and evidence IDs
- FastAPI read endpoints and optional Deep Agents + Ollama CLI
- unit/integration tests on synthetic incident
- Review: known anomalous station S03 ranks first; baseline and offline graph/permission tests verified. See `review-results.md`. Manual live-agent smoke remains pending because Ollama was unavailable. No later milestone has started.

## M2 — Real agent execution infrastructure
- persistent LangGraph checkpoints with distinct investigation threads
- async job queue and streaming events to UI
- bounded steps/tokens/time, error handling, cancellation
- model adapter and tests with mocked tool-calling models
- Acceptance: resume interrupted run, no cross-run data leakage, failure cases pass

## M3 — PDF+CSV evidence ingestion
- Docling PDF ingestion including tables and page metadata
- document chunk provenance and lexical retrieval, then optional vector retrieval
- multiple allowlisted CSV uploads; schema validation and per-case file isolation
- export citations, query provenance and calibrated uncertainty
- Acceptance: golden fixture returns correct document page + correct CSV finding

## M4 — Agentic user experience and MCP
- React UI case list, event timeline, tool-call detail, charts, report drafts
- approved read-only MCP adapter (mock server first)
- explicit human approvals for actions that change data
- Acceptance: user can start case, inspect evidence, pause/resume and export report

## M5 — Evaluation, observability and advanced agents
- known-cause and ambiguous incident benchmark; tool selection, correct evidence, hallucinations
- local tracing; optional self-hosted Langfuse
- single-agent versus subagent experiment with cost/latency comparison
- provider benchmark for GTX 1080 Ti Ollama and hosted model
- Acceptance: reproducible scorecards and regression gates

## Out of scope initially
- GMP claims, production equipment control, Veeva/SAP/Siemens integrations, unconstrained code execution
