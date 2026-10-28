# EIL architecture decision record (ADR-001)

## Mission
An agent-driven investigation system that uses evidence from structured measurements, manuals/PDFs, and authorized tools to answer engineering questions. The first supported scenario is manufacturing false-ejection analysis.

## Boundaries
- `analytics.py`: deterministic analysis and source identification, never LLM arithmetic.
- `agent.py`: optional framework-based tool-using agent. Uses Deep Agents (on LangGraph), not a custom agent loop.
- `api.py`: local FastAPI integration and input validation.
- `runs.py`: transactional SQLite run records, durable queue, event log and budget counters.
- `service.py`: single-owner dispatcher, Windows-spawn worker supervision and process cancellation.
- `execution.py`: standard Deep Agents middleware for budgets/tool audit and LangGraph SQLite checkpoints.
- `data/`: generated synthetic evidence. `ground_truth.json` is eval-only; do not expose to agent.
- `tests/`: reference expectations independent of the model.

## Target architecture (not all implemented)
React UI -> FastAPI -> persistent investigation jobs -> LangGraph workflow -> Deep Agents research/planning -> allowlisted tools (DuckDB, Docling retrieval, MCP) -> evidence store/report.

## Execution/approval policy
M1/M2 analytic tools remain read-only. An explicit Deep Agents `StateBackend` holds virtual state persisted by the thread's `SqliteSaver`, with `FilesystemMiddleware` exposing `ls`, `read_file`, `glob` and `grep`. It does not mount the machine's filesystem. File-writing, deletion, execution and default subagent dispatch are disabled. Offline tests verify tool binding and forged-call rejection. The host application's fixed worker process is not an agent-accessible execution capability. A separate security design, approval policy and sandbox are still required before exposing any execution tool.

## M2 execution

The CLI and HTTP API submit a UUID-scoped job to `runs.sqlite3`. A single background dispatcher
starts one trusted Python worker at a time. The worker constructs the existing Deep Agents
graph with `SqliteSaver` in `checkpoints.sqlite3`, using the generated run ID as its thread ID.
Run limits and model configuration are frozen in the run record, and counters survive resume.
No API field selects a model, thread ID, filesystem path or worker function.

State databases and ownership locks live under `.eil/` or a trusted `EIL_STATE_DIR`. Separate
SQLite exclusive locks prevent two API/CLI services, or overlapping real workers after a
restart, from using the same execution directory. An orphan watcher exits a real worker when
its parent disappears. An active run becomes `interrupted` on shutdown/recovery; queued jobs
remain queued. Recovery resumes pending LangGraph nodes with `None`, never a second user
question. Checkpoint writes use `durability="sync"`.

Pause and cancellation terminate the worker, including blocked synchronous model I/O. Pause
is a development process interruption, not a human-approval LangGraph `interrupt()` prompt.
The last committed checkpoint is recoverable, and an unfinished read-only node can repeat.
Cancellation is final. Model attempts and token reservations are charged before a call, so
restarting or pausing does not refund unknown work. The parent independently monitors total
active time across attempts; paused/queued time does not count.

The event log records status transitions, checkpoint nodes, model usage, requested tools,
arguments, observations and errors. The SSE endpoint replays only the requested run's events
and supports a persisted cursor; it streams run/tool events, not token-by-token model output.
Only controlled errors reach API records. Automatic model summarization is disabled because
its internal model calls would bypass the external run-budget hooks.

## Design trade-offs
- M1 uses standard-library CSV aggregation to keep baseline analysis testable without framework packages. Introduce DuckDB when generalizing query patterns, never raw model-authored SQL against unrestricted stores.
- M2 uses one active worker with up to twenty queued jobs. This is a local development service, with no distributed queue, authentication or retention policy.
- No vector database until document retrieval evaluation justifies one. Start with full-text retrieval and citations.
- Multi-agent only after comparison with a single-agent baseline.
