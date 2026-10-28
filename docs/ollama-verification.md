# Live Ollama verification — 2026-10-28

The local Ollama integration passed the M1 smoke test after fixing redirected Windows
Unicode output and explicitly selecting an 8,192-token context. The real CLI answered the
default question correctly, using analytical tool evidence. No later milestone was started.

## Observed environment

The service became available at `http://localhost:11434` after the earlier connection-refused
checks. `/api/version` returned **0.40.6**. `/api/tags` and `/api/show` confirmed that the
configured **qwen3.5:4b-q8_0** model was installed and advertised completion, vision, tools
and thinking capabilities. It is a 4.2B Q8_0 model, approximately 5.16 GB on disk.

The Windows host reported an NVIDIA GeForce GTX 1080 Ti with 11,264 MiB and driver 582.78.
After the successful test, `/api/ps` reported `context_length: 8192`, with model size and
`size_vram` both **5,198,713,978 bytes** (about 4.84 GiB). This establishes the memory fit
observed for this run, not a hardware benchmark for other models or longer tasks.

The Ollama CLI was still absent from the session's PATH; API access was sufficient for
ChatOllama. No Ollama installation, upgrade, model download, provider switch or service
restart was needed or performed.

## Failures found and fixes

1. The initial exact `uv run --locked python -m eil.cli agent` invocation reached inference
   but exited 1 after 46.35 seconds when printing the answer. Python's redirected Windows
   stdout used cp1252, and the model returned characters outside that encoding. CLI output
   now uses JSON's default Unicode escaping. A regression test writes a Unicode model
   answer through an actual cp1252 `TextIOWrapper` and verifies the JSON round trip.
2. A traced rerun then exited 0 in 29.01 seconds but failed content acceptance. Its successful
   `compare_station_performance` observation correctly ranked S03 first, yet the final model
   answer omitted S03 and named S02 as the largest change. It also misstated S01's delta and
   provided no row citations. The server had loaded a **4,096-token context**. After the
   comparison, reported input was only 2,050 tokens despite a 5,373-character tool result.
3. ChatOllama now explicitly sets `num_ctx=8192`. The next traced run processed **5,356 input
   tokens** after the tool result, returned the correct ranking and citations, and passed
   acceptance. This supports context truncation as the cause of the earlier lost evidence;
   there was no server truncation log captured. The independent plain CLI rerun returned the
   same correct answer. Offline adapter tests verify the context passed to ChatOllama.

The larger context uses the documented ChatOllama `num_ctx` parameter. Ollama documents a
4k default on GPUs below 24 GiB and the memory tradeoff of increasing context:
[Ollama context length](https://docs.ollama.com/context-length). The configured model's
official listing advertises tool support: [qwen3.5:4b-q8_0](https://ollama.com/library/qwen3.5:4b-q8_0).
The selected 8k value is sufficient for this fixture, rather than a recommendation for
arbitrary investigations.

## Passing checks

| Check | Observed result |
| --- | --- |
| Local version, model listing and model details APIs | HTTP 200; configured model available |
| Real compiled Deep Agents graph + actual ChatOllama inference, with local callback trace | Exit 0 in 28.33 seconds |
| Exact `uv run --locked python -m eil.cli agent`, without diagnostic instrumentation | Exit 0 in 25.34 seconds; same answer as traced run |
| Actual tool execution | `compare_station_performance`, status `success`; observation exactly equals deterministic `compare_stations()` |
| Finding | S03, from rate 0.016123 to 0.141144, **+12.5021 percentage points** |
| Row citations | `ROW-00003`, `ROW-00167`, `ROW-00171`, `ROW-00335`; all are real S03 evidence IDs in the returned observation |
| Evidence versus inference | Lighting/exposure changes described as a hypothesis; answer states correlation does not imply causation and leaves the cause unconfirmed |
| Tool boundary in the live trace | Only the allowed analytical comparison tool was called |
| `uv run --locked pytest -q` | **44 passed**, including Windows output regression |
| `uv run ruff check .`, `uv run ruff format --check .` | Passed |
| `uv lock --check --offline`, `uv pip check` | Lockfile current; installed dependencies compatible |

The cited boundary IDs are valid, but the model's "through" wording is shorthand: observations
are interleaved across stations. The full tool observation preserves the exact source-row
list. Broad factual reliability, adversarial robustness, long investigations, cold-start
performance, cancellation and production budgets remain outside this smoke test.

The local trace used a callback around the actual graph and executed the CLI entry point;
it supplied no fake model responses and sent no tracing data to an external service. A
separate local acceptance check compared its tool output against the deterministic function,
verified the cited IDs, and checked the tool names. Normal offline tests continue to exercise
the permission failure cases independently of the model.

Raw evidence is kept in the ignored `reports/` directory:

- `ollama-live-environment.json` and `ollama-live-loaded-model.json`
- `ollama-default-context-cli.json`, `ollama-default-context-trace.jsonl` and status JSON
- `ollama-traced-cli.json`, its status JSON, and `ollama-live-trace.jsonl`
- `ollama-live-cli.json`, `ollama-live-cli-status.json`, `ollama-live-cli.stderr.log`
- `ollama-live-acceptance.json` and the one-off diagnostic `trace_ollama_smoke.py`

M1 live verification is complete for this synthetic scenario. Stop here; do not begin M2.
