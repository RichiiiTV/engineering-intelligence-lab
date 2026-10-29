# M4 results — local investigation workbench

Completed 2026-10-29 on branch `codex/m4-investigation-workbench`. M5 has not started.

## Delivered behavior

- React/TypeScript case navigation, case creation and explicit PDF/CSV uploads with data-category confirmation.
- Per-CSV baseline/incident chart, exact rate table, calculation provenance, source hashes and original-file downloads.
- Case PDF search and row/page citation inspection. Document/model/tool text is rendered as escaped text.
- Investigation creation with a fixed evidence snapshot and bounded time/output settings; pause, resume and cancel controls.
- Durable SSE timeline with replay, reconnect and per-run deduplication; tool detail pairs arguments and observations by call ID.
- Model report review, citation warnings, full JSON export, editable draft proposals and approved Markdown downloads.
- Immutable, persistent draft proposals. A separate content-bound approve/reject decision is required before saving a draft.
- Fixed, opt-in, read-only MCP mock implemented with the official SDK's actual protocol exchange over memory streams.
- Built UI served at `http://127.0.0.1:8000/`; Swagger remains at `/docs`. Vite development proxy remains optional.

The agent still has no host shell, arbitrary Python, unrestricted host filesystem, external MCP transport or write tool.
Existing case isolation, evidence snapshots and cumulative run budgets remain in place.

## Integration and approval boundaries

The MCP SDK is locked at 1.30.0 on its supported 1.x maintenance line (`mcp>=1.28,<2`).
`use_mock_mcp` defaults to false and is frozen in the run record. An enabled case run exposes
only `read_mock_station_context(S01..S04)`, backed by the fixed `eil-synthetic-maintenance-v1`
server. The adapter performs initialization, tool listing and a tool call, validates the
reviewed name/schema and typed observation, limits response size and enforces a three-second
deadline. Read-only annotations are hints, not authority. Changed catalogs fail closed before
dispatch. No case files are sent to the mock, and mock text cannot resolve as a case citation.

Draft proposal title/body are immutable and hashed. Approving the exact preview creates one
saved version in the same SQLite transaction as the decision and audit event. Repeated identical
decisions are idempotent. Rejection creates no draft; stale hashes and conflicting decisions
return 409. No direct save or approval tool is exposed to the agent. Explicit user case creation
and uploads remain ordinary UI operations.

This is a single-user local review flow, not authenticated proof of human identity or a
multi-user authorization system. Keep the API bound to loopback. Browser writes from unrelated
origins are rejected; the workbench has a self-only CSP. These controls do not replace authentication.

## Compatibility and checks

Validated environment: CPython 3.12.15, uv 0.13.5, Node 24.12.0, npm 11.6.2.
Frontend lock resolves React/React DOM 19.3.1, TypeScript 5.9.3, Vite 7.3.7,
Vitest 3.2.7 and Lucide React 0.468.0. Python integration keeps the existing tested Deep Agents,
LangGraph, Ollama and Docling versions; `uv.lock` includes the added MCP SDK and dependencies.

Commands run from the repository root unless noted:

```powershell
$env:UV_CACHE_DIR = Join-Path (Get-Location) '.uv-cache'
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv lock --check --offline
uv pip check
git diff --check

Push-Location frontend
npm.cmd test
npm.cmd run build
npx.cmd prettier --check src package.json tsconfig.json vite.config.ts index.html
npm.cmd audit --omit=dev --audit-level=high
Pop-Location

.\scripts\start-workbench.cmd
```

Backend: **111 tests passed in 113.54 seconds** on the final full-suite run.
Frontend: **6 tests passed**, TypeScript/production build passed, formatting passed.
Backend validation covers M1–M3 regressions plus M4 protocol/approval/UI-serving checks.
Ruff, lock consistency, installed-package compatibility and whitespace checks passed.
The runtime npm dependency audit reported **0 vulnerabilities** on 2026-10-29; this excludes dev dependencies.

M4 tests cover the real MCP session and Deep Agents tool binding, unknown tools/stations/extra
arguments, changed server catalogs and misleading read-only annotations, draft rejection,
stale hashes, concurrent approval retries, durable decisions, case filtering, unrelated browser
origins, fixed sample downloads, static assets/CSP scope, and missing-build behavior.
Frontend tests cover case creation/failure, evidence prerequisites, upload confirmation/size
limits, exact chart values, citation actions, SSE replay/isolation and escaped untrusted text.

The initial PowerShell launcher could not run because this machine disables PowerShell scripts.
It was replaced with a verified native CMD launcher; execution policy was not changed.
The CMD launcher builds successfully and starts the UI/API together on port 8000.

## Browser and live Ollama acceptance

Browser checks used the actual local FastAPI service and committed synthetic fixtures, not
mocked HTTP responses. Checked on 2026-10-28, with restart/persistence rechecked on 2026-10-29:

1. Created case `7509e40b-c1e9-4453-be83-ccd4e872f814` (S03 inspection drift).
2. Uploaded the 336-row inspection CSV and two-page synthetic maintenance PDF through the UI.
   The PDF used actual local Docling conversion. Overview showed S03 1.61% to 14.11%, +12.50 pp.
3. Searched `illumination exposure`; the first hit was PDF page 2. Opened the citation and verified
   its page, excerpt, citation ID and source SHA-256.
4. Started live Ollama run `791a06db-2c3f-4a32-9fba-245758cd88d0` with mock MCP enabled.
   Paused during worker startup, reloaded the browser, and resumed the same run with remaining
   budgets. The mock call returned the fictional S03 note through the SDK. The fuller request
   later stopped at the output limit: 4 model calls, 7 tool calls, 18,258 charged tokens,
   48.797 seconds cumulative active time across two attempts. The UI displayed the controlled
   `budget_exceeded` error. Durable checkpoint resume after completed tool work is separately
   covered by the existing M2/M3 offline worker tests.
5. Ran concise live investigation `5229bca5-7a80-4816-b644-3f1328fefd9e` with mock MCP and a
   2,048-token output cap. Completed using `qwen3.5:4b-q8_0`: **3 model calls, 4 tool calls,
   10,284 charged tokens, 9 steps, 26.172 seconds active time**. It reported S03 +12.5021 pp,
   labeled MCP context fictional, and stated causality remained unknown. One early CSV call
   used an incorrect source ID, received a constrained error, and was retried with the correct case-scoped source ID.
6. The model printed its CSV reference without the required brackets. The original report
   correctly warned that it contained no recognized answer citations. JSON preserved 8 resolved
   tool-supplied row references and the original model text; the citation rules were not loosened.
7. Requested and rejected a draft proposal; confirmed no draft was saved. Prepared an explicitly
   labeled automated acceptance draft with bracketed source references, closed the preview,
   reloaded, and reopened the durable pending proposal. Approved that exact preview.
8. Downloaded the full JSON report and approved Markdown draft through the browser. Verified
   their contents, run/proposal IDs and content digest. One approved draft exists; it survived
   server restart. Its content hash is
   `649bd1af5d80f51a1fb84899f2bbaca1088097e6dad157265756827a1196f4db`.
9. Checked a narrow mobile layout: no document-level horizontal overflow. Restored the browser
   viewport, inspected the desktop view, and found no browser warning/error logs at that check.

Local evidence: `.eil/` contains durable case/run/draft state; browser downloads are in the user's
Downloads folder. `reports/m4-workbench.jpg` is the ignored local preview. These runtime artifacts,
model assets, `node_modules` and built `dist` are not committed.

## Remaining limits and milestone stop

- A small local model can reach output/context budgets, repeat tools, or format citations incorrectly.
  The UI exposes these limits and warnings; successful completion is not guaranteed for every question.
- The approved draft is a review artifact. Its approval does not certify claims, causal inference,
  or statistical confidence; the original model report remains separate and unchanged.
- OCR is disabled. Native PDF parsing has the existing M3 bounds, not a hardened OS sandbox.
- Lists show the latest 50 cases/runs/proposals/drafts. No multi-user roles, production deployment,
  external MCP server, equipment write, Langfuse integration or M5 evaluation system was added.
- Backend and browser acceptance were exercised locally; no hosted deployment was requested.

Stop after M4 reporting. M5 requires another user request.

## Official references consulted

- [React: creating an app](https://react.dev/learn/creating-a-react-app)
- [Vite: getting started and Node compatibility](https://vite.dev/guide/)
- [MCP Python SDK 1.x maintenance guidance](https://github.com/modelcontextprotocol/python-sdk/tree/v1.x)
- [MCP SDK memory-transport testing](https://github.com/modelcontextprotocol/python-sdk/blob/v1.x/docs/testing.md)
- [MCP tool annotations are hints](https://py.sdk.modelcontextprotocol.io/api/mcp_types/)
