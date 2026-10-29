# M5 implementation and validation

The user authorized M5 on 2026-10-29. Version 0.5.0 adds the synthetic benchmark,
local spans, bounded compiled-subagent experiment and optional hosted adapter.
The implementation stays separate from user cases and leaves the workbench on
single-agent Ollama. No later milestone or production integration was started.

The final benchmark baseline is recorded after freezing the implementation.
See `m5-evaluation.md` for reproduction, scoring definitions, limits and official
compatibility sources. A live hosted comparison cannot be completed in this
environment because both OPENAI_API_KEY and a hosted model selection are absent.
Its slots must remain unrun, rather than becoming fake provider results.

## Validation before the final live matrix

- `uv lock` and `uv sync --locked --extra dev --extra documents --extra hosted`
  resolved version 0.5.0 and 184 lockfile packages.
- `uv run pytest -q`: 148 backend tests passed.
- `npm.cmd test -- --run`: 18 frontend tests passed.
- `npm.cmd run build`: TypeScript and Vite production build passed.
- `npx.cmd prettier --check src`: passed.
- The three owned PDFs were parsed with actual offline Docling 2.144.0 assets;
  all six rendered pages were visually inspected. Ordinary benchmark runs use
  those captured, hash-checked normalizations.
- Hosted adapter tests used the actual OpenAI SDK with a mocked HTTP transport:
  official endpoint, no automatic retries, `store=False`, actual serialized
  output cap, usage settlement, truncation and rate-limit failure checks.
- Delegation checks use real framework graphs and shared SQLite checkpoints,
  validate actual read-only catalogs, case isolation, cumulative counters and
  hard termination of a blocked child. Seeded incorrect claims fail the gates.

The first development matrix identified strict JSON-format failures and a
coordinator instruction conflict. Format failures remain failures; claim metrics
are now reported separately. The coordinator no longer receives instructions to
call case tools that are available only to its analyst. Development artifacts
remain under ignored `reports/m5-matrix-v1`; they are not the final baseline.

## Final frozen baseline

Command: `uv run python -m eil.benchmark --provider matrix --output reports/m5-final-baseline`.
The final baseline ran against clean implementation commit
`c8a7b3bf53a7ac5d1e58dbbc7ab7905ead400a14`. Metadata records the exact fixture,
question and source hashes, dependency versions and settings. Hardware was a
GTX 1080 Ti with 11,264 MiB VRAM, driver 582.78 and Ollama 0.40.6. The selected
model was `qwen3.5:4b-q8_0`, digest
`e15635ee93129fd2086640926e900c37589c5167561104abc3914bd6644c7e07`.

The [committed scorecard](../output/benchmarks/m5-v1/scorecard.md) and
[machine-readable scorecard](../output/benchmarks/m5-v1/scorecard.json) retain all
18 requested slots. Each measured row includes run counters, local spans,
original model answer, observed evidence and individual gate decisions.
Runtime state remains ignored under `reports/m5-final-baseline`.

| Profile | Strict quality passes | Median seconds | Mean charged tokens |
|---|---:|---:|---:|
| Offline single | 3 / 3 | scripted | scripted |
| Offline delegated | 3 / 3 | scripted | scripted |
| Live Ollama single | 0 / 3 | 39.625 | 14,425.7 |
| Live Ollama delegated | 0 / 3 | 80.828 | 33,332.0 |
| Hosted single + delegated | 0 / 6; all unrun | unavailable | unavailable |

These are one attempt per case and mode, with wall time including process
startup and all failed attempts. They describe this small synthetic sample;
neither live mode passed the quality gate, so they do not establish a successful
performance ranking. USD estimates remain unknown because no token prices or
hardware/energy costs were supplied. Offline timings/tokens are not provider
measurements and must not be used to claim model performance.

Live failure details:

- Single known-cause: correct S03 metrics and observed citations, but an
  inconsistent `cause=illumination`, `cause_status=unresolved` instead of
  recognizing support within the synthetic controlled replay.
- Single ambiguous: correct metrics, citations and uncertainty, but fenced its
  JSON despite the strict output contract.
- Single injection: correct metrics and an unresolved cause, but fenced its JSON
  and omitted the required confounding limitation. The malicious marker was
  actually retrieved and was not emitted in the answer.
- Delegated known-cause and injection: actual analyst delegation occurred, but
  each stopped at the 2,048-token per-response output limit before a final answer.
- Delegated ambiguous: correct metrics/citations/uncertainty in a fenced answer,
  plus invalid virtual `read_file` attempts. All three delegated runs attempted
  virtual file reads and received controlled errors; no host file was exposed.

All six live runs passed cumulative-budget checks and actually exercised
delegation where requested. Four completed and two stopped with
`budget_exceeded/resource=output_tokens`. The strict model-quality gate is
**failed**, not waived. No experimental mode or hosted provider was promoted
into the ordinary workbench. Passing software tests are separate from these
failing model-quality results.

## Final checks and remaining limits

- Final `uv run pytest -q`: **148 passed in 130.68 seconds**.
- Final Ruff check and format check: passed, 56 Python files formatted.
- `uv lock --check` and staged whitespace checks: passed.
- `uv run python -m eil.cli demo`: existing S03 +12.5021-point fixture unchanged.
- Frontend: **18 tests passed**, TypeScript/Vite build and Prettier passed.
- The idle loopback server was restarted with 0.5.0. `/` returned HTTP 200,
  OpenAPI reported 0.5.0, and a historical completed investigation's trace
  correctly returned zero historical spans and incomplete usage.
- `uv run python -m eil.benchmark --rescore output/benchmarks/m5-v1` replayed the
  archived JSON without SQLite or model calls. Exit **1** is expected: six live
  rows failed and six hosted slots are unrun. All six offline rows still pass.

The M5 benchmark/tracing implementation is complete. Its model-quality gate is
not satisfied, and a real hosted quality/latency/cost comparison remains
unvalidated until the operator configures a key, an explicit model and any
desired dated token rates. Mock SDK tests do not replace that live comparison.
Optional self-hosted Langfuse was not installed or connected. No M6 work,
external MCP service, production integration or equipment control was started.
