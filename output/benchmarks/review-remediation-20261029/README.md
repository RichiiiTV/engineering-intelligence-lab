# Review remediation evidence

Recorded 2026-10-29. See [results](../../../docs/gap-remediation-results.md).

- `final-v1`: 12 live Ollama rows, two repetitions of three original cases in
  single/delegated modes. All passed.
- `final-v2`: eight live single-agent rows, two repetitions of four additional
  negative/conflicting cases. All passed.
- `offline-final-v1` / `offline-final-v2`: 12/16 scripted calibration rows in both
  graph modes. Calibration is software validation, not model-quality evidence.
- The other directories retain intermediate scorecards and per-row scores,
  including failures. Their full local state/observations are retained under
  ignored `reports/gap-remediation/`; intermediate source snapshots are not
  represented as fully reproducible releases.
- Final directories include every row's `run.json`, `trace.json`, `score.json`
  and `evidence.json`. Only generated/public demo evidence is included. No live
  workspace databases, credentials, sessions or private uploads are archived.
- `pdf-isolation.json` is the real worker resource/privilege probe;
  `siemens-connection.json` records public query/connection metadata without
  copying upstream summaries/pages; `advisories.json` records advisory totals.
- `hashes.json` identifies artifact files. Expected answers were used by scorers
  only. Runtime typed feedback uses actual tool observations.

The live gate measures the guarded workflow, including deterministic numeric
and citation checks plus budgeted model corrections. It does not certify general
language entailment, arbitrary engineering answers or production safety. The
original failed M5 baseline remains unchanged. Hosted validation was left
pending by the user; no paid call was made.
