# Review remediation results — 2026-10-29

The ten findings in the original project/security review have implementation
and acceptance coverage. Hosted live validation is intentionally pending at the
user's request. The local application remains a read-only investigation tool;
these changes do not authorize production equipment or network deployment.

## Finding-by-finding result

| Original gap | Implemented result | Acceptance evidence / limit |
|---|---|---|
| Live model quality | Suppress unnecessary Ollama reasoning, remove virtual filesystem/planning tools from case model bindings, compact PDF observations, preserve adjacent citations, use framework structured output/native Ollama JSON schema for bounded evaluation synthesis, validate typed numeric/citation/replay claims and retry through the same budgeted graph. | Final original gate 12/12 live; expanded single-agent gate 8/8 live. Earlier failures are retained. These are guarded workflow results, not unaided model accuracy or a general reliability guarantee. |
| Authentication, tenant access and reviewer identity | Argon2 accounts, one-use local enrollment, hashed revocable sessions, idle/absolute expiry, bounded/rate-limited sign-in, owner-scoped case/run/source/export/SSE/draft access, session-derived approval actors and administrator-only backups/user creation. | Cross-user/role denial, session expiry/revocation, setup replay, password change, authenticated approval attribution and bounded password admission tests. No permanent password was chosen for the user's workspace. |
| PDF OS isolation | Dedicated locked CPU Docling image, fixed local engine, immutable image ID per call, no network/host fallback, non-root/read-only/capability/resource limits and bounded stdin/stdout/deadlines. | Real two-page golden conversion: 21 chunks. Live probe confirmed UID 65532, no network, read-only root, zero capabilities, no new privileges, seccomp, 2 GiB/no swap, two CPUs and 128 processes. Missing image/assets and admission/time limits fail closed. |
| Global storage and lifecycle | Installation-wide SQLite/row/event limits; recoverable Trash/restore; manual 90-day eligibility policy; exact content/actor-bound deletion approval; verified backups before purge; bounded archives; verified restore into a new directory. | Quota across owners, stale/foreign/wrong-hash decisions, checksum/path/overwrite rejection, preservation of actual sources/drafts/tokens/checkpoints, session revocation and interrupted-purge recovery tests. No user case was permanently deleted. |
| Provider overage undercount | Actual over-envelope usage and the terminal budget state are committed atomically, followed by an audited overage event. Further model calls/continuations are refused. | Synthetic one-token/provider overage regression verifies counters and trace after failure. Actual usage can exceed a limit if the provider violates the reservation; accounting reports that overage instead of hiding it. |
| Claim support and lexical recall | Recomputed per-CSV evidence ledger, potential conflict reporting, bounded typed metric/quotation verification endpoint, adjacent-page-item retrieval, full independent citation resolution in exports and closed replay-contract validation during evaluations. | Incorrect rates, wrong station/source snapshot, fabricated quotations, conflicting datasets, unsupported replay claims and missing citations are rejected. General prose entailment and physical causation remain explicitly unverified. |
| Siemens SPS coverage/version scope | Explicit family/CPU/firmware/TIA context; exact outbound query disclosure; reviewed V20 manual metadata; separate unverified MCP results; explicit no-version-match/compatibility status; local manual candidates survive remote outage. | Eight positive/negative golden question cases, exact official manual host/spoof tests, two live contextual MCP searches and browser rendering. Exact CPU/firmware applicability is not asserted. The upstream service still often returns marketing pages. |
| Narrow/one-shot evaluations | Four additional hash-frozen generated cases: another affected station, no increase, conflicting PDFs and missing PDF. Repeated original single/delegated and expanded single-agent live runs; repeated offline calibration in both modes. | 20/20 final live rows and 28/28 final offline rows passed. Hosted comparison remains unrun, by user instruction. Original v1 files/results are preserved. |
| Older-case UI/history | Selected-case latest-run request, owner-filtered paged case/history APIs, next offsets and deduplicated case pages; neutral labels when recent status is unavailable. | UI regression opens a case whose run is absent from the global recent list; UI/backend pagination regression covers more than 50 entries. |
| CI/update policy | Windows/Linux offline acceptance, locked dependencies, frontend tests/build, advisory audit job, read-only pinned Actions and weekly Dependabot for both uv projects, npm, Docker and Actions. | Equivalent Windows commands passed locally. No Git remote is configured, so a hosted Actions run and Linux CI run have not been performed. |

## Final evaluation evidence

| Suite | Mode | Repetitions per case | Result | Median seconds, all attempts |
|---|---|---:|---:|---:|
| Original v1, live Ollama | Single | 2 | 6/6 | 20.344 |
| Original v1, live Ollama | Delegated | 2 | 6/6 | 30.946 |
| Expanded v2, live Ollama | Single | 2 | 8/8 | 20.899 |
| Original v1, offline calibration | Both | 2 | 12/12 | See scorecards |
| Expanded v2, offline calibration | Both | 2 | 16/16 | See scorecards |

The single-agent default is retained. Delegation was slower and used more tokens
in this small sample; these measurements do not establish a general provider or
architecture ranking. Expanded live delegation was not claimed/tested. Offline
model output/usage is scripted and is never treated as model-quality evidence.

All live runs used local `qwen3.5:4b-q8_0`, temperature 0, 8,192-token context,
2,048 output tokens, and the existing cumulative 65-step/12-model-call/20-tool/
65,536-token/180-second experiment envelope. The workbench keeps its separate
M2 defaults/hard caps. Every correction request is metered. No general-purpose
subagent or hidden summarization call is enabled. Expected-answer manifests
are consulted only by scorers; runtime checks use observed tool evidence.

Final scorecards, findings, evidence, traces and run snapshots are checked into
[`output/benchmarks/review-remediation-20261029/`](../output/benchmarks/review-remediation-20261029/README.md).
Intermediate failed scorecards/per-row scores are included too; their complete
local observations remain in ignored `reports/gap-remediation/`. The original
0/6 live baseline under `output/benchmarks/m5-v1/` is unchanged. Final runs were
executed from the working tree; metadata records source hashes and the base Git
revision, with the remediation committed after verification.
The implementation is frozen in local commit `016c3df` on
`codex/close-review-gaps`; documentation/evidence follow in a separate commit.

Structured-output behavior follows the official
[LangChain contract](https://docs.langchain.com/oss/python/langchain/structured-output)
and [Ollama JSON schema API](https://docs.ollama.com/capabilities/structured-outputs).
The exact Siemens Cloud documentation host is allowed because it hosts the
reviewed [S7-1500 V20 manual collection](https://docs.tia.siemens.cloud/r/simatic_s7_1500_et_200mp_manual_collection_enus_20/comprehensive-information/cpu-function-manuals/cycle-and-response-times).
Other `siemens.cloud` subdomains and lookalike hosts remain rejected.

## Validation commands

- `uv run pytest -q`: **197 passed in 150.18 seconds**.
- `npm.cmd test`: **25 passed**; `npm.cmd run build`: TypeScript/Vite passed.
- Ruff check and format checks passed; `uv lock --check --offline` resolved the
  unchanged 187-package lock; no whitespace errors in the diff.
- `uv run python scripts/verify_pdf_isolation.py`: **passed**, real Docker worker
  plus two-page/table golden input. Probe retained in the versioned artifacts.
- `uv run python -m eil.benchmark --provider ollama --agent-mode both --repetitions 2 --timeout-seconds 180 --output reports/gap-remediation/final-v1`: **12/12**.
- `uv run python -m eil.benchmark_extended --provider ollama --agent-mode single --repetitions 2 --output reports/gap-remediation/final-v2`: **8/8**.
- The corresponding offline commands in both modes and two repetitions:
  **12/12 + 16/16**. No network/model request is permitted by calibration workers.
- `pip-audit --path .venv/Lib/site-packages --skip-editable`: **zero known
  vulnerabilities**; `npm.cmd audit`: **zero**. Audits exclude the editable
  project, Windows/Docker/native drivers and unknown vulnerabilities.
- Real contextual Siemens SDK searches: server `2026-03-30`, S7-1500 V20 returned
  six remote links/one reviewed manual candidate; S7-1200 V20 returned eight
  remote links/one reviewed candidate. Neither claimed firmware compatibility.
- Browser: synthetic account sign-in, account/storage controls, move to Trash,
  restore, verified backup creation and Siemens manual/summary rendering.
  Only disposable generated test state was used for these mutations.

## Handoff

The actual workspace was idle and was backed up before restart. It runs at
`http://127.0.0.1:8000/`; health is public, case access now returns 401 until
sign-in. The first account is intentionally unconfigured. Run
`uv run python -m eil.cli auth-bootstrap`, then enter the one-time code and your
chosen credentials in the browser. Existing cases will be assigned to that
account. Advanced workspace remains available after sign-in.

See the [operator guide](security-operations.md) for backup/restore, retention,
container setup and limits. Hosted validation remains pending as explicitly
requested; no hosted key/model is required for local use. No later milestone,
remote tracing, production API, PLC read/write or actuator connection was added.
