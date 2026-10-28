# Engineering Intelligence Lab (EIL)

A local-first **agentic engineering investigation workbench** developed with OpenAI Codex. **Independent of NodeWeft.**

## What is in this starter?

- Generated, versioned synthetic inspection dataset (`data/synthetic_inspection_v1.csv`)
- Deterministic and inspectable station comparison (`backend/src/eil/analytics.py`)
- FastAPI endpoints to inspect findings
- **Optional real Deep Agents + LangGraph tool-calling path** using an Ollama `ChatOllama` model
- `AGENTS.md`, milestone-specific Codex tasks, evaluation fixture, and tests

This is an initial vertical slice, **not yet a full PDF+CSV investigation app**. No PDF ingestion, React frontend, RAG, MCP, persistent checkpointing, or safe sandboxed execution is implemented yet. Live inference has not been benchmarked or verified in the generated environment.

## Quick start (Windows PowerShell)

```powershell
# Open this folder in VS Code, then:
uv sync --locked --extra dev
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
uv run python -m eil.cli demo
uv run uvicorn eil.api:app --reload
# Open http://127.0.0.1:8000/docs
```

Optional: **run a real agent** after starting Ollama and ensuring the configured model is installed:

```powershell
Copy-Item .env.example .env
uv run python -m eil.cli agent
```

Set `EIL_OLLAMA_MODEL` to an installed model that supports tool calling. Check the service and exact model tag before the manual smoke test:

```powershell
Invoke-RestMethod http://localhost:11434/api/tags
ollama list
# Only once the configured model is available:
uv run python -m eil.cli agent
```

The adapter validates model availability before constructing the graph, uses a 5-second connection timeout and 60-second HTTP inactivity timeout, and reports connection, missing-model, inference-timeout and rejected-request errors. The CLI exits with code 1 and an actionable message; the API returns 503. No model download or paid-provider fallback happens automatically.

A small local model may fail to call tools, emit invalid arguments, ignore evidence, or exhaust the graph's 35-step recursion limit. Model availability does not prove tool-calling support. The HTTP timeouts apply to individual requests/inactivity; they do not impose an overall investigation deadline. There is no total token budget, hard cancellation, queue, or production resource policy yet. Hardware fit, context size, latency, accuracy and real Ollama tool use still require a live benchmark.

The exposed tools are `compare_station_performance`, `inspect_station`, `ls`, `read_file`, `glob`, and `grep`. File tools use an explicit in-memory `StateBackend`, with no host files mounted. File-writing, deletion, shell execution, code interpreters, network-fetch tools and the default delegation tool are unavailable. Framework context offloading may still write to virtual state internally. `ground_truth.json` is not mounted or returned to the model. Dataset reads resolve paths and enforce the configured file within `data/`, including when an explicit path is supplied.

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

`POST /api/investigations` with `{"question":"Which station's false ejections changed most?"}` invokes the local Ollama-backed agent. Blank/oversized questions return 422. This experimental synchronous endpoint is for local development only; shared deployment still needs queues, persistent run state, total budgets and cancellation.

## Codex usage

The first-session review is recorded in [docs/review-results.md](docs/review-results.md). Stop at M1 until the user explicitly authorizes another milestone. See `docs/roadmap.md` and `AGENTS.md`.

## Data governance

Synthetic-only in M1. No connection to employer systems or use of internal GMP material. No autonomous modification of equipment. All analytical claims must report their evidence and uncertainty.
