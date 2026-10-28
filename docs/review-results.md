# M1 foundation review — 2026-10-28

The requested foundation review is complete. Deterministic analytics, offline Deep Agents
integration, permission checks, lint and the local FastAPI HTTP smoke passed. Ollama was
unavailable during that original review. The subsequent user-requested live verification
passed after two compatibility fixes; see [ollama-verification.md](ollama-verification.md).
M2 has not started.

## Environment and reproducibility

The supplied starter ZIP was extracted into the previously empty project workspace.
Read `AGENTS.md`, `README.md`, `docs/codex-task-01-review.md`, `docs/architecture.md` and
`docs/roadmap.md` before implementation. The review stayed within task 01.

| Component | Tested version |
| --- | --- |
| Platform | Windows, PowerShell |
| uv | 0.13.5 |
| Python | CPython 3.12.15 |
| deepagents | 0.7.32 |
| langgraph | 1.2.18 |
| langchain | 1.4.7 |
| langchain-core | 1.7.1 |
| langchain-ollama | 1.1.0 |
| ollama Python client | 0.6.3 |
| FastAPI / Starlette | 0.162.0 / 1.10.0 |
| httpx | 0.28.1 |
| pytest / Ruff | 9.2.0 / 0.17.3 |

`uv.lock` records 173 resolved packages, including metadata for the existing optional
`documents` extra. The tested dev environment contains 72 installed distributions.
The optional document stack was not installed or exercised. `.python-version` selects
Python 3.12, rather than the unrelated Python 3.8.10 executable on the user's PATH.
Minimum Deep Agents and ChatOllama constraints now reflect the reviewed API versions;
direct imports of httpx and the Ollama client are declared dependencies.

## Compatibility and changes

The existing `create_deep_agent(model=..., tools=..., system_prompt=...,
checkpointer=InMemorySaver())` call is compatible with the installed versions. No replacement
agent loop or provider substitution was needed. Compatibility was checked against official
documentation and the installed package source/signatures:

- [Deep Agents customization and middleware overrides](https://docs.langchain.com/oss/python/deepagents/customization)
- [StateBackend versus host filesystem and shell backends](https://docs.langchain.com/oss/python/deepagents/backends)
- [ChatOllama setup, model validation and tool calling](https://docs.langchain.com/oss/python/integrations/chat/ollama)
- [Deep Agents harness profiles](https://docs.langchain.com/oss/python/deepagents/profiles)

The starter's read-only description omitted default virtual file-write and delegation tools.
The app now supplies an explicit `StateBackend`, replaces `FilesystemMiddleware` with a
read-only tool allowlist, and disables Ollama's default general-purpose subagent through the
documented harness profile API. Profiles are a beta API; upgrades must rerun the offline
tool-surface tests. The exact observed model-visible tools were:

`compare_station_performance`, `inspect_station`, `ls`, `read_file`, `glob`, `grep`.

Offline tests execute both analytics tools through the actual compiled graph, check their
evidence rows and reject forged calls to `execute`, `eval`, `write_file`, `edit_file`,
`delete` and `task`. Virtual reads cannot open the host source file, a Windows system path,
or `/data/ground_truth.json`. No host filesystem, shell, interpreter, network-fetch tool,
MCP tool, skills folder or memory file is supplied. Framework context offloading can still
write its own virtual state; this grants no host-file access.

Dataset paths now resolve before checking the allowlist, so symlink targets outside `data/`
and explicit `load_rows(path=...)` arguments cannot bypass the directory/file boundary.
Tests cover explicit outside paths and configured traversal/absolute paths. No Windows
symlink was created in this review. The ground-truth file remains evaluation-only.

The adapter now validates the installed model at initialization and sets 5-second connection
and 60-second HTTP inactivity timeouts, ignoring ambient HTTP proxy settings for the local
service. Missing model, connection failures, inference timeouts and Ollama rejected requests
produce actionable local errors. The CLI returns exit code 1 without a traceback for those
errors; the API returns HTTP 503. Blank/oversized API questions return 422 before inference.
No model was downloaded and no paid provider was selected.

Ruff lint/import/format checks are configured, existing style issues were corrected, and
`run-demo.ps1` now runs the lint and format checks before tests. Analytics calculations are
unchanged.

## Commands and observed results

Commands were run from the project root. In this managed environment, uv's default cache
was not writable, so sessions used:

```powershell
$env:UV_CACHE_DIR = Join-Path (Get-Location) '.uv-cache'
```

The initial sandboxed package fetch failed because DNS/network access was restricted.
Dependency downloads completed with approved external network access. FastAPI TestClient
stalled in the socket-restricted sandbox; the run was stopped, and the same tests completed
with local socket support outside it. Those environment failures are not recorded as passes.

| Command/check | Result |
| --- | --- |
| `uv sync --extra dev` | Resolved and installed the dev environment |
| Original `uv run pytest -q` | 8 passed in 0.37s |
| Initial Ruff checks | Found import/unused-import and formatting issues; fixed |
| `uv lock --offline` | Lockfile resolved using downloaded metadata |
| `uv sync --locked --extra dev` | Locked environment verified |
| `uv lock --check --offline` | Lockfile current |
| Original review `uv run pytest -q` | 43 passed; includes actual graph execution with scripted model, permissions, adapter, API and CLI failure cases; follow-up suite has 44 |
| `uv run ruff check .` | All checks passed |
| `uv run ruff format --check .` | All discovered source files formatted |
| `uv pip check` | All 72 installed packages compatible |
| `uv run python -m eil.cli demo` | Exit 0; S03 ranks first |
| Real Uvicorn server, loopback port 8765 | Startup succeeded; server stopped after HTTP checks |
| `GET /api/health`, `/api/datasets`, `/api/metrics/summary`, `/api/metrics/stations/S03`, `/api/investigations/demo-report`, `/docs` | All returned HTTP 200 with expected results |
| `POST /api/investigations`, whitespace-only question | HTTP 422; no inference |
| Original `GET http://localhost:11434/api/tags` outside socket restrictions | Connection refused; service became available during the later follow-up |
| Original `uv run python -m eil.cli agent` | Skipped during the original review; passed in the later follow-up |

The deterministic report found S03 increasing from **1.6123%** to **14.1144%**, a
**12.5021 percentage-point** rise. It retains evidence row IDs and labels concurrent lighting
and exposure changes as a hypothesis, without claiming causation.

Local raw artifacts are in ignored `reports/`: `demo-review.json`, `api-review.json` and
`uvicorn-review.*.log`. Offline tests forbid HTTP sends while using scripted model responses;
real ChatOllama initialization is separately tested with a stubbed model listing.

## Remaining unverified behavior and stopping point

- The follow-up verified `qwen3.5:4b-q8_0` through the real local Ollama API, real tool
  execution and the default CLI question. General output quality, performance and context
  limits across tasks have not been benchmarked. See the separate verification report.
- Model availability validation does not establish tool support or reliable evidence use.
  Scripted responses prove integration wiring and tool boundaries, not LLM reasoning quality
  or resistance to all prompt injection.
- The existing 35-step recursion limit and per-request timeouts are not a total wall-clock or
  token budget. Graph recursion exhaustion and malformed model output can still fail a run.
  Hard cancellation, persistence, queues and production resource policies remain later work.
- No optional document ingestion, PDF RAG, MCP server, UI, Langfuse, production connection or
  later-milestone execution infrastructure was implemented.

To repeat live validation manually, start Ollama, confirm the configured model appears in
`/api/tags` or `ollama list`, then run `uv run python -m eil.cli agent`. Check that it calls
analytics tools, cites returned row IDs, identifies S03 and distinguishes hypotheses from
evidence. Do not treat a fluent answer without tool evidence as a successful smoke test.

Stop after this report. A later milestone requires a separate user request.
