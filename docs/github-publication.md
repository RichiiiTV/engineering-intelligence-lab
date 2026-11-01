# GitHub publication review

Local review completed on 2026-11-01 before publishing to the user-selected public
repository `RichiiiTV/engineering-intelligence-lab`.

The first remote acceptance run then exposed checkout-portability failures.
See [the root causes and correction](ci-portability.md); the local results below
remain the historical pre-publication record.

## Review and documentation

Rechecked the source-reader changes: resolved local citations use only the saved
investigation export; source text stays escaped; remote source media is inert;
original downloads and image previews retain the existing authenticated endpoints.
The source list, exact excerpt and native Escape/focus behavior are covered by
acceptance tests. The previous desktop/mobile browser verification is recorded in
`source-reader.md`.

Rewrote the root README around the current admin-ingestion / normal-chat workflow,
with Windows setup, local model configuration, public Siemens query boundaries,
the source-reader screenshot, an architecture diagram, documentation links and
explicit quality limitations. Removed obsolete README claims about unauthenticated
APIs and user-managed source selection in normal chat. The screenshot uses the
licensed public Voron corpus and a generated local QA workspace.

Expanded Git ignore rules for local `.env.*` overrides (preserving `.env.example`)
and SQLite journal/WAL/SHM sidecars. No source corpus, application behavior or
dependency version was changed for publication.

## Commands and results

| Check | Result |
| --- | --- |
| `.venv\Scripts\python.exe -m pytest -q` | **283 passed**, 230.60 seconds |
| `cd frontend; npm test` | **52 passed**, 12 files |
| `cd frontend; npm run build` | TypeScript and Vite build passed |
| `.venv\Scripts\ruff.exe check backend/src/eil tests` | Passed |
| `.venv\Scripts\ruff.exe format --check backend/src/eil tests` | 85 files already formatted |
| `uv lock --check` with workspace-local `UV_CACHE_DIR` | Passed; 187 packages resolved |
| `.venv\Scripts\python.exe -m eil.cli demo` | Deterministic synthetic S03 finding, with causal uncertainty |
| README relative file/anchor checks | All local targets exist |
| `git diff --check` | Passed |

The initial lockfile check could not write to the sandbox's default uv cache.
Repeating it with the ignored workspace-local `.uv-cache` completed successfully;
no lockfile update or dependency installation was needed.

## Publication content check

A local scan examined all **917 distinct historical blobs** reachable from the
pre-publication branch head (16,627,228 bytes). It found no matches for the reviewed
GitHub/provider/AWS token or private-key patterns, no tracked runtime/credential
paths and no blobs over 50 MiB. This is a bounded pattern/path check, not a proof
that arbitrary secrets or security defects cannot exist. The final documentation
changes were also reviewed before commit.

Only `.env.example` and `reports/.gitkeep` are tracked in their respective local
configuration/report categories. `.eil` state, user uploads, accounts, sessions,
private logs, environment secrets, model files and local reports are excluded.
The licensed Voron snapshots and full upstream notices remain unchanged.

GitHub authentication was verified as `RichiiiTV` using Git Credential Manager;
credential material was neither printed nor saved to the project. Publication is
an ordinary first push, without force-updating an existing remote history.

## Unchanged limits

Offline test success does not resolve the failed real Voron controller-question
pilot or the earlier M5 quality failures. Hosted validation remains deferred.
No new real-model evaluation, paid provider invocation, equipment access or
production deployment was performed. CI execution on GitHub is separate from
the local results above and must be checked after the push.
