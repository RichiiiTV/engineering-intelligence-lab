# Engineering Intelligence Lab (EIL)

A local-first **agentic engineering investigation workbench** developed with OpenAI Codex. **Independent of NodeWeft.**

## What is included?

- Generated, versioned synthetic inspection dataset (`data/synthetic_inspection_v1.csv`)
- Deterministic and inspectable station comparison (`backend/src/eil/analytics.py`)
- FastAPI endpoints to inspect findings
- **Optional real Deep Agents + LangGraph tool-calling path** using an Ollama `ChatOllama` model
- Durable SQLite investigation queue, thread-scoped checkpoints, run history and SSE events
- Step, model/tool call, token and time budgets; pause, resume and cancellation
- `AGENTS.md`, milestone-specific Codex tasks, evaluation fixture, and tests

M2 adds durable local execution. PDF ingestion, React, RAG, MCP and sandboxed code execution remain future work. The real Ollama agent has passed the synthetic investigation smoke through the bounded service. See [the M2 report](docs/m2-results.md) and [M1 Ollama verification](docs/ollama-verification.md).

## Quick start (Windows PowerShell)

```powershell
# Open this folder in VS Code, then:
uv sync --locked --extra dev
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
uv run python -m eil.cli demo
uv run uvicorn eil.api:app --host 127.0.0.1 --timeout-graceful-shutdown 5
# Open http://127.0.0.1:8000/docs
```

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

The exposed tools are `compare_station_performance`, `inspect_station`, `ls`, `read_file`, `glob`, and `grep`. File tools use an explicit virtual `StateBackend`, now persisted inside the thread's checkpoint, with no host files mounted. File-writing, deletion, shell execution, code interpreters, network-fetch tools and default delegation are unavailable. Framework result offloading can write virtual state internally. `ground_truth.json` is not mounted or returned to the model. Dataset paths remain allowlisted. The application starts its own fixed worker process; the agent has no process-launch tool or access to the run databases.

The committed `uv.lock` and `.python-version` record the reviewed environment. Offline tests use a scripted ChatOllama subclass with real tool binding and the actual Deep Agents graph; HTTP requests are forbidden in those tests. They verify framework wiring and permissions, not the quality or behavior of a real model. See [the completed M1 review](docs/review-results.md) for versions, commands and remaining limits.

## Example investigation

The dataset contains **synthetic** station observations, with a known intervention at `2026-10-10T00:00:00`: one station gets a large false-ejection increase and a correlated change in lighting/exposure. The answer to the injected fault is kept in `data/ground_truth.json` **for evaluation only**, not to be shared with the agent.

The deterministic baseline report tells you *which station* changed and how strongly. An LLM must use tools to connect observations and form hypotheses without claiming it has established causality.

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

`POST /api/investigations` accepts `{"question":"Which station's false ejections changed most?","limits":{"timeout_seconds":120}}`. It now returns HTTP **202** and a run record instead of synchronously returning an answer. Poll the run or consume its events. Model failure is recorded as `status: "failed"` with an actionable `error`; job creation itself can succeed while Ollama is down. Invalid questions/options return 422, unknown jobs 404, conflicting actions 409, full queue 429 and invalid server model-URL configuration 503.

```powershell
$body = @{question="Which station changed most? Cite tool evidence."} | ConvertTo-Json
$job = Invoke-RestMethod http://127.0.0.1:8000/api/investigations -Method Post -ContentType application/json -Body $body
Invoke-RestMethod "http://127.0.0.1:8000/api/investigations/$($job.id)"
curl.exe -N "http://127.0.0.1:8000/api/investigations/$($job.id)/events"
```

This API is for loopback development. It has no authentication, per-user authorization, retention quota or shared-deployment policy. Cancelling terminates the local worker; a remote Ollama server may continue computing until it notices the disconnected client. Checkpoint recovery can repeat an unfinished read-only node.

## Codex usage

M1 review and live verification are recorded in `docs/review-results.md` and `docs/ollama-verification.md`. M2 results are in [docs/m2-results.md](docs/m2-results.md). Stop after M2; later milestones require another user request. See `docs/roadmap.md` and `AGENTS.md`.

## Data governance

Synthetic-only in M1. No connection to employer systems or use of internal GMP material. No autonomous modification of equipment. All analytical claims must report their evidence and uncertainty.
