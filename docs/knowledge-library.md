# Shared knowledge library, users and audit trail

Implemented under the user's request of 2026-10-29. The normal question flow
retrieves document passages before answering; document management remains in
Administration. Uploaded case evidence, shared reference documents and public
Siemens MCP references remain separate sources with distinct citation IDs.

## Documents and answers

- Three original generated guides are bundled under CC0-1.0: PLC timing,
  measurement/reject rates, and source/version checks. They establish no exact
  Siemens device requirements and are labelled educational demonstration material.
- The app seeds them idempotently, preserving any administrator's disabled state.
  No manufacturer PDF is redistributed without a licence. Public visibility alone
  is not a redistribution licence.
- Administrators add UTF-8 text, Markdown or PDF files with title, product family,
  edition/version, licence provenance and explicit workspace-sharing confirmation.
  Documents and passages are immutable. Add a new document for a new edition;
  disable the old one for new questions. Existing run snapshots still resolve it.
- Shared documents are visible to all signed-in workspace users. Private case
  uploads retain their existing owner boundary and are never promoted automatically.
- The composer enables the library by default and allows a document subset or
  opt-out. The API freezes selected active document IDs at submission. Retrieval
  excludes other documents before ranking, not after retrieving global neighbours.
- `read_knowledge_library()` is a no-argument read-only Deep Agents tool bound to
  the human question and frozen selection. It caches one bounded result per run;
  models/documents cannot change source scope, run a network fetch or write files.
  A skipped required lookup or missing citations receives metered graph feedback.
- Citations use `kb:<document UUID>:p<page>:c<chunk>` and resolve against the frozen
  snapshot independently of model output. Exports separate library citations,
  unresolved/unobserved IDs, document hashes and retrieval provenance from case
  PDF/CSV evidence and Siemens search metadata. The UI shows excerpts and source
  downloads. HTML/document/model content is escaped, never executed.
- Matching passages do not prove claim entailment or compatibility. Prompts require
  the matching product/version, missing-detail questions, conflicting-edition
  disclosure, and explicit uncertainty when the selected sources cannot answer.

## Local vector backend

`knowledge_documents` and `knowledge_passages` live in the existing quota-limited
evidence SQLite database, so existing backups preserve raw documents, metadata,
chunks and vector BLOBs. There is no new external database or hosted provider.

The fixed local Ollama `/api/embed` endpoint generates normalized float32 vectors
with `embeddinggemma:300m` by default (`EIL_EMBEDDING_MODEL`). The endpoint must be
loopback HTTP, has no model/user-selected URL, no redirects/proxy inheritance,
bounded batches/responses and a timeout. Cloud model entries are rejected. Model
name and digest are stored with vectors; changed models require reindexing.

Search builds a bounded in-memory FTS5/BM25 and sqlite-vec cosine search over the
frozen corpus, combines rankings with reciprocal-rank fusion, and returns at most
three passages. Keywords are literal tokens, never raw SQL/FTS operators. Only
the installed sqlite-vec extension is loaded; extension loading is disabled
immediately afterward. Relevance is not a calibrated confidence score.

Indexing is an explicit administrator action, with batches of at most 16 texts,
a 90-second batch-loop deadline (plus at most one 30-second in-flight request),
and atomic index publication per document. A failed reindex preserves the old
index. Query embeddings remain inside the cumulative supervised run deadline;
each library call also consumes the existing tool budget. Embedding work is local
retrieval, not an unmetered generative model invocation. Its model identity and
retrieval method are recorded separately from generation token counters.

Limits: 100 library documents, 10,000 passages, 2,000 passages per document.
PDFs use the existing isolated parser: 10 MiB, 20 pages, no OCR. Text/Markdown
are limited to 1 MiB; page labels follow explicit form-feed boundaries (otherwise
page 1). Large manufacturer manuals need a separately reviewed increase to parser
limits; this feature does not silently weaken isolation or resource caps.

If indexing, the model or vector extension is unavailable, answers use labelled
keyword retrieval. No cloud fallback, automatic model download or paid run occurs.

## User administration

Existing opaque sessions, Argon2 password hashes, session expiration and case
ownership remain. Administrators list paginated users and active session counts,
create members/admins, change roles, disable/reactivate accounts and revoke
sessions. Role changes and deactivation revoke sessions immediately. Accounts are
disabled rather than deleted, preserving evidence ownership and audit identities.
An administrator cannot demote/disable their own account or remove the last active
administrator. Permission checks and changes occur inside a SQLite transaction.
There are at most 1,000 accounts. Members cannot access management or audit APIs.

Initial enrollment still requires a trusted operator setup code. No default or
automatically chosen real-workspace password was introduced. Password changes
remain self-service with the existing current-password check.

## Audit trail

Legacy authentication audit history is migrated into a separate `audit.sqlite3`.
Account/session changes first commit to a bounded transactional outbox in the auth
database; delivery is idempotent and retains the original timestamp. Anonymous
denials use bounded aggregate counters. A history outage leaves login usable and
readiness degraded; a full security-event outbox rejects account-security changes
explicitly. Legacy events retain
their recorded actors/times/types; new metadata defaults to empty rather than
inventing historical details. Each new entry commits with a previous hash and
SHA-256 entry hash, serialized with concurrent writers. Database triggers forbid
application updates/deletes. Admin reads verify the full local chain.

Events cover authentication, account/session changes, document administration,
investigation submission/finish (IDs, status and counters), application writes,
source/report downloads and access denials. Route templates and UUIDs are stored,
not raw URLs, query strings, questions, passwords, session tokens or document text.
The existing owner-scoped run/tool event log retains detailed execution provenance;
the workspace audit is content-minimal. Document metadata records source provenance.

The admin view supports exact event-type/actor-ID filters and cursor pagination.
Page JSON downloads contain up to 100 events and the `next_after` continuation
cursor; **Download complete history** streams JSONL across all retained segments.
An administrator can archive a verified segment; up to eight segments are retained
without automatic deletion, and backup/restore includes them. The UI states page
and backlog limits explicitly. A local database/OS
administrator can replace the database or its triggers; this is an application
audit trail, not externally anchored tamper-proof storage. Retain exported heads
independently when stronger assurance is required.

Account changes and their audit outbox entries share an auth-database transaction.
Document/run state and workspace audit entries live in different databases;
they are not one distributed transaction. A process failure between commits can
leave an incomplete workspace audit record. Independent source hashes and the
owner-scoped run event log remain available for reconciliation.

## Validation

- Full backend regression: `uv run pytest -q` (equivalent direct environment
  invocation during validation) — **223 passed in 183.45 seconds**. Windows
  process access was required; a sandbox-stalled run was stopped and rerun with
  that access. The capacity-summary edge case was corrected before the passing run.

- `uv lock --check --offline`: 187 resolved packages; sqlite-vec 0.1.9 is now an
  explicit dependency (it was already present transitively). No new network service
  was introduced. Ruff check and format checks pass.
- Frontend: `npm.cmd test` — **33 tests pass**; TypeScript/Vite production build
  passes. Source selection, escaped report passages, admin account protections,
  explicit mutation payloads and audit pagination/integrity are covered.
- Backend acceptance includes real SQLite cosine matching for semantic synonyms,
  keyword fallback/model drift, scope filtering before ranking, no-argument cached
  retrieval, malformed/unlicensed/duplicate uploads, durable citation resolution,
  metered graph feedback, token refusal, bounded capacity summaries, nonlocal or
  credentialled endpoint refusal, administrator permission checks, session revocation, legacy
  audit migration, concurrent chain writes, update/delete refusal, tamper detection,
  and backup/restore of vectors and audit records with session invalidation.
- Real local EmbeddingGemma and Ollama browser run: **two model calls, one library
  tool call, 3,272 generation tokens**, hybrid retrieval active, one cited library
  reference, no unresolved/unobserved library citations. The answer correctly
  cited the generated weighted-rate example (30/1,100 ≈ 2.7273%). This checks that
  closed example, not general engineering correctness.
- Browser checks confirm the default composer, cited answer/passages, indexed
  document administration, user/session controls and filtered verified audit view.
  Test state/accounts are generated and isolated from the actual workspace.
- The actual workspace was backed up with SQLite integrity checks before migration.
  Its three generated guides are preloaded and indexed (six passages); existing
  case IDs, owners and source hashes are unchanged. No real account/password was
  created. The app still requires the operator's first-account setup if unconfigured.
- Model installation used the official registry's hash-verified GGUF through the
  local blob/create API because the existing Ollama container intentionally has no
  external network. Its network configuration remained unchanged. The model is
  `embeddinggemma:300m`, local manifest digest
  `b44b2e244cc37dabe08d767b6405d17dbbbdd026bff3797ae37a0f245786d400`.
- Detailed generated test output, backups, model-install observations and browser
  screenshots are under ignored `reports/knowledge-library/` and
  `reports/knowledge-release.log`. Hosted validation remains deferred at the user's
  request; no paid provider call occurred.

Implementation references: [Ollama embedding API](https://github.com/ollama/ollama/blob/main/docs/api.md#generate-embeddings),
[EmbeddingGemma model](https://ollama.com/library/embeddinggemma),
[sqlite-vec Python integration](https://github.com/asg017/sqlite-vec/blob/main/examples/simple-python/demo.py),
[vector distance API](https://github.com/asg017/sqlite-vec/blob/main/site/api-reference.md),
[SQLite FTS5/BM25](https://www.sqlite.org/fts5.html).
