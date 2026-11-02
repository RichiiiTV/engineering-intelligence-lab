# Budget-stop recovery

Implemented for the explicit 2026-11-02 goal. An investigation that reaches a
budget or time limit now leaves a useful evidence preview instead of an empty
answer. It remains `budget_exceeded` or `timed_out`, with its original error and
usage. A preview is **partial evidence review**, not a completed investigation,
successful model answer, verified diagnosis or new quality-gate pass.

## What the user sees

- A German or English notice, using the language frozen for that investigation.
- Up to three literal excerpts from text already retrieved, with exact source
  citations. Source text retains its original language. Embedded markup and fake
  citation instructions are rendered inert.
- An honest empty-preview message when no suitable text was retrieved. Tool
  calculations, visual transcriptions and public Siemens reference metadata
  remain in their existing provenance views; they are not promoted to literal
  document evidence by this preview.
- A **Finish from existing evidence** action after an output-token stop, when
  there is enough of the existing run budget to try a concise answer. It makes no
  additional searches or vision calls and cannot increase any limit.
- The existing explicit token-continuation action, now available in normal chat
  as well as the file-results view. If total-token capacity must increase, the
  button says so. There is no automatic continuation.

The server still decides admission. Exhausted model-call, tool-call, step or time
limits, actual provider usage overages, deleted cases and competing conversation
turns cannot be bypassed. Duplicate continuation requests queue only once. A
second output truncation leaves another incomplete preview and stops again.

## Implementation boundaries

`RunStore.finish` builds the preview transactionally from its saved source reads
and at most 40 saved successful case-tool observations. It never asks a model,
retrieves more sources, reads source files or contacts Siemens. The preview
filters citations against frozen library/machine/catalog, case and attachment
scopes; it does not use truncated model prose or delegated claims. Provider
overages still charge actual usage atomically, while a pending cancellation wins
the final state transition.

An explicit output-limit continuation reuses the same durable LangGraph thread
and checkpoint. Its model request has tools removed, reasoning disabled and the
existing output cap. A server-side tool guard also rejects unexpected tool work.
The normal adapter reservation/settlement code meters every new request. No
question, source selection, language, elapsed time or usage counter is reset.
Total-token extensions remain explicit, bounded to 65,536 per request and 131,072
per investigation; finish-only continuations cannot extend them.

This uses the existing framework middleware and checkpointer, consistent with
the official [LangGraph persistence documentation](https://docs.langchain.com/oss/python/langgraph/persistence).
There is no new general tool-calling engine. Partial stopped turns are excluded
from reusable chat answer history. Completed capacity summaries remain labelled
and unverified. Experiment scoring still requires `completed` and the original
answer contract; a preview cannot satisfy either gate.

## Acceptance and validation

The controlled graph test retrieves a generated manual, receives a real adapter
`done_reason=length`, and checks that the saved result contains cited source text
and none of the truncated draft. One explicit continuation keeps the same thread,
limits, language and sources, completes using one metered request and does not
repeat the successful retrieval. Further tests cover repeated truncation,
cross-owner API denial, frozen-source filtering, inert untrusted text, no-evidence
stops, other exhausted limits, provider overages, cancellation, concurrent clicks
and the hard cap. Existing delegated-budget tests explicitly verify that previews
remain benchmark failures.

An offline, read-only replay of the original V8 Q4 gantry failure produced three
scoped excerpts from its saved observations. Its original `budget_exceeded`
status, 18,731 tokens, `result: null` and archived scorecard were left unchanged.
This demonstrates recovery of evidence, not an improved live answer. The replay
artifact is local and ignored under
`reports/budget-recovery-20261102/v8-offline-preview.json`.
Existing archived results are not backfilled or rewritten. Their explicit
continuation remains available when their recorded budgets permit it.

Final local validation:

| Check | Result |
| --- | --- |
| Full backend suite | **419 passed, 7 platform/capability skips** |
| Frontend suite | **79 passed in 17 files** |
| Production frontend build | Passed |
| Offline M5 calibration and extended gates | **28 runs passed** |
| Ruff lint and formatting | Passed, 111 Python files |
| Publication guard, including Git history | **609 tracked files, zero findings** |
| Browser acceptance | Cited preview, source reader, explicit finish and language switch checked with generated fixtures |

Commands used were `.venv/Scripts/python.exe -m pytest -q`,
`.venv/Scripts/ruff.exe check backend tests`,
`.venv/Scripts/ruff.exe format --check backend tests`, `npm test` and
`npm run build` in `frontend`, and the documented `eil.benchmark` /
`eil.benchmark_extended` offline commands with both agent modes and two
repetitions. The publication command was
`.venv/Scripts/python.exe -m eil.publication --history`.

An existing eight-second delegate timeout test missed child startup during an
overlapping run of tests and benchmarks. It passed in isolation and in the final
full run after the benchmark processes finished; its time budget was not changed.

No fresh live-model quality run, hosted comparison, model download, HPC job or
production deployment is part of this change. Existing M5 and V8 failures remain
recorded.
