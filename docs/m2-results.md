# M2 — Durable, inspectable investigation execution

Completed on 2026-10-28. **67 offline tests pass**, and the real Ollama investigation passed
through the durable, budgeted CLI. A separate Uvicorn process recovered that CLI result and
replayed its persisted events over HTTP. M3 has not started.

## Architecture and API changes

The existing Deep Agents/LangGraph tool loop is retained. M2 adds application-level execution
management around it:

| File | Responsibility |
| --- | --- |
| `backend/src/eil/runs.py` | Validated limits, transactional SQLite job queue, run history, cumulative counters and event log |
| `backend/src/eil/service.py` | Single-owner dispatcher, one Windows-spawn worker, hard local pause/cancel/timeout, restart recovery |
| `backend/src/eil/execution.py` | Documented `SqliteSaver`, synchronous checkpoints, standard model/tool middleware for budgets and observations |
| `backend/src/eil/agent.py` | Inject a checkpointer/middleware; freeze stored model settings and cap generated tokens; retain the reviewed tools |
| `backend/src/eil/api.py` | HTTP 202 job creation, status/list/control endpoints and cursor-based SSE replay |
| `backend/src/eil/cli.py` | Durable bounded agent/resume commands; status/pause/cancel; Ctrl+C cancels the active CLI run |
| `tests/fakes.py`, `tests/test_runs.py` | Actual graph, SQLite and Windows process tests with a controlled ChatOllama subclass |
| `tests/test_api.py`, `tests/test_cli.py` | Async API contract, events, errors, controls and Windows JSON output |
| Settings, README, architecture, roadmap, AGENTS, `pyproject.toml`, `uv.lock` | State location, usage, scope, version 0.2.0 and reproducible dependencies |

Each new investigation receives a generated UUID, also used as its LangGraph thread ID.
Limits, question and Ollama model/URL are stored with the job. Request bodies cannot select
a model, thread, path or worker function. SQLite `runs.sqlite3` stores the queue, timestamps,
attempts, status, result, tool observations and controlled errors. `checkpoints.sqlite3`
stores the framework's state; `SqliteSaver.from_conn_string` is used directly.

A background supervisor claims FIFO jobs and starts one fixed Python worker at a time.
There can be at most twenty queued jobs. The model never receives a shell, Python executor,
process-launch tool, host filesystem mount or access to the databases. Ownership locks
prevent multiple services or overlapping real workers in the same state directory.

Graph execution uses `durability="sync"`. Pause terminates the worker, including blocked
synchronous model I/O. Resume loads the same thread and passes `None` to continue pending
nodes, rather than appending the question again. Shutdown interrupts active work; startup
marks stale running records `interrupted`. Queued jobs remain queued and run after startup.
The real worker also watches its parent and exits if that parent disappears.

This is a process interruption rather than an interactive `interrupt()` approval prompt.
An unfinished read-only node can repeat after recovery. A committed analytical tool was not
repeated in the pause/restart/resume acceptance test.

The former synchronous POST contract intentionally changes: `POST /api/investigations`
returns **202** with a run record. The answer is later available as `result.answer` from
`GET /api/investigations/{id}`. Model failure appears as a failed run with an actionable
`error`, without an API traceback. Other endpoints provide run listing, pause, resume, cancel
and `/events`. SSE carries persisted status/tool/checkpoint/usage events, not individual
generated tokens. `Last-Event-ID` or `?after=` resumes the event cursor without crossing runs.

## Resource controls

| Control | Default | Maximum accepted |
| --- | --- | --- |
| Graph steps | 35 | 100 |
| Model attempts | 8 | 20 |
| Tool calls | 16 | 40 |
| Total tokens | 32,768 | 131,072 |
| Generated tokens per request | 1,024 | 2,048 |
| Total active seconds across attempts | 120 | 600 |
| Context per request | 8,192 | Fixed for this fixture |

Counters are charged transactionally before model/tool work and persist across resume.
Before a model request, the service reserves the full context plus its output allowance;
afterwards it reconciles against reported usage. Missing usage or an interrupted request
keeps the reservation. A budget too small for that conservative reservation stops before
inference. Reservations may reject a request that would actually have fit; this is deliberate.
Output capped by the model with `done_reason: length` is a budget failure, not a successful
partial answer. Automatic summarization is disabled because its internal model calls would
otherwise bypass the budget hooks.

Graph steps are counted from updates, with checkpoint metadata reconciled on recovery;
model attempts are charged even when they fail. No budget resets on resume. Active time
includes worker startup and inference, but excludes queued and paused time. The parent polls
at roughly 50 ms and terminates the worker when its cumulative deadline is reached; OS
scheduling and process teardown can add delay. HTTP timeouts remain a separate backstop.

Paused, interrupted and failed runs can resume with their remaining budgets. Cancelled,
completed, timed-out and budget-exhausted runs cannot resume. A resumed failed run may
immediately exhaust a previously spent budget. Limits are immutable for an existing run.

## Compatibility and dependencies

Official references were checked alongside installed package source/signatures:

- [LangGraph checkpointers, thread scope and durability modes](https://docs.langchain.com/oss/python/langgraph/checkpointers)
- [LangGraph persistence and SQLite's local-development role](https://docs.langchain.com/oss/python/langgraph/persistence)
- [Deep Agents customization and harness profiles](https://docs.langchain.com/oss/python/deepagents/customization)
- [LangChain model/tool middleware hooks](https://docs.langchain.com/oss/python/langchain/middleware/custom)
- [ChatOllama adapter and tool calling](https://docs.langchain.com/oss/python/integrations/chat/ollama)

| Package/runtime | Tested version |
| --- | --- |
| Project / Python / uv | 0.2.0 / 3.12.15 / 0.13.5 |
| Deep Agents | 0.7.32 |
| LangGraph / SQLite checkpointer | 1.2.18 / 3.1.2 |
| LangChain / langchain-core | 1.4.7 / 1.7.1 |
| langchain-ollama / Ollama Python client | 1.1.0 / 0.6.3 |
| aiosqlite / sqlite-vec | 0.22.1 / 0.1.9 |
| FastAPI / httpx | 0.162.0 / 0.28.1 |
| pytest / Ruff | 9.2.0 / 0.17.3 |

The SQLite package brought aiosqlite and sqlite-vec as transitive dependencies; no vector
retrieval feature or optional document stack was implemented. The lock resolves 176 packages
including the pre-existing optional document extra; 75 distributions are installed for dev.

## Commands and acceptance evidence

Commands were run from the project root, with a writable uv cache in this managed host:

```powershell
$env:UV_CACHE_DIR = Join-Path (Get-Location) '.uv-cache'
uv sync --extra dev
uv lock --offline
uv sync --locked --extra dev --offline
uv run --locked pytest -q
uv run ruff check .
uv run ruff format --check .
uv lock --check --offline
uv pip check
uv run python -m eil.cli demo
```

The final offline suite passed **67 tests in 84.86 seconds** on Windows. Offline worker tests
forbid HTTP sends and exercise the actual compiled graph, real SQLite checkpointer and real
Windows-spawn processes. Key checks passed:

- Pause after a real analytical tool checkpoint, stop the service, reopen both databases,
  and resume the same thread without repeating that committed tool or duplicating the input.
- Distinct investigations keep separate messages, results and checkpoint `thread_id` values.
- Cancel and timeout terminate a blocked fake model call, independently of its response.
- A crashed worker's exit code is recorded; the run can resume through a new service.
- Model, tool, token and step budgets stop looping execution. Token reservations and model
  limits remain spent across interruptions and resume; truncated output is rejected.
- Unsupported station/path-like input reaches the existing constrained analytical error,
  with no dataset escape. M1 forged execution/write/delegation and host-file tests still pass.
- API requests receive 202; model failures are inspectable records; invalid input/configuration
  is controlled. SSE replays persisted events and honors its reconnect cursor.
- A second service cannot take the same state directory. Queue admission and queued controls
  persist. The API remains responsive while a model worker is blocked.

All Ruff, lockfile and installed dependency checks passed. The deterministic demo still ranks
S03 first. The initial 63-test pass was followed by output/resume edge tests and crash recovery.
One early assertion read elapsed metadata before the worker had been reaped; `wait()` now
waits for supervision to finish, and the final suite passes.

Optional real-model check, in an isolated ignored state directory:

```powershell
$env:EIL_STATE_DIR = Join-Path (Get-Location) 'reports\m2-live-state'
uv run --locked python -m eil.cli agent
```

It exited **0 in 40.40 seconds** end to end and recorded 39.156 seconds of supervised active
time: **5 graph steps, 2 model calls, 1 tool call, 7,880 tokens**. It used the installed
`qwen3.5:4b-q8_0`, identified **S03 +12.5021 percentage points**, cited valid S03 row IDs and
kept the lighting/exposure explanation as a hypothesis. The timing is one smoke observation,
not a benchmark; the offline suite was running concurrently.

A separate real Uvicorn server on `127.0.0.1:8766` reopened that state directory. HTTP checks
recovered the completed CLI result, replayed all **15 events** (including the successful
comparison), accepted a new job with 202, recorded its deliberately insufficient token budget
as `budget_exceeded` before inference, and returned 422 for a blank question. The server was
stopped afterwards. Raw evidence is ignored under `reports/m2-*`, including JSON, SSE and
the isolated state directory.

## Optional manual Windows smoke and remaining limits

Check `http://localhost:11434/api/tags` for the configured model first. Use the README's CLI
or HTTP commands. Run one API/CLI owner per state directory, using the same `EIL_STATE_DIR`
when inspecting or resuming. The CLI prints the generated ID before waiting. A second shell
can send `pause` or `cancel`; stop the original owner before CLI `resume`, or use API resume
while the API owns the directory. Ctrl+C on the CLI cancels. Unknown model/connection errors
are available in the saved run record, and CLI failed runs exit nonzero.

Remaining limits are material for shared deployment:

- Local development only: no authentication, per-user access control, distributed workers,
  encrypted state, storage retention quota, migration policy or production resource policy.
  UUID isolation is not an authorization scheme. Keep the server on loopback.
- Terminating the local worker does not guarantee instantaneous cancellation of computation
  already accepted by Ollama. The model server must honor context/output limits and report
  usage correctly for exact token accounting. Interrupted/unknown usage is conservatively
  charged, not measured.
- Event and checkpoint databases are separate transactions. A crash can leave a checkpoint
  ahead of its event record; completed checkpoints are authoritative, and unfinished work can
  repeat. Counters can overcharge unknown work. No exactly-once side-effect guarantee exists;
  tools remain read-only.
- Recovery across code, data or model-tag changes is unverified. Keep the fixture/model
  unchanged while resuming. SQLite files are trusted local state, not uploads to accept from
  an untrusted source. The explicit 8k context is measured only for the synthetic scenario.
- Real pause/restart recovery and cancellation were verified with controlled models;
  a real Ollama pause/restart/resume sequence was not separately benchmarked. The successful
  real-model run validates the durable execution path, not general factual reliability.
- The low-level M1 `run_agent()` helper remains for compatibility/offline tests. The bounded,
  durable application interface is `RunService`, used by the CLI and API.

No PDF, UI, MCP, Langfuse or production-system integration was added. Stop after M2.
