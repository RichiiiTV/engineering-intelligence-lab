# M6–M10 implementation and validation

Completed locally on **2026-10-30**. The existing workbench is running at
`http://127.0.0.1:8000/`; choose **My machines** or open
`http://127.0.0.1:8000/?page=machines`. Existing credentials are preserved; sign in
with your existing account. Advanced retains the original diagnostic workspace.

## Delivered

| Stage | Result |
|---|---|
| M6 | Transactionally checked authentication generations close password/revocation races. Separate audit history, bounded auth outbox, anonymous counters, complete JSONL export, verified archives/backup coverage and authenticated readiness. |
| M7 | Preserved passage locations, typed product/version filtering, observed-citation and block-quotation contracts, explicit unsupported/review-required/capacity outcomes. |
| M8 | Private machine profiles and manual/document/code sources; automatic local embedding groups; bounded read/static tools; supervised atomic ingestion with progress/cancel/retry/discard, PDF page batches and retained source lifecycle. |
| M9 | Named notebooks, explicit source revisions, immutable per-answer snapshots, bounded follow-up history, new run budgets/checkpoints, idempotent submission, safe rich text/code and direct citation navigation. Public Siemens questions remain separate from private context. |
| M10 | Hash-anchored generated knowledge pack and 50-case evaluation, local model/cloud-alias checks, bounded warm embedding batches, parser complexity limits, cross-platform fixture bytes, complete local release validation and verified workspace migration. |

Similarity groups are computed automatically from owner-scoped machine centroids
with complete-link cosine threshold 0.82. Unknown/unindexed machines remain
individual. A group is an organization aid; it never merges physical machine
identity, permissions or the sources an answer is allowed to read.

## Validation

| Check | Result |
|---|---|
| Final complete backend: `.venv/Scripts/python.exe -m pytest -q` | **245 passed in 208.30 seconds** |
| Complete frontend: `npm test -- --reporter=dot` | **37 passed**, 9 files |
| `npm run build` | TypeScript + Vite passed |
| `ruff check .`, `ruff format --check .` | Passed; intentional invalid uploaded-code fixture explicitly excluded |
| `uv lock --check` | Passed, 187 resolved packages; no dependency changes required |
| Python advisory audit | **167 installed packages, zero known advisories** |
| Full npm advisory audit | **Zero known advisories**, including development dependencies |
| Versioned knowledge suite, lexical | **50/50** |
| Same knowledge suite, live local hybrid embeddings | **50/50** |
| Real isolated PDF | Generated 21-page document parsed in batches 1–20 and 21; original page 21 preserved |
| Real background source upload | Completed/indexed with local embeddings; existing notebook selection unchanged |
| Real Deep Agents/Ollama notebook | Initial code answer was visibly review-required for missing citation syntax. Follow-up resolved the prior subject, cited selected sources and declined to infer a hardware defect. A bounded private-source citation reminder was added and independently tested with token accounting. |
| Browser | Automatic group, machine sources, notebooks, follow-up, source-change notice, safe code rendering and citation-to-exact-passage navigation inspected. |

Evaluation categories: retrieval 32/32, applicability 4/4, no-match retrieval 4/4,
citation/quotation contracts 4/4, static inspection 2/2, isolation 2/2, frozen
snapshots 2/2. These are deterministic mechanism checks on generated fixtures;
they do not establish real-manual coverage or LLM engineering accuracy.

Official compatibility references used: [Ollama embeddings](https://docs.ollama.com/api/embed),
[Ollama cloud model behavior](https://docs.ollama.com/cloud),
[Docling converter/page ranges](https://docling-project.github.io/docling/reference/document_converter/).
Downloaded local GGUF model metadata and live embedding dimensions were checked
before private generation; no hosted validation or paid model invocation ran.

## Existing workspace upgrade

Before migrations, four existing SQLite databases were backed up with SQLite's
backup API and integrity-checked. A compatible archive was restored successfully
into a separate directory. The upgrade preserved the existing account/password
hash/role, all **six investigation records**, all **six case source hashes**, and
the original bytes/metadata of the **three shared starter documents**. Public
vectors were reindexed with the current retrieval format. Audit migration verified
the retained chain; readiness reports zero pending events and zero stale shared
passages. The current loopback app returns HTTP 200. Temporary preview service
was stopped; unrelated application containers were not changed. The existing
stopped Ollama/gateway dependencies were restarted with their original settings.

Local, ignored verification artifacts:

- `reports/m10-release-tests.log`, `m10-frontend-final.log`
- `reports/m10-knowledge-{lexical,hybrid}.json`
- `reports/m8-pdf-smoke.json`, `m10-ingestion-smoke.json`
- `reports/m10-upgrade-backup/snapshot.zip`, `m10-upgrade-results.json`
- `reports/m10-readiness.json`, Python/npm advisory reports
- `reports/m10-machine-groups.png`, `m10-notebook.png` (generated demo account)

Private workspace backups and test state remain local and are excluded from Git.
Use the existing restore helper into a new directory; restored sessions are revoked.

## Remaining limits

- General claim entailment, causal conclusions and hardware correctness remain
  unverified. The earlier M5 live model-quality failures remain recorded. A local
  model can still need review; citation resolution alone is not a quality pass.
- Hosted-model comparison remains **deferred by the user**. No real internal
  corpus or redistributable manufacturer-manual corpus was supplied for scoring.
  The new pack is original CC0 fictional material, not supplier documentation.
- Authentication changes and audit outbox records are atomic. Domain/run state and
  workspace audit delivery span databases; abrupt failure between those commits
  can still leave a content-free audit-record gap. Source hashes and durable
  owner-scoped execution events support reconciliation. The local hash chain is
  not externally anchored against a host administrator.
- The system remains a bounded local prototype: 200-page/10-MiB machine PDFs,
  OCR disabled, explicit database/source/job/history limits, no automatic history
  rotation. See [the operator workflow and exact limits](machine-workspaces.md).
- Similarity thresholds are heuristic. Review physical identity and versions;
  grouping does not authorize cross-machine evidence sharing. Uploaded code is
  never executed, compiled, connected to a PLC, or written to production systems.

All authorized stages are implemented. No M11 or production deployment was started.
