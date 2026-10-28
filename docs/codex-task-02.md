# Codex task 02 — Add durable, inspectable agent execution

Read `AGENTS.md`, `docs/architecture.md`, and `docs/roadmap.md`. Work only on the next milestone after M1.

## Objectives
1. Verify current Deep Agents, LangGraph and langchain-ollama APIs from official docs and record tested versions via `uv lock`.
2. Add an integration test using a fake tool-calling chat model or controlled stub; do not require Ollama or paid APIs for CI.
3. Add a durable SQLite checkpointer using documented LangGraph checkpointing. Keep state scoped by investigation/thread ID.
4. Introduce an investigation-run service that records run ID, start/end, status, tool calls, and errors.
5. Add bounded runtime controls and an interrupt/cancel mechanism for development usage.
6. Preserve the read-only tool boundary and avoid exposing host filesystem/shell/network capabilities.
7. Document how to run an optional manual Ollama smoke test on Windows.

## Acceptance
- `uv run pytest -q` passes offline.
- At least one test verifies resume/recovery and one verifies isolation between investigation threads.
- Failure of Ollama gives actionable error, not an unhandled stack trace in API.
- A test confirms unsupported station ID cannot escape the dataset allowlist.
- No PDF, UI, MCP or production API integration is added in this task.

## Reporting
Summarize architecture, files changed, dependency versions, commands/tests run, unresolved risks. Stop after M2.
