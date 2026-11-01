# Public repository privacy

The user authorized removal of personal identity details from the published Git
history on 2026-11-01. A verified complete local Git bundle was made before any
rewrite and remains in the ignored local audit directory. It contains original
identities/artifacts and must never be uploaded. Runtime workspaces, conversations,
attachments, accounts, credentials and local audit files remain excluded from Git.

## Scope

- Remove unrelated project background from the current README and repository
  instructions.
- Use generic paths in environment examples and fictional identifiers in owned
  synthetic test material. The edited injection PDF is visually verified, with
  passages recaptured by local offline Docling rather than invented provenance.
- Rewrite author/committer identity to the public repository account handle and
  its GitHub no-reply email. Personal email addresses and local account labels
  are removed from reachable public history, including compressed PDF content.
- Preserve historical evaluation outcomes. Redacted evidence exports are labelled
  derivatives; the public injection fixture has its own declared revision and
  new hashes. No recorded real-model failure was turned into a pass or rescored.
- Keep the licensed Voron sources and attribution unchanged. Public upstream
  author/contact attribution is distinct from private operator information.

## Publication check

Run `uv run python -m eil.publication --history` before publishing. CI fetches
complete history and runs this check on Windows and Ubuntu. It reports file paths
and finding categories, never the matching personal value or credential.

The bounded check covers tracked text, no-reply commit identities, personal home
paths, credential patterns, image EXIF and decoded streams in the owned PDF
fixtures. It includes regression tests for unsafe paths/emails, encoded PDF text,
safe API routes, legitimate public attribution and binary false positives.
Licensed upstream contact information is allowed in explicitly published public
machine packs; that does not exempt secrets or private workstation paths.

This is a pattern/metadata gate, not a semantic guarantee about arbitrary future
documents or images. Review uploads and visible screenshot contents before
committing them. No account or source content from the runtime `.eil` directory
belongs in this public repository.

## Working with rewritten history

Commit IDs change during the approved scrub. Fetch the cleaned `main` into a fresh
branch or make a fresh clone; do not merge an old unsanitized branch back into it.
Never push all local backup refs. The private bundle is for local recovery only.
Force-updating the reachable branch cannot erase existing third-party clones,
GitHub cached commit views, past workflow logs or copies already downloaded.
Those may require separate provider support or cleanup.
