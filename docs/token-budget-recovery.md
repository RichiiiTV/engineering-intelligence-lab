# Token admission and recovery fix

Completed 2026-10-29 for investigation `ab468aea-2090-4cf3-afaa-e4cb874cf7ad` in case
`4327ab6d-ec54-433a-b747-e3292a67e562`. This is a bounded M4 runtime fix, not M5.

## Cause

The run stopped with 23,018 tokens charged against a 32,768 allowance. The remaining 9,750
tokens did not fit the old fixed reservation: 8,192 context + 2,048 output = 10,240.
The old middleware incremented the model-attempt counter before failing token admission,
so it recorded seven model calls although only six requests had started. Earlier requests
also tried a PDF filename through the virtual filesystem and a search limit of 10,
outside the case tool's supported range.

## Changes

- Model-call admission and token reservation are now one atomic transaction. Rejected
  admission does not increment calls or alter token usage. Failed/interrupted actual
  requests still retain their conservative reservation.
- The output cap fits the remaining allowance while retaining the full 8,192-token input
  envelope. Requests need context plus a usable output allowance (at least 256 tokens,
  or the user's smaller configured output limit).
- Near the call/tool/token allowance, the normal charged model request finishes from
  gathered evidence. LangChain's documented `ModelRequest.override` removes tools,
  preserves system instructions and adds a concise final-summary instruction. Optional
  Ollama thinking is disabled for that summary. A model that nevertheless requests tools
  is stopped before dispatch. Truncated output is still a failure.
- Successful capacity summaries are marked `result.capacity_limited` and labeled as
  findings gathered so far. They do not imply that missing checks were performed.
- Case search exposes query length and 1–5 result bounds in its actual tool schema.
  The case prompt explains that uploaded PDFs are not virtual filesystem paths.
- Both UI modes offer continuation for eligible token stops, including historical records.
  `POST /api/investigations/{id}/continue` accepts `additional_tokens` (default 0).
  It requeues the same thread/checkpoint and source snapshot with no question duplication,
  completed-tool replay or counter reset. Zero-increase continuation uses remaining capacity.
- If necessary, the user can explicitly request up to 65,536 additional tokens per action,
  within the absolute 131,072 total ceiling. The UI offers at most 32,768 per action.
  The server checks status, remaining call/tool/step/time limits and queue capacity in
  the same transaction. Concurrent submissions cannot queue or extend twice. Increases
  preserve `initial_limits` and record `token_allowance_extended`; zero-increase recovery
  records `investigation_continued`.

Default budgets, absolute caps, case isolation and read-only agent permissions are unchanged.
No agent tool can extend budgets. Pause/resume still cannot reset usage or limits.

## Validation

```powershell
$env:UV_CACHE_DIR = Join-Path (Get-Location) '.uv-cache'
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
Push-Location frontend
npm.cmd test
npm.cmd run build
npx.cmd prettier --check src package.json tsconfig.json vite.config.ts index.html
Pop-Location
git diff --check
```

- **118 backend tests passed** in 103.53 seconds, including original budget, timeout,
  cancellation, checkpoint, evidence and MCP tests.
- **18 frontend tests passed**, including same-investigation recovery, zero-increase
  continuation, bounded extra capacity and exhausted-limit refusal. Production build,
  Ruff, Prettier and whitespace checks passed.
- New backend checks cover atomic failed admission, exact Ollama request serialization,
  reduced output cap, original-adapter preservation, cumulative accounting, concurrent
  continuation, hard caps, API validation and source-snapshot isolation after later uploads.
- A real SQLite/LangGraph checkpoint stopped after an analytical tool is continued and
  completed without repeating its question or completed tool.

## Live recovery

The local server was restarted after confirming there were no queued/running jobs.
The original run was continued through the API with `{"additional_tokens": 0}`.
Its source IDs, thread ID and existing usage were retained. The resumed request reserved
the remaining 9,750 tokens and capped output at 1,558.

Result: **completed**, 29,197 charged tokens **within the unchanged 32,768 allowance**,
8 recorded model attempts (including the historical failed admission), 6 tool calls,
2 service attempts and 75.594 seconds cumulative active time. No error remained.
It returned the S03 1.61% to 14.11% finding, source references, a maintenance hypothesis and
uncertainties. It is explicitly capacity-limited; claims still require evidence review.

Browser automation could list the tabs but tab control failed with
`browser.user is unavailable` in this turn. Live recovery was verified through the local
API and persisted records; UI behavior was checked with frontend interaction tests.
Refresh the current page to load the new continuation controls and summary label.

## Compatibility

Inspected the installed LangChain `ModelRequest.override` and Ollama serialization before
using them. The runtime model is shallow-copied to adjust `num_predict`; temperature,
context and existing clients are retained. No dependency upgrade or custom agent loop
was introduced. Official reference:
[ModelRequest.override](https://reference.langchain.com/python/langchain/agents/middleware/types/ModelRequest/override).
