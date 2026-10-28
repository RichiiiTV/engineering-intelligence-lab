# M3 — PDF/CSV evidence ingestion and traceable investigation

Completed on 2026-10-28. The final **99-test offline suite passed in 107.28 seconds** in the
dev-only environment, without Docling/PyTorch or model downloads. The optional real Docling
golden verifier passed, and a real local Ollama case investigation correctly connected the
S03 CSV increase to the maintenance record on **PDF page 2**. M4 has not started.

## Implemented scope

| File | Responsibility |
| --- | --- |
| `backend/src/eil/evidence.py` | Immutable case/source BLOB storage, strict CSV validation, source snapshots, lexical search, prescribed metrics and scoped citation resolution |
| `backend/src/eil/pdf_ingest.py` | Real Docling PDF/table extraction with page/item provenance, local assets, CPU limits, timeout and process cleanup |
| `backend/src/eil/case_tools.py` | Four read-only tools closed over a frozen case/source list |
| `backend/src/eil/exports.py` | Source/citation resolution, observed/requested query provenance and explicit uncertainty checks |
| `backend/src/eil/uploads.py` | Body-size admission before multipart spooling, including chunked requests |
| `api.py`, `cli.py`, `agent.py`, `runs.py`, `service.py`, `execution.py` | Case/upload/query/export endpoints, optional case CLI flag and durable M2 run integration |
| `output/pdf/synthetic-maintenance-note.pdf` | Owned, visually verified two-page golden source PDF |
| `.gitattributes` | Preserve PDF bytes and cross-reference offsets across Windows Git checkouts |
| `tests/fixtures/`, `tests/evidence_fixtures.py`, `tests/test_evidence.py`, `tests/test_case_api.py` | Captured actual Docling output, fixture authoring source, offline golden/isolation/security/export/API tests |
| `scripts/verify_m3_golden.py` | Reproducible optional real Docling acceptance command |
| README, architecture, roadmap, AGENTS, settings, `pyproject.toml`, `uv.lock` | Version 0.3.0, installation, usage, tested dependencies and milestone boundaries |

No UI, MCP, Langfuse, production API integration or vector database was added. The lexical
golden check passes, so there is no demonstrated need for vector retrieval in this milestone.

## Evidence and isolation architecture

Explicit uploads receive generated source UUIDs and SHA-256 hashes, under a generated case
UUID. The original bytes and normalized observations are stored in
`<EIL_STATE_DIR>/data/evidence.sqlite3`. Filenames are metadata, never paths. Uploads are
immutable; duplicate content in a case is rejected, and there are no replacement/delete APIs.
The accepted data-policy declaration is `synthetic` or `licensed-public`; it does not
automatically verify the uploader's rights or the contents' provenance.

A case-backed investigation freezes its source IDs at submission. The same IDs survive
pause/restart/resume. Later uploads affect new investigations only. Tools do not accept a
case ID, URL, SQL statement or filesystem path; their closures enforce the stored case and
source list. Case tools replace the global fixture tools, preventing a silent demo-data
fallback. Legacy runs without a case ID retain their original behavior.

Docling consumes a PDF `DocumentStream`, uses the standard local CPU pipeline and FAST
TableFormer, and disables OCR, remote services and external plugins. Models must be
explicitly prefetched. The parser child sets Hugging Face/Transformers offline mode, and a
parent watcher prevents orphan conversion processes. One parser is admitted at a time.
The application, not the model, launches that fixed worker.

Normalized chunks retain Docling item references, character offsets, original bounding-box
coordinates and page numbers. Long items are split at 1,200 characters. Multi-page items
retain their full page list; the first page is a convenience locator, not a claim that all
text belongs there. Boxes are item-level provenance, not exact highlights for each substring.

Search builds a bounded in-memory SQLite FTS5 index from only the chosen snapshot. Its BM25
corpus statistics cannot be influenced by other cases or later uploads. User/model queries
become literal quoted word tokens, never raw SQL or FTS operators. Search returns at most
five chunks; relevance scores are not factual confidence values.

CSV sources are analyzed separately through the existing deterministic `station_metrics`
function. No implicit merging/deduplication across files occurs. Source hashes, grouping,
metric definition, rounding, rows scanned/used and excluded incomplete station coverage are
reported. Citation rows are explicitly samples, not the complete aggregation's provenance.
The original source remains downloadable with an independently checkable hash.

## Validation and bounded inputs

| Control | Implemented bound |
| --- | --- |
| PDF | 10 MiB, 20 pages, 2,000 chunks |
| CSV | 2 MiB, 20,000 rows |
| Case | Ten sources, 30 MiB of original upload bytes |
| Upload body | 10 MiB plus 64 KiB of multipart overhead, checked before spooling |
| PDF conversion | One at a time; 120-second parent deadline, 100-second Docling deadline; two model-inference threads |
| Retrieval | Query 1-500 characters, up to 32 literal terms, 1-5 results |

CSV requires exactly the nine inspection columns: `row_id`, `timestamp`, `station_id`,
`period`, `inspected`, `false_ejects`, `true_rejects`, `illumination_lux`, `exposure_us`.
UTF-8/BOM input, unique safe row IDs, ISO timestamps, stations S01-S04, baseline/incident
periods, bounded non-negative integer measurements, positive inspected counts and total
rejections not exceeding inspected counts are validated. Incomplete station periods are
listed and excluded; no comparable station is an actionable error.

Malformed/unsupported input is rejected before source registration. Quotas/duplicate checks
are repeated transactionally at insertion. Body limits work even without `Content-Length`.
Missing Docling/assets returns 503, parser contention 429, invalid content 422, oversized
request bodies 413, duplicate/quota conflicts 409 and cross-case/unknown sources 404.

## Citation export and uncertainty

`GET /api/investigations/{id}/export` returns a versioned JSON evidence report: answer,
source hashes/metadata, resolved PDF excerpts or CSV rows, tool observations, requested and
observed query definitions, and explicit uncertainty. It accepts explicit same-source grouped
shorthand, while flagging malformed, unresolved, unobserved and missing answer citations.
CSV `rN` is an internal zero-based row ordinal; resolution gives the original row ID and
physical CSV line. PDF references retain pages and item-level bounding boxes.

The uncertainty fields state `causation: not_established`, `statistical_confidence:
not_estimated` and `claim_entailment: not_verified`. This keeps claims bounded by the evidence
without inventing numerical confidence. Resolving a citation establishes a source location,
not that every attached model claim follows from it. A zero-hit search is not proof that
the document lacks an observation.

## Versions and official compatibility sources

| Component | Tested version |
| --- | --- |
| Project / Python / uv | 0.3.0 / 3.12.15 / 0.13.5 |
| Docling / docling-slim | 2.144.0 / 2.144.0 |
| docling-core / docling-parse | 2.105.0 / 7.24.1 |
| docling-ibm-models / PyTorch | 4.0.4 / 2.15.0 |
| python-multipart | 0.0.32 |
| Deep Agents / LangGraph | 0.7.32 / 1.2.18 |
| LangGraph SQLite checkpointer / langchain-ollama | 3.1.2 / 1.1.0 |
| SQLite | 3.53.1, FTS5 available |
| FastAPI / pytest / Ruff | 0.162.0 / 9.2.0 / 0.17.3 |

The lock resolves 177 packages including the optional document extra. The tested dev-only
environment has 100 distributions; the full document environment has 157. Docling/PyTorch
remain in the optional `documents` extra. Lightweight docling-core and multipart support are
base dependencies. The PDF extra was restored after the dev-only CI check.

Official documentation and installed signatures were checked:

- [Docling advanced options: offline assets, DocumentStream, limits and model options](https://docling-project.github.io/docling/usage/advanced_options/)
- [Docling pipeline options](https://docling-project.github.io/docling/reference/pipeline_options/)
- [Docling document converter source](https://github.com/docling-project/docling/blob/main/docling/document_converter.py)
- [SQLite FTS5, literal queries and BM25](https://www.sqlite.org/fts5.html)

## Commands and observed results

Commands ran from the repository root, with `$env:UV_CACHE_DIR` set to `.uv-cache` on this
managed host. Dependency/model downloads required approved network access; ingestion itself
did not download anything. No paid provider or cloud parsing service was used.

```powershell
uv sync --locked --extra dev --extra documents
uv run --no-sync docling-tools models download layout tableformer --output-dir .eil/docling-models --quiet
uv run --no-sync python scripts/verify_m3_golden.py
uv sync --locked --extra dev --offline
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv lock --check --offline
uv pip check
uv run python -m eil.cli demo
uv sync --locked --extra dev --extra documents --offline
```

- **99 tests passed in 107.28 seconds**, without the optional document stack. Ordinary tests
  load the real captured Docling document through docling-core, then use actual SQLite
  retrieval/analytics, the real Deep Agents graph and controlled model responses. No model
  downloads, Ollama or paid APIs are required. M1/M2 tests remain green.
- New checks cover page/table provenance, exact S03 metrics, multiple CSV source namespaces,
  case isolation, score stability across other-case/later uploads, frozen snapshots through
  pause/upload/resume, malformed data, duplicate/quota rejection, filename traversal, literal
  FTS/SQL handling, blocked default-fixture tools, scoped export, grouped/malformed references,
  multipart/chunked bounds and CLI missing-case errors.
- The optional real golden verifier passed: **2 pages, 1 table, page 2 retrieved, S03
  +12.5021 percentage points**. Both PDF pages were rendered with Poppler and visually checked.
  A direct real conversion also ran with HTTP sends forbidden, verifying local model use.
- A real Uvicorn API uploaded and parsed the PDF in **21.09 seconds**, accepted the CSV and
  verified the same page/finding. The real Ollama case run completed in **51.344 active
  seconds**, with **4 model calls, 4 tool calls and 16,688 tokens**. It reported S03's increase,
  the page 2 setpoint/exposure changes, and correlation rather than causation.
- The first live export check exposed grouped references that were not recognized by the
  exporter. That parser was fixed and regression-tested. Re-exporting the immutable saved run
  resolved all four references: two page 2 PDF chunks, plus `ROW-00003` and `ROW-00171`, with
  no unresolved, malformed or unobserved citations. A subsequent real HTTP readback passed.
- In the SDK-free environment, the API still served stored evidence/export and verified the
  original PDF hash. A new PDF conversion returned the documented 503 dependency instruction
  and registered no source. The server was stopped after the smoke checks.
- Ruff, lock freshness, installed compatibility and the unchanged deterministic demo passed.
  The staged PDF blob was checked byte-for-byte against the visually verified file; its
  SHA-256 is preserved by the binary Git attribute.
  The verifier's initial sandbox temporary-directory denial was resolved by using an isolated
  directory under ignored `reports/`; its successful run cleans up only that generated state.

Ignored raw evidence is in `reports/m3-*`, including conversion logs, the real run/export,
golden verifier JSON, HTTP readback results and isolated live case state. Generated input
and captured Docling output are committed for reproducible CI. Layout/table model assets
and caches remain ignored local state.

## Remaining limits and stopping point

- This is local development on loopback: no authentication, per-user authorization, storage
  encryption or global retention policy. UUID scoping is not user authorization. Licenses
  and demo-data declarations are not independently verified.
- PDF support is for PDFs with a text layer; OCR is disabled. FAST table extraction and
  hard character chunking can lose layout/context. One golden document does not establish
  accuracy for arbitrary manuals, scans, diagrams, languages or multi-page tables.
- The parser is a separate bounded process, not a native-code sandbox or OS memory limit.
  A disconnected client may leave conversion running until completion/deadline. Document
  bytes stay local, but explicitly prefetched model assets need separate provenance/version
  management for strict reproducibility across future model updates.
- Lexical retrieval can miss synonyms and semantically related text. There is no vector
  retrieval or evidence-grounded claim-entailment evaluator. Valid citations do not guarantee
  a factually correct answer; confidence values are intentionally not fabricated.
- CSV analysis supports the prescribed inspection schema and stations only. Sources are
  compared individually; overlapping datasets are not combined automatically. Example row
  citations are not exhaustive support for an aggregate.
- The M2 limits around read-only node replay, remote Ollama cancellation, trusted local SQLite
  state and cross-version checkpoint recovery still apply. Case snapshots freeze upload
  content, but there is no cross-version ingestion migration policy.

M3 acceptance is complete for the generated golden scenario. Stop here; do not begin M4.
