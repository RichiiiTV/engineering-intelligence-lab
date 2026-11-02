# Citation quality and GPU model profiles

This scoped follow-up was authorized on 2 November 2026: fix the known citation
quality failures and configure candidates for L40S, A100 40 GB, A100 80 GB and
four A100 40 GB. It preserves the original evaluation outputs and the default
local Ollama configuration. No model weights were downloaded, HPC job submitted,
private machine corpus published or hosted provider invoked.

## Citation defects and remediation

The saved V3 trace corrects one earlier report detail: the Q8 controller run failed
with `EvidenceNotFound` after passing an exact citation ID to `read_catalog_source`,
which expected a bare document ID. It did **not** fail at the output limit in that
run. The Q4 run retrieved the MCU/bootloader passage but cited the product overview
and repeated the wrong citation after the initial repair.

- Catalog observations now distinguish `document_id` from `citation_id`. Source
  tools accept an exact previously observed citation as a selector, then apply
  the same frozen source/owner authorization. Guessed IDs and other machines
  remain rejected. Byte offsets are omitted from model observations so they are
  not mistaken for line numbers; stored source/export bytes remain intact.
- Exact observed `[Citation: kb:...]` / `[Quelle: kb:...]` references normalize to
  canonical citations. Unknown IDs and code examples are not silently rewritten.
- Selected MCU and binary-memory literals must occur in the nearby cited passage,
  not merely somewhere in the retrieved set. Paragraphs/list items and adjacent
  labelled attribution/quotation blocks are handled explicitly. An unrelated good
  citation elsewhere cannot hide an incorrect one.
- Verbatim evidence quotations are checked against the cited observations.
  Decorative outer quotation marks and Markdown escaping are presentation, while
  source text remains immutable. Changed quotations are repaired or withdrawn.
- One bounded repair includes actual excerpt/ID pairs and asks for a short
  replacement answer, not a debate about the rejected draft. Existing cumulative
  budgets still apply. This uses the existing middleware and model adapter.
- After an unsuccessful repair, unsupported citation/quotation drafts are
  withdrawn. The user receives clearly labelled, bounded original source excerpts
  with their actual references, or an explicit request for documentation if no
  observation is available. No extra LLM call is made. `answer_mode` distinguishes
  `generated`, `source_extract` and `citation_abstention`; the failed
  `draft_answer_contract` is retained for honest evaluation.
- Narrow guards cover the observed German belt/pulley and racked/latched
  confusions. They retain the original terms rather than inventing a translation.
  This is **not** general translation or engineering claim verification.
- Claims of searching user problem logs are rejected unless the corresponding
  lookup actually completed in that run. Public document citations cannot prove
  that a private investigation step happened. Hypothetical requests for logs and
  actual logged lookups are handled separately.

All excerpts remain untrusted reference data. Markdown/control-looking source
content is escaped, and embedded fake citation lines are not rendered as new
references. Private observations stay owner-scoped. Siemens queries, source
snapshots, budgets and retry accounting retain their existing boundaries.

## Evaluation

The existing public pack and three fixed questions are unchanged. Versioned
diagnostic iterations remain in ignored local report directories rather than
overwriting prior runs. V4/V5 exposed layout/quotation false warnings as well as
continued small-model terminology errors. These iterations are development
diagnostics, not controlled model-ranking experiments.

V6 exposed a quotation-parser bug with blank lines in literal fallback excerpts;
it was captured using the actual licensed public Markdown fixture. V7 then passed
all six narrow automated cases (five generated/repaired answers and one source
extract). Manual review initially suspected an unperformed log-search claim in
the Q4 unknown-code answer. **Trace review corrected that interpretation:**
`read_problem_logs` was called, but searched an empty attachment set; no user logs
were supplied. This must not be interpreted as inspection of real logs. V8 adds
an explicit completion-based provenance check, with generated failure tests for
the no-lookup case. All earlier raw scorecards stay unchanged.

The final suite records ordinary model answers separately from fallback excerpts.
A correct extract does not turn a failed model draft into a model-quality pass.
`claim_entailment` remains `not_verified`: literal occurrence and quotation checks
cannot prove a free-form causal diagnosis, negate a conflicting edition or establish
compatibility with installed equipment. Human review and broader evaluation remain
necessary. Hosted validation remains deferred.

The final **V8** run used a stable implementation hash and the unchanged public
fixtures, 120-second / five-model-call / 32,768-token / 1,024-output-token limits.
It passed **5/6 final-response checks**:

| Case | Qwen 3.5 4B Q8_0 | Qwen 3.5 4B Q4_K_M |
| --- | --- | --- |
| Octopus MCU / bootloader | Generated/repaired answer, correct `c10` passage; passed. | Generated/repaired answer, correct `c10` passage; passed. |
| Gantry symptoms | Generated/repaired answer; passed narrow citation/terminology checks. | **Output-token limit reached before completion; no answer; failed.** |
| Unknown code | Bounded unsupported-code response; passed. | Bounded unsupported-code response; passed the added unperformed-log check. |

V8 contains five generated/repaired responses and zero fallback responses; its
overall gate remains **failed** because of that output-cap failure. The earlier
V7 source-excerpt response separately exercised the fallback in a live run.
No new random retry was used to replace V8's failed case, and no budget or score
was relaxed to make it pass. Both original controller citation failures are
resolved in this follow-up; reliable small-model completion remains a limitation.
The proposed larger GPU models have **not** been validated against these cases.

Raw model outputs and local state stay outside Git. Implementation and source
hashes are recorded in each new scorecard, with separate complete/stable flags;
an incomplete or implementation-changing evaluation cannot pass the gate.
The final V9 validator adds the German `Logsuche` spelling and was tested by
offline replay of all six V8 outcomes, without model calls or status changes:
the same five responses passed and the output-cap failure remained. Both Q4
unknown-code traces contain the actual empty-set lookup, so this guard correctly
leaves those responses unchanged.

Local verification:

- Complete backend suite: **409 passed, 7 platform/capability skips**; the last
  spelling extension was also covered by **55 focused checks**.
- Linux generated-only launcher/manifest/profile suite: **23 passed**. Actual argv
  assembly was exercised through a generated fake vLLM CLI, not an inference engine.
- Frontend: **75 tests across 16 files passed**, TypeScript/Vite build passed.
- Both unchanged offline benchmark gates: **28/28 scripted runs passed**.
- Ruff lint/format: **112 files passed**; lockfile and whitespace checks passed.
- Offline npm policy: **189 entries, 0 findings**. No dependency versions changed.
- Bandit: **0 high / 8 medium / 19 low**, retaining the previous reviewed SQL,
  subprocess/container and tokenizer-flag findings; no new high/medium finding.
- Publication guard: **606 tracked files and published history, 0 findings**.

The full Windows/Linux CI acceptance and live dependency-advisory gates run on
publication. Reproduce the source checks with:

```bash
uv run ruff check backend/src/eil tests scripts/model_manifest.py scripts/hpc_profiles.py
uv run ruff format --check backend/src/eil tests scripts/model_manifest.py scripts/hpc_profiles.py
uv run pytest -q
uv run python -m eil.publication --history
uv run python -m eil.supply_chain
```

## GPU deployment support

The [GPU profile guide](gpu-model-profiles.md) documents four reproducible operator
templates: BF16 Qwen 3.5 9B on L40S / A100 40 GB, 27B on A100 80 GB, and
35B-A3B with TP=4 across four A100 40 GB. Each includes a bounded Qwen3 Embedding
0.6B server and memory/concurrency headroom. Native query instructions have a
separate index identity and frozen configuration, requiring reindexing.

The generator also provides older Qwen3 Q8 Ollama aliases compatible in principle
with the reported legacy module. It does not promise image support for those
text-only alternatives or patch the module's known advisories. Native model
architectures, built-in parser aliases and BF16 support were checked against
official model/vLLM documentation; **actual GPU fit, diagnostic quality, topology,
driver compatibility and tokens/second remain unmeasured on these allocations**.

`python -m eil.quality_followup --configured` plans a three-case run for the
operator-configured local backend/model. Adding `--live` explicitly runs it in a
fresh ignored directory. It supports the vLLM profiles without a cloud fallback;
credentials remain exclusively in the runtime environment.
