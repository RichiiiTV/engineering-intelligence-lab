# Engineering Intelligence Lab (EIL)

A local-first **agentic engineering investigation workbench** developed with OpenAI Codex. **Independent of NodeWeft.**

## What is included?

- Generated, versioned synthetic inspection dataset (`data/synthetic_inspection_v1.csv`)
- Deterministic and inspectable station comparison (`backend/src/eil/analytics.py`)
- FastAPI endpoints to inspect findings
- **Optional real Deep Agents + LangGraph tool-calling path** using an Ollama `ChatOllama` model
- Durable SQLite investigation queue, thread-scoped checkpoints, run history and SSE events
- Step, model/tool call, token and time budgets; pause, resume and cancellation
- Case-isolated PDF/CSV uploads, local Docling tables/pages, lexical search and citation exports
- React/TypeScript UI with case navigation, charts, live activity, tool details and report review
- Fixed read-only mock MCP integration, explicitly enabled per investigation
- Content-bound approval proposals before saving immutable report drafts
- Versioned M5 evaluation scorecards, content-minimal local traces and bounded delegation/provider experiments
- `AGENTS.md`, milestone-specific Codex tasks, evaluation fixture, and tests

M5 adds a separate synthetic benchmark workflow and local trace exports. See [M5 protocol](docs/m5-evaluation.md), [M5 results](docs/m5-results.md), [M4 results](docs/m4-results.md), [M3 evidence validation](docs/m3-results.md), and [M2 execution checks](docs/m2-results.md). The ordinary workbench retains its single-agent Ollama behavior.

## Quick start (Windows PowerShell)

```powershell
# Open this folder in VS Code, then:
uv sync --locked --extra dev
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
uv run python -m eil.cli demo
# Build the React interface (Node 22.12+ or 24 recommended):
Push-Location frontend
npm.cmd ci
npm.cmd test
npm.cmd run build
Pop-Location
uv run uvicorn eil.api:app --host 127.0.0.1 --timeout-graceful-shutdown 5
# Workbench: http://127.0.0.1:8000/    API docs: http://127.0.0.1:8000/docs
```

For the full UI with local PDF parsing, run `.\scripts\start-workbench.cmd` from this folder. It installs locked frontend dependencies if missing, builds the UI, and starts the loopback API with the `documents` extra. The CMD launcher works without changing PowerShell execution policy. Prefetch Docling models as described below before uploading PDFs. It does not start or download Ollama models.

For UI development, run the backend on port 8000, then `cd frontend; npm.cmd run dev`. Open `http://127.0.0.1:5173`; Vite proxies `/api` to port 8000. The built application is served directly by FastAPI at port 8000 with no second server needed. Rebuild and reload after frontend edits.

## Using the workbench

**SPS help** opens the [Siemens public knowledge search](http://127.0.0.1:8000/?page=siemens). Enter a public SIMATIC/S7/TIA Portal question and click **Search Siemens**. The app sends that question to the fixed Siemens MCP search tool and displays a labeled Siemens-generated summary and official source links. It keeps case files/history separate and provides no equipment connection. Search coverage varies; verify the exact CPU, firmware and TIA version against the linked documentation. See [project gaps and security review](docs/project-security-review.md).

The local API now checks loopback Host headers, rejects unrelated browser origins/cross-site API requests, and bounds JSON bodies before parsing. This remains a single-user local application; those controls do not add authentication or make network deployment suitable.

If a run reaches its token allowance, **Continue investigation** resumes its saved progress using the remaining capacity when possible. If needed, **Continue with extra capacity** explicitly adds a bounded token allowance; other limits and usage counters remain intact. The agent now summarizes gathered evidence before reaching capacity, and those results are labeled as findings so far. See [token recovery and validation](docs/token-budget-recovery.md). This refines the original fixed-reservation/immutable-limit behavior described in the historical M2 report.

The default page now follows the approved simpler design: add files, ask a question, then review the finding and source links. It creates the case automatically, keeps run controls in plain language, and downloads a readable HTML report that can be printed or saved as PDF from a browser. Use **Try the demo files** to start with the committed generated fixtures.

The original full interface remains available through **Advanced workspace** (`/?view=advanced`). It retains model/run settings, tool activity, complete source provenance, JSON exports and explicit draft approval. The mode switch changes presentation; it is not an admin authentication boundary. Simple investigations keep the existing server budgets, use the longer supported 2,048-token output allowance, and leave mock MCP off by default.

The default results use only the run's saved evidence snapshot. CSV findings and the comparison chart are computed by the deterministic API, one file at a time. Model notes remain separate and source-reference warnings remain visible. Report download does not save a draft in the application; saving a draft still requires approval in the advanced workspace.

The following detailed workflow remains available in the advanced workspace:

1. Create a case. Upload generated or explicitly licensed public inspection CSVs and text PDFs; confirm the data category. The guide and upload dialog link the committed synthetic samples.
2. Review the Overview chart and calculation provenance, search the PDFs, and open row/page citations. Each CSV is compared separately. Overview includes current case sources; runs freeze their own source snapshot.
3. Start an investigation with a question and active time limit. Optionally allow the read-only **synthetic mock MCP** context. Activity replays persisted SSE events and exposes tool arguments/observations. Pause/resume/cancel controls preserve cumulative budgets.
4. Review the model answer, citation checks and limitations in Report. Export the full JSON record. For a saved draft, edit the text, request review, then **Approve & save draft** or reject the proposal. Pending proposals survive reload; approved versions download as Markdown. Draft approval records a decision, not claim validity.

The MCP mock implements the MCP SDK's actual initialization, tool listing and tool call exchange over in-memory streams. It has one reviewed synthetic station-context tool, no configurable commands/URLs and no writes. It is disabled by default; the option is frozen in each run. It is not an external plant connection or a case citation source.

This remains a single-user loopback demo. Approval is an explicit local UI/API decision bound to immutable proposal content, **not authenticated proof of a person's identity**. Do not expose the API to a network. Browser mutations from unrelated origins are rejected; this does not replace authentication. Case creation and uploads are explicit user actions; no agent tool can create cases, upload files or save drafts.

Optional: **run a real agent** after starting Ollama and ensuring the configured model is installed:

```powershell
# Only when .env does not already exist:
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
uv run python -m eil.cli agent
```

Set `EIL_OLLAMA_MODEL` to an installed model that supports tool calling. Check the service and exact model tag before the manual smoke test:

```powershell
Invoke-RestMethod http://localhost:11434/api/tags
ollama list
# Only once the configured model is available:
uv run python -m eil.cli agent
```

The adapter validates model availability, requests an 8,192-token context, and uses 5-second connection and 60-second HTTP inactivity timeouts. The run supervisor separately enforces total active time. CLI output is a run record with its answer under `result.answer`; it includes the run ID, status, counters and errors. Unicode is JSON-escaped for Windows redirected output. No model download or paid-provider fallback happens automatically.

A small local model may ignore evidence or return invalid arguments. The server's original 4,096-token context produced an incorrect answer; the explicit 8,192-token setting passed the fixture. Longer tasks still need context/memory measurements. Development defaults are 35 steps, 8 model attempts, 16 tool calls, 32,768 total tokens, 1,024 output tokens per call and 120 seconds of active time. Limits persist across resume. Token admission conservatively reserves a full context plus output allowance before each request; unknown or interrupted usage retains that charge. Automatic summarization is disabled so it cannot make unbudgeted model calls. See [execution controls and limitations](docs/m2-results.md).

Only one CLI/API service may own a state directory. Stop the API before running `agent` or `resume` through the CLI, or use the API to submit work. The default state folder is ignored `.eil/`; `EIL_STATE_DIR` can select another trusted local folder. Use one Uvicorn worker. Reloading or stopping the service interrupts active work; it requires an explicit resume. Queued work remains durable.

The CLI prints the investigation ID to stderr at submission. From a second PowerShell session using the same state directory:

```powershell
uv run python -m eil.cli status <run-id>
uv run python -m eil.cli pause <run-id>
uv run python -m eil.cli cancel <run-id>
# Once the first service has stopped, resume the same durable thread:
uv run python -m eil.cli resume <run-id>
```

Ctrl+C cancels a CLI investigation. `agent --timeout-seconds 60` selects a shorter total time budget. Paused, interrupted and failed jobs can resume with their remaining budgets; completed, cancelled and exhausted jobs cannot resume. A failed job that exhausts its remaining budget on retry must be replaced with a new investigation.

Legacy fixture investigations expose `compare_station_performance`, `inspect_station` and four virtual read tools. Case investigations replace the fixture tools with `list_case_sources`, `search_case_documents`, `compare_case_stations` and `read_case_citation`, scoped to a frozen case/source list. File tools use an explicit virtual `StateBackend` persisted in the checkpoint, with no host files mounted. File-writing, deletion, shell execution, code interpreters, network-fetch tools and default delegation are unavailable. Framework result offloading can write virtual state internally. `ground_truth.json` is not mounted or returned to the model. The application's fixed worker processes are not agent-accessible execution tools.

The committed `uv.lock` and `.python-version` record the reviewed environment. Offline tests use a scripted ChatOllama subclass with real tool binding and the actual Deep Agents graph; HTTP requests are forbidden in those tests. They verify framework wiring and permissions, not the quality or behavior of a real model. See [the completed M1 review](docs/review-results.md) for versions, commands and remaining limits.

## Example investigation

The dataset contains **synthetic** station observations, with a known intervention at `2026-10-10T00:00:00`: one station gets a large false-ejection increase and a correlated change in lighting/exposure. The answer to the injected fault is kept in `data/ground_truth.json` **for evaluation only**, not to be shared with the agent.

The deterministic baseline report tells you *which station* changed and how strongly. An LLM must use tools to connect observations and form hypotheses without claiming it has established causality.

## M3 PDF and CSV cases

Ordinary offline tests and CSV uploads need only `uv sync --locked --extra dev`. Real PDF
conversion additionally needs Docling and its explicitly prefetched layout/table assets:

```powershell
uv sync --locked --extra dev --extra documents
uv run --extra documents docling-tools models download layout tableformer --output-dir .eil/docling-models --quiet
uv run --extra documents python scripts/verify_m3_golden.py
uv run --extra documents uvicorn eil.api:app --host 127.0.0.1 --timeout-graceful-shutdown 5
```

Conversion uses local CPU models, with OCR, remote services and external plugins disabled.
No model download happens during ingestion. Missing dependencies/assets return actionable
503 errors. Use `EIL_DOCLING_ARTIFACTS` for another trusted local model folder.

Create a case and upload generated or explicitly licensed public demo evidence:

```powershell
$case = Invoke-RestMethod http://127.0.0.1:8000/api/cases -Method Post -ContentType application/json -Body '{"title":"Synthetic inspection evidence"}'
curl.exe -sS -F "data_policy=synthetic" -F "file=@output/pdf/synthetic-maintenance-note.pdf;type=application/pdf" "http://127.0.0.1:8000/api/cases/$($case.id)/sources"
curl.exe -sS -F "data_policy=synthetic" -F "file=@data/synthetic_inspection_v1.csv;type=text/csv" "http://127.0.0.1:8000/api/cases/$($case.id)/sources"
$body = @{case_id=$case.id; question="Which station changed most? Use CSV metrics and the PDF, cite evidence and distinguish hypotheses."} | ConvertTo-Json
$job = Invoke-RestMethod http://127.0.0.1:8000/api/investigations -Method Post -ContentType application/json -Body $body
Invoke-RestMethod "http://127.0.0.1:8000/api/investigations/$($job.id)"
Invoke-RestMethod "http://127.0.0.1:8000/api/investigations/$($job.id)/export"
```

The required upload `data_policy` is `synthetic` or `licensed-public`; it is the uploader's
declaration, not automated license verification. After stopping the API, the CLI can use the
same stored case: `uv run python -m eil.cli agent --case-id <case-id>`. Investigations without
a case ID retain the original synthetic fixture behavior.

Files are immutable BLOBs in `<state>/data/evidence.sqlite3`; uploaded names are metadata,
never host paths. A run freezes source IDs at submission. Later uploads affect new runs
only. CSV sources are compared separately, never silently merged. CSV headers must exactly
match the nine inspection columns; station/period enums, ISO timestamps, unique row IDs,
integer measurements and rejection counts are validated.

Limits are 10 MiB/20 pages per PDF, 2 MiB/20,000 rows per CSV, and ten sources/30 MiB per case.
Request bodies are bounded before multipart spooling, including chunked requests. One PDF
conversion runs at a time, with a 120-second process deadline. These are development limits,
not a native-parser sandbox or an OS memory quota.

Retrieval uses SQLite FTS5/BM25 over the frozen source snapshot. Query words are literal;
neither raw SQL nor FTS operators are accepted. Chunks preserve item references, page ranges,
bounding boxes and offsets. Multi-page items explicitly retain all page numbers. Citations
resolve to source hashes and PDF excerpts or CSV row IDs/physical line numbers. `rN` in a CSV
citation is a zero-based internal row ordinal; resolve it to see the original row ID/line.

The JSON export includes the answer, immutable source inventory, observations, requested and
executed query definitions, resolved citations and uncertainty. It flags malformed, unknown,
unobserved or missing answer references and supports explicit grouped citation shorthand.
Resolution validates location, not claim entailment. Lexical scores are not confidence
probabilities; statistical/causal confidence is not estimated. Example CSV rows are samples,
while each aggregate identifies its full source hash, grouping and number of rows used.

The synthetic golden fixture is on page 2 of `output/pdf/synthetic-maintenance-note.pdf`,
with its captured real Docling output under `tests/fixtures/`. The PDF is visually verified.
The ordinary suite consumes that capture without downloading models; the optional verifier
runs the real Docling pipeline and checks page 2 plus S03's +12.5021-point CSV increase.

## Endpoints

- `GET /api/health`
- `GET /api/datasets`
- `GET /api/metrics/summary`
- `GET /api/metrics/stations/S03`
- `GET /api/investigations/demo-report`
- `POST /api/investigations` — create a job, HTTP 202
- `GET /api/investigations` — recent run records
- `GET /api/investigations/{id}` — status, result, counters and actionable errors
- `GET /api/investigations/{id}/events` — persisted SSE stream; reconnect with `Last-Event-ID`
- `POST /api/investigations/{id}/pause`, `/resume`, `/cancel`
- `POST /api/cases`, `GET /api/cases`, `GET /api/cases/{id}`
- `POST /api/cases/{id}/sources` — multipart PDF/CSV upload and explicit data policy
- `GET /api/cases/{id}/search?q=...` — bounded lexical PDF retrieval
- `GET /api/cases/{id}/sources/{source}/comparison` — deterministic CSV finding
- `GET /api/cases/{id}/sources/{source}/file` — original bytes as an attachment
- `GET /api/cases/{id}/citations/{citation}` — resolve one scoped reference
- `GET /api/investigations/{id}/export` — case-backed evidence report JSON

`POST /api/investigations` accepts `{"question":"Which station's false ejections changed most?","limits":{"timeout_seconds":120}}`. It now returns HTTP **202** and a run record instead of synchronously returning an answer. Poll the run or consume its events. Model failure is recorded as `status: "failed"` with an actionable `error`; job creation itself can succeed while Ollama is down. Invalid questions/options return 422, unknown jobs 404, conflicting actions 409, full queue 429 and invalid server model-URL configuration 503.

```powershell
$body = @{question="Which station changed most? Cite tool evidence."} | ConvertTo-Json
$job = Invoke-RestMethod http://127.0.0.1:8000/api/investigations -Method Post -ContentType application/json -Body $body
Invoke-RestMethod "http://127.0.0.1:8000/api/investigations/$($job.id)"
curl.exe -N "http://127.0.0.1:8000/api/investigations/$($job.id)/events"
```

This API is for loopback development. It has no authentication, per-user authorization, retention quota or shared-deployment policy. Cancelling terminates the local worker; a remote Ollama server may continue computing until it notices the disconnected client. Checkpoint recovery can repeat an unfinished read-only node.

## Codex usage

M1 review and live verification are recorded in `docs/review-results.md` and `docs/ollama-verification.md`. See [M2 results](docs/m2-results.md) and [M3 results](docs/m3-results.md). Stop after M3; later milestones require another user request. See `docs/roadmap.md` and `AGENTS.md`.

## Data governance

Use generated or explicitly licensed public demo data only. No connection to employer systems or use of internal GMP material. No autonomous modification of equipment. All analytical claims must report their evidence and uncertainty.
