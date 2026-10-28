# EIL architecture decision record (ADR-001)

## Mission
An agent-driven investigation system that uses evidence from structured measurements, manuals/PDFs, and authorized tools to answer engineering questions. The first supported scenario is manufacturing false-ejection analysis.

## Boundaries
- `analytics.py`: deterministic analysis and source identification, never LLM arithmetic.
- `agent.py`: optional framework-based tool-using agent. Uses Deep Agents (on LangGraph), not a custom agent loop.
- `api.py`: local FastAPI integration and input validation.
- `data/`: generated synthetic evidence. `ground_truth.json` is eval-only; do not expose to agent.
- `tests/`: reference expectations independent of the model.

## Target architecture (not all implemented)
React UI -> FastAPI -> persistent investigation jobs -> LangGraph workflow -> Deep Agents research/planning -> allowlisted tools (DuckDB, Docling retrieval, MCP) -> evidence store/report.

## Execution/approval policy
M1 analytic tools are read-only. An explicit Deep Agents `StateBackend` holds only virtual state, with `FilesystemMiddleware` exposing `ls`, `read_file`, `glob` and `grep`. It does not mount the machine's filesystem. File-writing, deletion, execution and default subagent dispatch are disabled. Offline tests verify both tool binding and rejection of forged calls. Later: add LangGraph persistence, resource quotas, approval interrupts and an explicit network/filesystem sandbox BEFORE exposing any execution tool. Do not rely on prompting to enforce permissions.

## Design trade-offs
- M1 uses standard-library CSV aggregation to keep baseline analysis testable without framework packages. Introduce DuckDB when generalizing query patterns, never raw model-authored SQL against unrestricted stores.
- M1 API is synchronous and uses per-call agent creation. Future job management is required for production-like workloads.
- No vector database until document retrieval evaluation justifies one. Start with full-text retrieval and citations.
- Multi-agent only after comparison with a single-agent baseline.
