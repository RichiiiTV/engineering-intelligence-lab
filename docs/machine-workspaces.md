# Private machine workspaces and notebooks

This describes the earlier explicit workspace workflow, now retained for admin/
Advanced access. The normal-user entry is [automatic problem chat](chat-backbone.md):
admins upload machine data; users only describe a problem and optionally attach
images/logs. Existing private sources are not automatically shared.

Open **My machines** from the normal workbench. Add a named machine, then upload
its manuals, documentation or code exports. You must have permission to process
the material. Private uploads stay scoped to your account and machine; the shared
administrator library continues to accept only generated/licensed public content.

Indexing uses local `embeddinggemma:300m` embeddings and SQLite vectors plus BM25
keyword retrieval. Active document vectors form a normalized centroid for each
machine. Related machines are grouped automatically with complete-link cosine
similarity at 0.82: every pair must meet the threshold. Different embedding model
digests/dimensions are never compared. Missing indexes remain individual workspaces.
The threshold is a heuristic, not calibrated confidence. Groups do not merge
physical identities, permissions or investigation sources. Generic/shared manuals
can make different machines appear related; review the machine identity yourself.

Create a **notebook** for a problem. It starts with the currently available machine
sources. Review the selection before asking; additions and archived editions produce
a notice and require explicit reselection. Every answer freezes its own source IDs,
machine version context and bounded conversation snapshot. A follow-up gets a new
run/checkpoint and budget, retaining up to four completed question/answer pairs
(question 1,000 characters and answer 2,200 characters per exchange). Prior claims
are untrusted context and must be checked against retrieved evidence again.

Only one queued/running answer per notebook is admitted, including resume/token
continuation. Submission IDs prevent a retried request from silently creating a
second run. Existing pause/resume/explicit token-continuation controls remain under
**Run details and controls**; all previous usage remains charged to its original run.

Answers display code blocks and safe rich text. Click a **Source** marker to open
its passage, then download the immutable original if needed. Page ranges, parser
item/bounding-box metadata and code line ranges survive citations and exports.
Citation/quotation validation checks source identity and observation, not general
engineering entailment. Missing/unseen references are visibly review-required.
There is one bounded citation-format reminder; a model that still omits references
remains review-required. General causation/hardware correctness is unverified.

Python uploads allow bounded syntax parsing (32,000 characters, 1,000 tokens,
80 levels of nesting); more complex files stay searchable text with an explicit
inspection limit. Other code formats are text inspection only. Code is never run,
compiled, connected to a PLC, or used to follow includes/URLs. Agent tools cannot
change users, source selections, jobs, budgets or files on the host.

Private generation requires a loopback HTTP Ollama endpoint and a downloaded GGUF
model verified through local metadata; cloud models/aliases are rejected before
private prompts. Embeddings have the same local boundary. Trust the local Ollama
service and host configuration. The optional Siemens lookup sends only the separate
**Public Siemens question** entered by the human, never machine profiles, document
text, source code or notebook history. Public results are untrusted references.

## Ingestion and lifecycle limits

- Up to 50 machines per owner, 50 notebooks per machine, 100 turns per notebook,
  and 100 active sources per machine. Whole-installation evidence storage remains
  256 MiB and 10,000 passages; disabling a source does not delete its history.
- UTF-8 text/code up to 1 MiB; each upload up to 10 MiB. PDFs up to 200 pages and
  2,000 passages use 20-page batches in `eil-pdf-worker:2`. Case PDFs retain their
  existing 20-page limit. OCR remains disabled; scanned-only files fail explicitly.
- One supervised ingestion worker, four queued/running jobs and 30 MiB staged bytes,
  500 retained job records. A job has a 600-second overall deadline. Each PDF batch
  has a 110-second container kill limit and fixed memory/CPU/no-network/read-only
  controls; machine indexing is bounded to 420 seconds within the overall deadline.
- Index vectors and publication are atomic. Failures retain inactive staged sources;
  retry/cancel is explicit. A service restart marks running jobs interrupted. Parent
  death stops the trusted worker and only its generated parser container. No silent
  resend occurs for uncertain Siemens outcomes.
- Archive retains old sources for existing answers. A reviewed purge API requires
  the inactive source's SHA-256 and the exact deletion confirmation. It rejects
  retained notebook/investigation references and active work. It removes local
  application rows, not copies in backups or exported reports. No agent has this API.
- No automatic history deletion. On capacity exhaustion, review/archive the workspace
  and explicitly discard stopped unsuccessful staged uploads from Upload activity
  when their bytes are no longer needed; retry then requires a fresh upload. This
  never deletes published sources or answers. Retained failed uploads count toward
  the 30 MiB staged-byte limit. Review the workspace
  and backups with an operator. Job-history rotation and unlimited corpora are not
  implemented. The application remains a bounded local prototype.

## Generated knowledge pack and evaluation

`data/benchmarks/eil-knowledge-v1/manifest.json` lists ten original CC0 fictional
manual/code fixtures, hashes and 50 versioned checks. Its invalid `checks.py` is
deliberately excluded from repository lint and is only read as data. These fixtures
are educational; no supplier manuals or real internal code are redistributed.
Upload your own authorized material to a private machine to investigate your system.

```powershell
uv run python -m eil.knowledge_benchmark --output reports/knowledge-lexical.json
uv run python -m eil.knowledge_benchmark --semantic --output reports/knowledge-hybrid.json
docker build -f containers/pdf/Dockerfile -t eil-pdf-worker:2 .
```

The semantic command uses the configured local embedding model; it does not call
a hosted provider. Metrics separate retrieval (32), explicit applicability (4),
no-match retrieval (4), citation/quote contracts (4), static inspection (2), isolation
(2) and frozen snapshots (2). Both lexical and live hybrid runs passed 50/50 locally.
These scores do not measure LLM answer correctness, reliable engineering abstention
or general prompt-injection resistance. The earlier M5 quality failures remain
recorded, and hosted validation remains deferred.
