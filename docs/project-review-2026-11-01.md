# Project review — 1 November 2026

The review found three concrete security/availability gaps and several small
performance and UX improvements. They are fixed with regression coverage. No
known dependency vulnerability or evidence of package tampering was found in the
versions checked. That result does not certify packages against unknown malware.

## Scope and fixes

Review covered authentication, roles and session revocation; owner authorization;
machine/library/problem-source separation; chat and run recovery; model adapters;
retrieval and evidence exports; Siemens query construction; upload/PDF isolation;
backup/retention; audit metadata; browser rendering; and dependency/CI controls.
Independent security, performance and frontend reviews informed the fixes, followed
by another review of the integrated diff. No equipment or production system was
accessed. Hosted-model validation remains deferred.

| Priority | Finding | Resolution and acceptance |
| --- | --- | --- |
| P2 — privacy | The Ollama SDK follows HTTP redirects by default. A misconfigured or hostile loopback proxy could redirect a generation request containing private context to another host. | Explicitly disable redirects on both generation clients. A mocked 307 test proves the prompt is not forwarded to the external target. |
| P2 — privacy | Embeddings did not enforce the full local-model identity policy used for generation: a remote alias or incomplete local-model metadata could pass the earlier check. | Share the downloaded-GGUF/size/digest/remote-alias checks across adapters. Bound `/api/tags` to 2 MiB. Invalid metadata is rejected before any text-bearing POST; local vectors and digest keys retain their existing format. |
| P2 — availability | Applying an empty retention plan still made a complete workspace backup. A member could repeat this no-op to exhaust the shared three-backup quota. | Reject an empty pending plan before backup creation. Repeated attempts create zero backups; a real purge still creates its recovery backup. Completed/interrupted retention recovery remains covered. |
| P3 — performance | Idle chats repeatedly fetched the conversation list and detail; slow requests could overlap and late results could replace a newer selection. | Poll only active runs, serialize periodic requests, pause hidden tabs and refresh on return/history open. Abort/version checks protect selection changes. Completed idle chats have zero periodic reads after their initial load. |
| P3 — performance | Machine lookup tools sent storage/ingestion metadata and repeated query text to the model on fresh and cached reads. | Compact only the model-facing observation. Preserve exact passage text, citation/source IDs, product versions, source locations, uncertainty and unknown fields. Save the complete raw lookup first; exports and source snapshots remain unchanged. |
| P3 — UX | Adjacent headings, lists and paragraphs could render as one confusing block. Initial chat-load errors lacked a focused recovery action. | Parse safe block boundaries, preserve escaped HTML and constrained citations, and expose the existing translated Retry action. Late submission responses preserve newer drafts and chat selections. |

These are scoped fixes; no dependency major upgrade, source corpus change,
evaluation baseline rewrite or agent framework replacement was introduced.

## Dependency and supply-chain checks

Checked the committed lockfiles and the installed environment with Node 24.12.0
and npm 11.6.2. Reports and clean-install artifacts remain in the ignored local
`reports/project-review-20261101/` directory.

| Check | Result |
| --- | --- |
| `npm audit --json` | 0 known advisories |
| npm registry signatures | 139 installed packages verified; 54 verified attestations |
| All locked versions through OSV | 189 unique npm package versions; 0 matches |
| Lock versus official registry metadata | 189 entries use public HTTPS registry URLs and SHA-512 pins; 0 tarball/integrity mismatches |
| Fresh `npm ci --ignore-scripts` versus existing installation | 8,522 package files compared; 0 differences, excluding generated `.bin` wrappers and the installer's root metadata |
| Python `pip-audit` | 167 installed distribution records: 166 third-party packages audited, 0 known vulnerabilities; the editable project itself is skipped and reviewed/tested here |
| Python lock through OSV | All 186 locked PyPI package versions, including optional/platform-specific dependencies; 0 matches |
| Bandit | 0 high, 8 medium and 18 low alerts, manually reviewed as described below |

Install hooks in this lock are `esbuild@0.28.2` and the optional macOS-only
`fsevents@2.3.3` (not installed on this Windows host). A clean frontend build works
without third-party install hooks. `frontend/.npmrc` now disables them by default;
CI explicitly uses `npm ci --ignore-scripts`. Normal explicit `npm test` and
`npm run build` commands still run.

A new offline CI guard rejects non-registry URLs, missing/invalid SHA-512 pins,
linked packages and newly introduced install-hook packages. Advisory checks and
registry signature verification remain separate gates. Publication scanning now
also catches npm tokens, checked-in secret configuration files and literal npm
authentication values; environment-variable placeholders remain supported.

`whatwg-encoding@3.1.1` is deprecated transitively. It has no advisory match in
this check. A major test-environment upgrade solely to remove that deprecation
would add risk without resolving a demonstrated vulnerability.

Signatures establish registry integrity, not benign behavior. Advisory databases
can lag a compromise, and this was not a full manual source audit of every
transitive package. See [npm signature verification](https://docs.npmjs.com/verifying-registry-signatures/),
[npm lifecycle controls](https://docs.npmjs.com/cli/v11/using-npm/config/#ignore-scripts)
and the [OSV API](https://google.github.io/osv.dev/api/).

### Static-alert triage

Seven medium Bandit B608 alerts are variable-length SQL placeholder lists or
constant allowlisted field/table names in `audit.py`, `catalog_tools.py`,
`evidence.py`, `knowledge.py`, `runs.py` and `storage.py`. User values are bound
parameters, not concatenated SQL. The remaining medium B108 alert is the isolated
PDF container's `/tmp` tmpfs: the container has a read-only root, no network,
non-root UID, dropped capabilities, resource limits and `noexec,nosuid` tmpfs.
It is not a shared host temporary filename. Low alerts are predominantly fixed
operator subprocess commands and deliberate exception handling. No exploitable
agent-controlled shell or SQL path was established. Alerts were not broadly suppressed.

The review did not establish another concrete authorization bypass. Existing
tests continue to exercise cross-owner denial, session revocation, bounded
retrieval, source snapshotting, upload rejection and canonical-human-only Siemens
queries. This is an application review, not an external penetration test.

## Performance: measured facts and limits

**Fewer idle requests.** Previously a selected chat requested its list and detail
every 1.5 seconds: up to 80 reads/minute, including completed investigations.
Completed chats now issue no periodic reads. Active runs refresh after the prior
request finishes; hidden tabs pause, and visibility/history actions trigger a
fresh read. Frontend tests verify request counts, slow requests, cleanup and races.

**Smaller tool observations.** Three saved public Voron lookup observations were
8,365 / 8,281 / 8,305 JSON characters. The model-only projection was about
5,418 / 5,423 / 5,395 characters, a 34.5–35.2% reduction. Passage text and evidence
identity were retained. This is a character measurement, not a measured token or
latency improvement. Generated regression fixtures additionally verify a reduction
above 30%, raw snapshot/export equality and cached reuse without changing budgets.

**Retrieval and model latency remain distinct.** The existing 63-passage Voron
lookup traces took roughly 4.69–4.91 seconds per lookup. Search builds a scoped
in-memory FTS/vector index, and the default embedding policy unloads the embedding
model to free VRAM for generation. Either can contribute latency; the trace does
not isolate their contributions.

The failed controller-answer trace had four model calls, 13,209 accounted tokens
and about 55.1 seconds wall time. Its prior chat history was empty. That trace
does not record Ollama's separate load/prefill/decode durations, so total tokens
divided by elapsed time would not be a valid decoding tokens/second figure.

**A new live tokens/second measurement was not run.** The configured local Ollama
endpoint returned a connection error; the Docker Linux engine was also stopped.
No remote provider was substituted, and no unrelated Docker stack was started.

### Recommended next improvements

| Order | Improvement | Acceptance before changing defaults |
| --- | --- | --- |
| 1 | Add explicit local timing for embedding, index construction, retrieval, model loading, prompt evaluation, decode and time to first output. | Benchmark a fixed generated/public question set with the same model digest, hardware and warm/cold policy; preserve quality scores separately. Use Ollama `eval_count / (eval_duration / 1e9)` for decode tokens/second. |
| 2 | Cache scoped retrieval indexes by immutable source snapshot and embedding digest. | Prove identical ranking/citations, owner/catalog isolation, invalidation after archive/reindex and bounded memory; compare cold and warm latency. |
| 3 | Benchmark a short embedding keep-alive window against the current unload policy. | Measure repeated chat latency and GPU memory contention with generation on the actual host. Avoid retaining both models if it causes offloading or out-of-memory failures. |
| 4 | Compare smaller quantizations/model choices on the same evidence and evaluation suite. | Require diagnostic quality and citation support to hold before accepting a throughput gain. Existing failed quality cases must remain visible. |
| 5 | Add an optional streamed progress/answer experience and clearer ingestion summaries. | Keep a clear distinction between provisional text and final validated citations; test reconnect, cancellation, language freezing and keyboard/mobile access. |

These were proposals at the time of this review. Their subsequent implementation,
measurements and remaining failures are recorded in the separate
[performance/HPC follow-up](performance-and-hpc-followup.md); the original results
below remain unchanged. Ollama exposes the
[load, prompt-evaluation and evaluation metrics](https://docs.ollama.com/api/generate)
needed for the first step. No numerical decoding throughput target is asserted.

## README and usability

The README now uses a repository-native SVG cover, a compact three-step workflow,
an actual public-corpus source-reader image, a shorter quick start and a focused
documentation index. Full setup, PDF and development instructions were moved to
[Getting started](getting-started.md). It retains the real pilot failures and
scope limitations. No external font, generated runtime dependency or personal
content was added to the design assets.

## Verification

- Complete backend suite: **307 passed**.
- Frontend: **64 tests across 14 files passed**; TypeScript and Vite production build passed.
- Ruff lint and format: **92 files passed**; `git diff --check` passed.
- Both scripted benchmark gates passed: **28 single/delegated runs** across the
  base and extended fixtures with two repetitions. These are transport/calibration
  checks, not live model-quality or throughput measurements. `uv lock --check --offline` passed.
- Offline npm policy: **189 entries, 0 findings**; dependency results are above.
- Publication/privacy guard: **574 tracked files and the current published history,
  0 findings**. Generated reports, test state and clean-install dependencies remain ignored.
- Browser verification used only the saved public Voron fixture: answer layout,
  citation opening, raw source mode and English controls passed. README and chat
  layouts were checked at desktop and 390-pixel widths; no page overflow or broken
  README images was observed. The README preview approximates GitHub styling.
- Security failure cases include rejected prompt redirects, rejected model metadata,
  repeated empty retention requests, unsafe dependency records and npm secret values.
- UX/performance failure cases include failed initial loads, overlapping refreshes,
  stale selections, late submissions, unknown source references and ambiguous machines.

Reproduction commands are in [Getting started](getting-started.md#development-and-verification).
The full suite uses scripted/offline models; its success does not establish live
engineering answer quality. Earlier [M5 failures](m5-results.md) and the
[Voron controller-question failure](public-machine-pilot.md) remain unchanged.

Private-model checks trust the operator's loopback model server metadata; they
are not remote attestation of server internals. Local backups still rely on host
filesystem protection, audit chains are not externally anchored, and legitimate
usage can consume configured quotas. Production security, equipment compatibility,
host hardening and hosted-model quality remain outside this validation.
