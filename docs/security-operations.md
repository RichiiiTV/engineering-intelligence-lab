# Local workspace operations

EIL remains bound to `127.0.0.1`. Accounts add application access control;
they do not protect files from the Windows account that owns the workspace.
Do not expose this development server to a network. TLS, enterprise identity,
equipment access and production deployment are separate work.

## First account

Start the workbench, then run this in a second terminal in the repository:

```powershell
uv run python -m eil.cli auth-bootstrap
```

Open `http://127.0.0.1:8000/`, enter the printed one-time code, choose a username
and a password of 14–128 characters. The code expires in 15 minutes and is
consumed once. It cannot enroll another administrator after setup. Existing
unowned local cases and investigations are assigned to this first owner.
No default password is installed. Do not put a password or setup code in Git.

Passwords use Argon2. Session tokens are opaque, stored hashed in SQLite and
sent in a host-only HttpOnly/SameSite=Strict cookie (Secure when HTTPS is used).
Sessions expire after eight hours or 30 idle minutes. Sign out revokes a session;
changing a password revokes all sessions. Sign-in has account/client rate limits
and at most two simultaneous password verifications. API data, downloads, SSE,
traces, drafts and API documentation require authentication. SSE rechecks the
session while streaming. Case ownership applies to administrators too.

Choose **Account** to change a password or, for administrators, add a member.
Approval records take reviewer identity from the authenticated session; a request
cannot supply its own reviewer identity. Native CLI tools are trusted operator
tools and their decisions are explicitly distinguished from session approvals.

## Trash and retention

Account → Files and storage lists owned cases and Trash, with pagination.
Pause/finish a case's active investigations before moving it to Trash. Restore
keeps sources, IDs, drafts and cumulative run budgets. Trashed cases are hidden
from normal APIs and cannot start/resume work.

Ninety days in Trash makes a case *eligible* for permanent deletion. Nothing is
automatically deleted. Review the exact plan, IDs and SHA-256, then type the
displayed confirmation to approve it. Approval binds the actor and plan and
expires after 15 minutes. A restore or source change invalidates it. Permanent
deletion first creates a verified backup; a full backup quota blocks deletion.
The plan is restartable after interruption, including checkpoint cleanup.
Cross-database deletion is recoverable/idempotent, not one SQLite transaction.

## Backups and restore

Administrators can create/download backups through Account when the service is
idle. Mutations are excluded during backup/deletion. Native operator commands
refuse to race a running service; stop it first:

```powershell
uv run python -m eil.maintenance status
uv run python -m eil.maintenance backup
# Use the actual reviewed backup file and a NEW directory:
uv run python -m eil.maintenance restore --archive .eil/backups/<backup-id>.zip --destination .eil-restored
# Inspect the restored installation before selecting it:
$env:EIL_STATE_DIR = Join-Path (Get-Location) '.eil-restored'
uv run uvicorn eil.api:app --host 127.0.0.1 --port 8000
```

Archives contain SQLite snapshots, manifest checksums and integrity checks.
They include all accounts' case data and password hashes: store downloads
privately. Session/setup tokens are excluded and sessions are revoked on
restore. Restore accepts only fixed database names, bounded sizes and matching
checksums. It rejects duplicate/traversal paths and existing destinations. An
incomplete restore remains marked and cannot start a service. Checksums detect
corruption; they do not authenticate an archive from an untrusted sender.

At most three archives / 2 GiB are retained in the installation. No older copy
is silently erased. Move a verified older copy to secure offline storage before
creating another. Model weights, Docker images, dependency caches and external
backup copies are operator-managed and excluded from this application quota.

Database logical limits: evidence 256 MiB, runs/events/drafts 128 MiB,
checkpoints 512 MiB, accounts/audit 16 MiB. There are at most 500 cases and 5,000
runs across all accounts. Each event is at most 128 KiB; admission reserves
maintenance room near the run database limit. Existing file/page/row/run budgets
still apply. SQLite free pages are reusable after deletion. WALs, a temporary
backup copy and parser scratch require additional working space; these are not
a hard quota on the entire Windows/Docker disk.

## Isolated PDF conversion

Uploaded PDFs require Docker Desktop's Linux engine (Windows) or the local
Docker socket (Linux). There is no host-process fallback. Build the fixed image:

```powershell
docker build -f containers/pdf/Dockerfile -t eil-pdf-worker:1 .
uv run --extra documents docling-tools models download layout tableformer --output-dir .eil/docling-models --quiet
```

Only the approved `.eil/docling-models` directory may be mounted, read-only.
The worker receives the PDF on stdin and returns bounded normalized JSON. It
runs as UID 65532 with no network, a read-only root, all capabilities dropped,
no new privileges, 2 GiB RAM/no swap, two CPUs, 128 processes and 128 MiB scratch.
The image ID is resolved before invocation. It receives no case database, host
shell, Docker socket, credentials or arbitrary host path. Admission permits one
parser at a time; the worker has an inner 110-second deadline and a host limit.
Missing Docker/image/assets fail closed. Keep Docker and Windows patched.

The historical M3 script directly exercises trusted conversion. The upload
acceptance path now always uses the container. Use the smoke command and
recorded resource probe in the remediation report for the deployed path.

## Verification and evaluations

`/api/cases/<id>/verify-claims` accepts bounded typed metric/quotation claims.
It recomputes CSV station/period rates and checks exact quoted substrings at
scoped citations. Exports include independent per-CSV comparisons and potential
conflicting measurements. They never merge unrelated CSVs. Adjacent PDF items
are returned with their own citations; agent observations omit repeated layout
metadata to preserve context, while exports resolve full provenance.

These checks do not prove arbitrary prose, PDF truth, statistical confidence or
physical causation. Model notes remain unverified. The benchmark's closed replay
contract additionally checks observed numeric/citation/replay claims and can ask
the model to correct a rejected answer through the same budgeted graph. It never
reads the expected-answer manifest to generate feedback. Results measure this
guarded workflow, not unaided model accuracy.

```powershell
uv run pytest -q
uv run python -m eil.benchmark --provider offline --agent-mode both --repetitions 2 --output reports/calibration-new
uv run python -m eil.benchmark_extended --provider offline --agent-mode both --repetitions 2 --output reports/extended-new
```

The four extra cases add another affected station, zero increase, contradictory
records and a missing PDF. Original v1 failures remain archived. Live runs are
explicit and bounded. Hosted runs require `OPENAI_API_KEY` and an explicit
`EIL_OPENAI_MODEL` outside Git; missing configuration records `not_run`.
CI performs offline acceptance on Windows/Linux, frontend builds and advisory
audits. Dependabot covers both uv projects, npm, Docker and Actions weekly.
There is no Git remote configured here, so hosted CI execution requires choosing
and pushing to the intended repository.

The normal question box includes Siemens documentation lookup. Public SPS/PLC
questions without files select it automatically, with a visible opt-out.
With attached files it starts disabled and requires a separate public product
query. The graph tool has no query arguments: it sends only the user's fixed
query/product/version fields to the MCP endpoint. It never sends case evidence
or model-generated text. Lookup is charged to the same run budgets and its
snapshot is reused after pause/resume; an interrupted unknown outcome is not
resent automatically. Reviewed V20 manual
candidates are metadata references, separated from unverified MCP summaries.
Unsupported TIA versions and unknown CPU/firmware compatibility remain explicit
gaps. On MCP outage, matching local manual candidates are still shown with an
outage label. Linked pages are not automatically fetched or executed.
The old `/?page=siemens` link opens the normal composer. The independent protocol
diagnostic view remains at `/?view=advanced&page=siemens`.

## Shared library and administration

The normal composer now searches selected shared library documents locally.
Shared-library uploads require an administrator, explicit workspace-sharing
confirmation, and generated or explicitly licensed public material. Keep private
case uploads inside their existing owner boundary. Manufacturer documents require
their own licence provenance and matching product/edition metadata.

Administration provides document availability/indexing, paginated users, role
changes, account deactivation and session revocation. Role changes/deactivation
revoke sessions; self-demotion/deactivation and removal of the last active admin
are rejected. There is no unauthenticated user-management or audit endpoint.

Audit records are append-only through the app and locally hash-chained, with
admin-only metadata views/export and integrity verification. They exclude question
and document contents, credentials, tokens and raw URL/query strings. A database/OS
administrator can replace the database; this is not an externally anchored
compliance archive. Existing owner-scoped run events retain detailed provenance.

Library vectors and documents are inside the existing evidence database and are
included in verified backups. Local embeddings cannot select an external URL or
cloud provider; outages use labelled keyword search. See
[library architecture, limits and validation](knowledge-library.md).
