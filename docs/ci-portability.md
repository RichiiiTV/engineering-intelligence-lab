# CI portability correction

The first public acceptance run on 2026-11-01 exposed checkout portability errors
that were hidden by the existing Windows working tree. The
[original run](https://github.com/RichiiiTV/engineering-intelligence-lab/actions/runs/41296533469)
failed two Ubuntu tests and five Windows tests; the dependency-advisory job passed.

## Causes and corrections

- **Extended benchmark CSVs:** their reviewed hashes authenticate LF bytes, but
  the v2 pack lacked Git line-ending attributes. Windows checkouts converted them
  to CRLF. The v2 CSV/JSON files now have explicit LF attributes. Their fixture
  content and pinned source hashes are unchanged.
- **Knowledge benchmark manifest:** the existing pin authenticates the original
  CRLF manifest (`fa6aba30f19a35b5318d1e2be3d43355fef12672ad831b4c5ce1472b694f995b`).
  The old local working file matched that pin, while Git stored normalized LF
  bytes (`089edc5b250bf6ddfa7fc91ebfa7574d92bfa4335501a06a907823ecb04c96dc`).
  The repository blob now retains the reviewed CRLF bytes, with text conversion
  disabled for this one file. Its logical content, source hashes, cases and
  original pinned hash remain unchanged. Whitespace checks explicitly recognize
  CRLF while retaining the usual whitespace rules. The trusted fixture generator
  now writes those exact original newline bytes on every operating system.
- **Host-file rejection test:** a real host path must be rejected on every OS,
  but the diagnostic differs for Windows and POSIX paths. The test now selects
  the expected error from the actual path form and also checks a fixed POSIX
  absolute path. Error status and the host-filesystem isolation boundary remain
  required; no agent permissions were changed.

The generator regression runs a trusted copy in a temporary directory, verifies
the unchanged manifest pin and checks every generated source hash. It never
executes the intentionally invalid uploaded-code fixture. The existing failure
test still requires rejection when a manifest byte is changed.

## Local acceptance

The staged index was exported into two new ignored directories using
`git -c core.autocrlf=false checkout-index --all` and the corresponding `true`
setting. Tests imported application code from each fresh export rather than the
original editable installation.

- Targeted portability/integrity suite: **11 passed** in the original workspace.
- Same suite in fresh LF export: **11 passed**.
- Same suite in fresh CRLF export: **11 passed**.
- Ruff lint and format checks: passed; 85 application/test files formatted.
- Staged manifest bytes match the existing reviewed SHA-256; staged whitespace
  validation passed.

The unchanged full Windows/Ubuntu CI matrix, frontend checks, offline benchmark
commands and dependency audits remain enabled. Their remote results are visible
in the [acceptance workflow](https://github.com/RichiiiTV/engineering-intelligence-lab/actions/workflows/ci.yml).
No check was skipped or relaxed to accommodate a failed fixture hash. No runtime
API, model configuration, dependency version, private workspace or evaluation
quality baseline was changed.
