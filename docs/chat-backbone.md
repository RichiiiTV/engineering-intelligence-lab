# Admin knowledge, automatic matching, one problem chat

Implemented on 2026-10-30 following the user's clarified workflow. This supersedes
the earlier user-managed machine/notebook flow as the normal entry point.

## Use

**Administrator:** open Administration → Machine knowledge. Upload manuals,
documentation or code exports and confirm that you may publish them to users in
this workspace. No machine name, notebook or document selection is required.
The background worker extracts passages, creates local embeddings, asks the local
LLM for structured machine identity and automatically publishes the assignment.
Upload activity shows progress/failures; source entries show the identity quotation
and whether assignment came from a source identifier or semantic inference.
Archive inappropriate/obsolete sources; provide a corrected edition when the data
does not identify its machine. Failed jobs support bounded explicit retry/cancel
and staged-byte discard. Partial batch failures retain only unsubmitted files.

**Regular user:** open the root page, describe the problem and optionally attach
images or error logs. The backbone identifies the relevant published machine,
retrieves its sources and handles conversation context. If identity is ambiguous,
it asks a short clarification in the same chat. There are no machine, notebook,
source-selection or debug controls. Account/password controls and chat history
remain available. Use a new chat for a different problem or machine.

Answers expose source markers. A click opens the exact manual/code/log passage or
original image. Read-only proposed checks are separate from observations and
hypotheses; generated answers do not apply or test changes on equipment.

## Scope and automatic organization

The new admin catalog is explicitly available to active accounts in this one local
workspace. Existing owner-private machine data is **not** silently published.
The older public-reference library retains its generated/licensed-public policy.
User problem attachments and conversations remain owner-scoped, including against
administrators; they never become shared machine knowledge. Machine management
APIs and Advanced views require an administrator.

Machine identity extraction uses a strict JSON schema and bounded source excerpts.
An identity must occur in an exact source quotation; unsupported identities/profile
values are removed. Explicit identities form groups. For unlabeled material,
semantic assignment requires the LLM to select a listed candidate, cosine ≥0.88
and margin ≥0.12. Otherwise the source stays in an unidentified group. Unknown
groups are excluded from confident automatic matching. Thresholds and extraction
confidence are heuristics, not calibrated physical-identity guarantees.

At question submission, the backend freezes the published source IDs and private
attachment IDs. New uploads cannot enter an already-created answer. Explicit
identifiers and local embedding matches select one machine; close/unsupported
matches produce clarification rather than a guessed diagnosis. Archived sources
remain available to existing snapshots; purge rejects retained catalog references.

Each answer uses a new LangGraph checkpoint/run and the existing step/tool/model/
token/time budgets. Up to four bounded prior exchanges supply context. Reviewed or
capacity-limited earlier claims are replaced with a review notice in model context.
Submission IDs make a failed chat request retryable without duplicate runs/files.
Pause/resume and token continuation retain original usage and cannot overlap another
active answer in the conversation. No agent can manage users, publish data or extend
its budgets.

## Images and logs

Images are decoded with Pillow, validated as nonanimated PNG/JPEG/WebP, pixel-capped
and normalized to bounded JPEG input. A separate local vision call transcribes all
visible text into a typed observation without receiving log/conversation claims.
Its calls and actual usage are charged to the same run budget. Observations are
cached by immutable attachment ID and local model digest; later answers use that
textual observation rather than repeatedly interpreting a large image. Image-only
transcription is kept separate from a machine diagnosis. Visual observations remain
model inferences; users can compare the original image with the extracted text.

Logs are UTF-8 text with immutable hashes, bounded line passages and `log:` citations.
CSV error logs do not need the synthetic inspection-data schema. New attached logs
must be read before answering; older logs remain available without forcing an
irrelevant reread on a visual-text follow-up. No uploaded code or log is executed.

Limits: four files / 10 MiB per question; at most two images, 5 MiB and 12 megapixels
each; log files up to 2 MiB and 2,000 passages. A run retains the latest eight
attachments, with at most two images. Original private attachments are limited to
1,000 files / 64 MiB across the installation, within the 256 MiB evidence database
limit. Conversations are limited to 100 per account and 100 answers each. Retention
is explicit; there is no automatic deletion of old evidence or histories.

## Local boundary and public references

Private classification, embeddings, vision and generation use verified downloaded
local Ollama models. Cloud aliases and non-loopback private generation are rejected.
The installed default generation model advertises vision support. Source code is
only searchable/readable or statically inspected; there is no shell, include/URL
following, PLC connection, compiler execution, actuator or production write.

No normal problem text automatically goes to Siemens. For an explicit public lookup,
type `/siemens` followed by the public product question. The composer discloses the
destination. Only the literal human-entered public question is bound to the existing
no-argument Siemens tool; files, images, logs, machine profiles and history never
enter that query. Public reference summaries remain unverified.

## Validation and remaining limits

Validation commands: `.venv\Scripts\python.exe -m pytest -q`,
`.venv\Scripts\python.exe -m pytest tests/test_chat_backbone.py -q`,
`.venv\Scripts\ruff.exe check backend/src/eil tests`,
`.venv\Scripts\ruff.exe format --check backend/src/eil tests`, and `uv lock --check`;
in `frontend`, `npm test -- --reporter=dot`, `npm run build` and `npm audit --json`.
The final 2026-10-31 follow-up reran the nine chat-backbone tests, build, Ruff and
lockfile checks successfully. The full-suite counts below are from 2026-10-30.

- Full backend: **254 passed in 215.32 seconds**; frontend: **41 passed**; TypeScript/
  Vite build, Ruff and `uv lock --check` passed.
- Real local ingestion: `xr7-manual.md` and `xr7-control.st` automatically joined
  XR7; `ab9-manual.md` formed AB9. No machine selection was supplied.
- Real normal-user chat: image/log uploaded in the browser, XR7 matched automatically,
  document/code/log/image source markers returned, and private image navigation worked.
- A generated-image follow-up correctly returned **VISUAL-42** with its image citation;
  the final run used 6,106 tokens with no capacity limit. The vision observation/cache
  and its budget accounting have independent failure/coverage tests.
- Failure checks cover unobserved machine identities, ambiguity, unsupported safety
  classifications, malformed attachments, member management attempts, another user's
  files/history, immutable snapshots, duplicate request retries and retained-source purge.
- Five existing SQLite databases were backed up, integrity-checked and restored into
  a separate directory before the upgrade. The account, six investigation records,
  six source hashes and three public document records were preserved exactly. No
  existing private material was published. Backup/restore includes all new tables.

The first live model answer introduced an unsupported safety/interlock role. It is
now visibly review-required; a heuristic grounding check and one bounded correction
attempt were added. Early image follow-ups also exposed context distraction and
unnecessary log rereads; typed visual observations/current-question focus resolve
the tested transcription case. Original failed/partial runs and budgets remain in
the isolated test state. These checks do not establish universal model correctness,
general claim entailment, safety certification or reliable physical-machine identity.
The prior M5 model-quality failures and cross-database audit crash window remain
documented. Hosted validation remains deferred; no paid provider or production
deployment ran. A real internal corpus has not been supplied for scoring.

Local ignored evidence: `reports/chat-final-release.log`, `chat-frontend-final.log`,
`chat-live-ingestion.json`, `chat-live-final-vision.json`, `chat-upgrade-results.json`,
`chat-backbone-upgrade-backup/snapshot.zip`, `chat-simple-user.png`,
`chat-admin-knowledge.png`, `chat-vision-proof.png` and dependency audit reports.

Compatibility references: [Ollama structured outputs](https://docs.ollama.com/capabilities/structured-outputs),
[local vision input](https://docs.ollama.com/capabilities/vision),
[Pillow image validation](https://pillow.readthedocs.io/en/stable/reference/Image.html).
