# M5 evaluation and local observability

M5 is an opt-in command-line experiment. It uses only the versioned synthetic
fixtures, in a fresh state directory for each row. It never opens the workbench's
`.eil` cases, saves report drafts, enables external MCP, or changes the workbench's
single-agent Ollama default.

## Reproduce and enforce the gates

From the repository in PowerShell:

```powershell
$env:UV_CACHE_DIR = Join-Path (Get-Location) '.uv-cache'
uv sync --locked --extra dev
uv run pytest -q
uv run python -m eil.benchmark --provider offline --output reports/m5-offline-check
uv run python -m eil.benchmark --provider ollama --output reports/m5-ollama-check
```

Use a new output directory for each run; existing directories are never
overwritten. `--agent-mode single|delegated|both`, repeatable `--case`, and
`--repetitions 1..5` select a bounded subset. The default covers all three cases
and both modes once. Each row has 65 graph updates, 12 model calls, 20 tool calls,
65,536 cumulative tokens, 2,048 output tokens per request, an 8,192-token context
envelope, and a 180-second hard supervised timeout. `--timeout-seconds` can set
1..600 seconds. Failed and interrupted work retains its charged usage.

Exit 0 requires every requested slot to pass every check. Any failure, missing
provider configuration, or empty result fails the gate. Offline calibration
runs the real Deep Agents graph, tool schemas, evidence stores, checkpoints and
budget middleware with a scripted transport and forbidden network access. It
tests the harness; its token counts and latencies are not model measurements.
`pytest` includes intentionally incorrect metrics, unsupported causes, invented
citations, malicious output, hash tampering, case isolation, output truncation,
blocked child execution and cumulative-budget failures.

Each live mode uses the same fixed question, evidence bytes and budget envelope.
Calls are sequential across rows, with no warmup excluded. Wall time includes
worker startup. Ollama uses temperature 0 and the configured model tag; metadata
records server version, installed model digests, GPU/driver, dependency versions,
source hashes, Git revision/dirty status, fixture hashes, question and schema.
Multiple repetitions are supported but even temperature 0 does not guarantee
identical provider outputs. Compare distributions over adequate repetitions
before making a model-selection decision.

## What the scorer checks

The model must return a closed JSON claim contract. Gates check completion,
format, required and allowlisted tool selection with no tool errors, S03's
rates/delta, both S03 CSV periods, an observed relevant PDF page-2 citation,
correct calibrated causal status, synthetic/physical-causation limitations,
actual injection exposure and rejection, use of delegation in that mode, and
budget compliance. A Markdown JSON fence fails the strict format gate; its
claim metrics are still scored separately so it is not reported as an arithmetic
mistake. Ambiguous incidents must remain unresolved. The controlled fixture
supports only a cause within the simulator.

This is a deterministic check of a narrow claim contract. It does not validate
arbitrary prose, establish physical causation, detect every hallucination, or
measure statistical confidence. Unknown model costs are `null`, never zero.
Failed-quality runs have latency/token observations but cannot establish a
performance ranking. A faster incomplete investigation is not a successful
agent comparison.

## Artifacts and replay

Each row writes `run.json` (counters/limits/source snapshot), `evidence.json`
(answer, observed tools and resolved provenance), `trace.json`, and `score.json`.
The root contains JSON and Markdown scorecards with per-mode descriptive
summaries. Runtime SQLite checkpoints remain in that row's ignored `state/`.
The JSON files alone support deterministic rescoring, without an LLM or database:

```powershell
uv run python -m eil.benchmark --rescore reports/m5-ollama-check
```

Rescoring preserves observations and records the scorer source hash. It does not
change a model answer or retry a failed run. The committed M5 baseline artifacts
can be rescored in the same way. These local files are review evidence, not a
cryptographically signed attestation against an operator modifying the files.

## Local spans

New workbench investigations persist matched model/tool spans with agent name,
parent span, wall timestamp, measured duration, usage and failure type. Nested
analyst spans point to their parent `task` span. Kill/interruption leaves an
incomplete span rather than invented timing. Spans omit prompts, arguments,
answers, observations, credentials and reasoning. The existing local audit and
evidence exports retain the information needed for source review.

Read them through `GET /api/investigations/{id}/trace` or:

```powershell
uv run python -m eil.cli trace <investigation-id>
```

Old runs remain readable but cannot acquire retroactive timing. Missing or
partially traced usage is marked incomplete and cannot receive a cost estimate.
No new external tracing service is enabled. Self-hosted Langfuse is optional in
the roadmap and was not installed or connected; local JSON is the implemented
observability path. The benchmark worker disables ambient LangSmith tracing.

## Bounded subagent experiment

Delegated mode uses a real Deep Agents `CompiledSubAgent` called
`evidence-analyst`, with the same explicitly selected model. The coordinator
delegates once and synthesizes the answer. Only the analyst has the four
case-scoped evidence tools. Deep Agents requires virtual `read_file` scaffolding
on the coordinator; it has no uploaded files or host filesystem mount. There is
no general-purpose child, recursive child delegation, summarizer model, shell or
write tool. Both graphs use the same SQLite saver in separate checkpoint
namespaces, the same frozen case snapshot and the same transactional run budget.
Child graph updates, requests and tools count toward the parent's limits. The
same process supervisor kills all blocked graph work on timeout/cancellation.
Delegation is benchmark-only and is not accepted as an API/run-control input.

## Optional hosted comparison

```powershell
uv sync --locked --extra dev --extra hosted
# Configure OPENAI_API_KEY outside version control and select an explicit model.
uv run python -m eil.benchmark --provider openai --model <model-id> --output reports/m5-hosted-check
# Matrix uses EIL_OPENAI_MODEL and the configured EIL_OLLAMA_MODEL:
uv run python -m eil.benchmark --provider matrix --output reports/m5-matrix-check
```

Matrix runs make paid hosted calls when credentials and a hosted model are
configured. Hosted mode sends only these generated fixtures to the official
OpenAI endpoint through `ChatOpenAI`; it cannot send workbench uploads. SDK
retries are disabled and `store=False` is explicit. Per-request output limits,
usage accounting and the shared supervisor apply. The hosted input guard counts
messages and serialized tool schemas with a framing margin; actual usage is
checked against its reservation. Token estimates depend on the provider's model
tokenizer, which may require its normal first-use tokenizer cache download.
Output caps include reasoning tokens where the provider supports reasoning.

Supply both `--input-usd-per-million` and `--output-usd-per-million` from a dated,
verified rate to estimate hosted token cost. The scorecard records the supplied
rates; it does not assume prices, account discounts or access. Estimates exclude
hardware, energy and taxes. Without rates, costs remain unknown. The first M5
environment had neither a hosted key nor model configured, so real hosted slots
remain explicitly unrun. Mock HTTP tests validate transport compatibility but
cannot establish hosted quality, latency, account access or cost.

## Compatibility sources

- [Deep Agents compiled subagents](https://docs.langchain.com/oss/python/deepagents/subagents)
- [ChatOpenAI integration](https://docs.langchain.com/oss/python/integrations/chat/openai)
- [OpenAI completion/output limit and usage](https://developers.openai.com/api/reference/python/resources/chat/subresources/completions/methods/create)
- [Ollama model list and digests](https://docs.ollama.com/api/tags)

Installed compatibility checks used Deep Agents 0.7.32, LangGraph 1.2.18,
langchain-openai 1.7.3 and OpenAI SDK 3.41.0. The installed SDK's message counter
ignores tool schemas, so the adapter counts them separately. The installed
LangGraph child graph with disabled checkpoints raised an internal attribute
error under synchronous durability; sharing the SQLite saver with separate child
namespaces passes the actual delegation/checkpoint tests.
