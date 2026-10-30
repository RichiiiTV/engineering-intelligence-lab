# M6–M10: dependable machine investigation workspaces

Authorized 2026-10-29 after the whole-project review. The user clarified that the
product should investigate manuals, documentation and internal code for different
machines. This plan extends M1–M5; stages are implemented and validated sequentially.

## M6 — Authentication, audit resilience and readiness

- Close concurrent password-change/login and revocation races with an authentication
  generation checked transactionally when issuing and accepting sessions.
- Separate durable audit history from identity/session storage, preserve legacy
  history, use a bounded transactional outbox, aggregate anonymous denials and
  expose backlog/capacity failures without making normal sign-in depend on history size.
- Add complete audit export/archival and backup/restore coverage; preserve explicit
  limits and a verifiable chain. Keep authentication and mutation failures explicit.
- Add functional readiness alongside liveness: database headroom, audit backlog,
  local model availability, parser and semantic-index state.
- Acceptance: password/revocation race fails closed; anonymous-read flood does not
  grow identity history unboundedly; exhausted audit destination leaves sign-in
  usable and readiness degraded; backup restores history and revokes sessions.

## M7 — Trustworthy retrieval and answer/source contracts

- Preserve canonical PDF provenance and typed product applicability metadata.
- Validate citations against both frozen selections and actually observed passages.
- Distinguish source-backed references, unsupported questions, missing product
  details, review-required answers and capacity-limited summaries. General engineering
  entailment/causation remain subject to review; do not claim a universal verifier.
- Add deterministic checks for explicitly quoted passages/typed critical claims.
- Acceptance: unseen/forged citations are visibly review-required; multi-page items
  retain ranges; incompatible explicit versions are excluded/labeled before ranking.

## M8 — Private machine backbone and document/code lifecycle

- Owner-scoped machine profiles grouped by family, with model/firmware/software
  context and separate local manuals, documentation and source-code collections.
- Automatic similarity groups from local document/machine embeddings, scoped to
  the signed-in owner. Groups suggest related machines/documents; physical machine
  identities, permissions and per-answer evidence scope remain explicit. Unknown
  or low-confidence matches stay unassigned rather than mixing private evidence.
- Support generated or user-authorized internal material only in private workspaces.
  Shared library uploads remain generated/licensed public material.
- Code is UTF-8 text with line references and bounded read/search tools. Never execute
  code, follow includes/URLs, expose a shell or connect to equipment.
- Bounded background parsing/indexing jobs with progress, retry/cancel and durable
  failure/restart handling. Larger PDFs use bounded page batches in the same isolated
  worker, preserving original page references and resource caps.
- Archive obsolete documents without affecting existing snapshots; reclaim only
  unreferenced content through an explicit reviewed operation. Show capacities.
- Acceptance: another account cannot list/read/export machine material; code line
  references resolve; paused answers retain original sources; job failures leave
  published indexes unchanged; private content cannot reach Siemens automatically.

## M9 — Machine notebooks and usable conversations

- Named notebooks under a machine, source selections and persistent product context.
- Follow-ups retain bounded owner-scoped conversation context and a frozen source
  snapshot for every answer; show when selections/editions change.
- Normal interface: select machine, ask, inspect inline source passages/code lines,
  clarify missing details and continue the same conversation. Preserve Advanced.
- Safe rich-text rendering, direct citation navigation, source previews and clear
  unsupported/review-required outcomes. Consolidate account administration and keep
  failed forms intact. External lookup always uses a separate explicit public query
  when machine/notebook context is present.
- Acceptance: follow-up resolves an earlier question's subject; notebook/machine
  boundaries hold; active runs cannot inherit newly added documents; UI failure
  states recover without losing inputs or expanding external disclosures.

## M10 — Evaluation, starter knowledge and release validation

- Versioned generated engineering/machine/code fixtures and a reviewed reproducible
  retrieval/answerability suite covering English/German, versions, absent answers,
  tables, code snippets, conflicting sources and injection attempts.
- Score retrieval, citation contracts, abstention, applicability, job failure/recovery
  and isolation separately. Preserve existing M5 baselines. No paid provider runs.
- Publish a generated knowledge-pack manifest with coverage/licences and a workflow
  for users to import their own private machine manuals/code. No supplier manual
  redistribution is implied without an appropriate licensed source.
- Run full backend/frontend/build checks, targeted live local-model/browser smoke,
  isolated PDF verification, dependency compatibility checks and backup migration.
- Acceptance: documented gates pass and all remaining limits are explicit. Stop
  after implementation, local deployment verification and reporting.

## Release safeguards

Use generated fixtures for tests; retain existing cases/accounts. Back up actual
state before migrations/restart, verify the idle server identity, bind to loopback
and preserve cumulative budgets and approvals. Do not create real user passwords,
publish internal material, enable remote tracing or introduce production controls.

## Status

- M6 implemented: authentication generations, separate audit history with bounded
  transactional outbox/anonymous counters, archive segments/full JSONL export,
  backup support and authenticated readiness. Targeted acceptance:
  `pytest tests/test_m6.py tests/test_auth_storage.py tests/test_knowledge_admin.py`
  — **34 passed in 31.03 seconds**. Archive quota: eight retained segments; history
  is retained and chain links verified, never silently purged. Backlog saturation
  blocks account-security changes explicitly while sign-in remains usable.
- M7 implemented: canonical passage metadata/page ranges, typed product context
  and explicit edition exclusion, retrieval-specific embedding inputs, deterministic
  citation/block-quotation contracts and visible review/unsupported outcomes.
  Targeted backend acceptance: **28 passed in 12.46 seconds**. Frontend: **33
  passed**, TypeScript/Vite build passed. General claim entailment remains unverified.
- M8 implemented: owner-scoped machine sources, local embedding centroid groups
  (complete-link cosine threshold 0.82), bounded text/code inspection with line
  references, atomic background indexing, explicit retry/cancel and archived-source
  lifecycle. Reviewed purge rejects investigation/notebook references. Targeted
  backend gate: **29 passed in 13.38 seconds**; frontend build passed. PDFs are
  capped at 200 pages, 10 MiB and 2,000 passages; installation storage quotas apply.
  Similarity groups never merge identities or automatically share evidence.
- M9 in progress. M10 starts after the notebook acceptance gate.
