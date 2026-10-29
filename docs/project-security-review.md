# Project gaps, security review and Siemens SPS connection

This is the original review snapshot. The user subsequently authorized fixing
the findings. See [remediation results](gap-remediation-results.md) and the
[operator guide](security-operations.md) for current behavior and validation.

Reviewed 2026-10-29, after M5. This is a code/configuration review, dependency
audit, failure-case testing and a real public MCP integration check. It is not
a penetration-test certification or approval for production equipment use.

## Outcome

The strongest parts are deterministic CSV calculations, case/source snapshots,
read-only graph tools, durable checkpoints, cumulative budgets, content-bound
draft approval and auditable evidence exports. The application remains a local
single-user prototype. M5 software tests pass, but its live model-quality gate
remains failed. A public Siemens search connection improves access to reference
material; it does not resolve those reliability or deployment gaps.

## Security issues addressed

| Finding | Previous behavior / risk | Change and verification |
|---|---|---|
| High: missing Host validation | Loopback binding and an Origin check derived from the request host did not stop DNS rebinding. An attacker-controlled Host and matching Origin could pass the old checks. | Outermost TrustedHost middleware accepts only localhost/loopback hosts. Live adversarial Host returned 400; tests cover reads and writes before handlers/body parsing. |
| Medium: body limits covered uploads only | Oversized JSON could be read into memory before field validation. | Mutating API bodies are admitted before parsing: 128 KiB for JSON, existing 10 MiB + bounded multipart overhead for uploads. Chunked upload limits remain tested. |
| Browser-origin checks only covered mutations | API reads lacked the same explicit origin check. | API reads/writes reject unrelated origins; cross-site Fetch Metadata is rejected. Live unrelated Origin returned 403. Native local clients and the existing Vite development origin remain supported. |
| Vulnerable frontend development dependencies | npm reported three affected package entries: Vitest, @vitest/mocker and tinypool, including critical worker-related advisories. These are test/development dependencies, not bundled application code. | Upgraded Vitest 3.2.7 to 5.0.5 on compatible Node 24/Vite 7.3.7. Final npm audit: zero reported vulnerabilities. All frontend tests/build pass. |

The dependency upgrade follows the [official Vitest migration requirements](https://vitest.dev/guide/migration/)
and publisher advisories for [mock path traversal](https://github.com/vitest-dev/vitest/security/advisories/GHSA-82fw-gwwq-j7x9)
and [worker option pollution](https://github.com/tinylibs/tinypool/security/advisories/GHSA-85c8-ppgw-ccpr).
Advisory severity is not proof that the shipped local UI was remotely exploitable.

Python package metadata was checked with `pip-audit --path .venv/Lib/site-packages
--skip-editable`: no known vulnerabilities were reported. This excludes the
unpublished editable project, native drivers, Windows, Ollama and unreported
vulnerabilities. Exact scan outputs are retained locally in ignored
`reports/security-review/`.

Bandit reported seven low-severity findings around fixed trusted benchmark
subprocess commands and one medium SQL-construction finding. The SQL expression
constructs only a number of `?` placeholders; source/case IDs and FTS terms are
bound parameters, not interpolated user SQL. No arbitrary agent shell or Python
execution was found. Those scan findings were reviewed rather than reported as
confirmed command/SQL injection.

## Remaining gaps, in priority order

| Priority | Gap | Next concrete step |
|---|---|---|
| P1 | Live M5 quality gate: 0/6 Ollama attempts passed all checks. Formatting, calibration, virtual-file misuse and output truncation remain. | Improve the single-agent evidence workflow against the frozen cases and retain regression gates. Do not promote delegation based on this sample. |
| P1 before network use | No authentication, tenant authorization or authenticated reviewer identity. UUID case isolation is not access control. Any trusted local process can use the API. | Keep loopback-only. Add identity, authorization and authenticated approvals before shared/network deployment. |
| P1 before untrusted/private PDFs | Docling runs in a killable process with offline settings, but not an OS security sandbox or hard memory quota. | Add low-privilege/container isolation, memory/CPU quotas and OS-level egress restrictions before accepting sensitive or hostile inputs. |
| P2 | No global disk/event retention, deletion/backup lifecycle or global upload quota across unlimited cases. | Define retention and recoverable deletion, bound global storage and implement backup/restore validation. Per-case limits alone do not bound the installation. |
| P2 | Unexpected provider usage can be underreported: `RunStore.settle_tokens` rejects usage above a reservation before recording the overage. The run stops, but recorded tokens stay at the reservation. | Record actual over-envelope usage and a failed-budget event atomically, stop further calls, and preserve that overage on resume/export. This was reproduced with a synthetic local one-token overage; no paid call was made. |
| P2 | Evidence exports check citation identity/location, not whether arbitrary claims follow. Lexical search can miss a relevant passage. | Add claim-to-source/contradiction tests and broader ambiguous/negative cases; preserve the existing uncertainty labels. |
| P2 | Siemens search coverage is uneven and not specialized to CPU/firmware/TIA versions. General queries can return product/marketing pages; one German manual query returned no AI-search results. | Add vetted SPS question/manual benchmarks and version-aware retrieval before relying on generated answers for engineering decisions. Never invent missing manuals or citations. |
| P2 | M5 uses three narrow synthetic cases and one live repetition per mode. Hosted comparison remains unrun. | Broaden/repeat evaluations and configure an explicit hosted model/key outside the repository if that comparison is required. |
| P2 | The simple UI finds runs from a global latest-50 list. Older cases can open without their latest result. | Fetch the selected case's own investigation list and introduce pagination for cases/history. |
| P3 | No checked-in continuous-integration workflow or automated dependency-update policy. | Put offline tests/build/calibration gates and dependency auditing in the repository's chosen CI system. Live provider tests should be explicit and budgeted. |

No sensitive data, credentials, live plant connections, production APIs or PLC
writes were introduced. The uploaded-data category confirmation remains a user
declaration, not proof of document licensing or automatic detection of secrets.

## Siemens MCP integration

The real SDK successfully initialized the public endpoint
`https://mcp.siemens.com/mcp`; the server identified itself as
`siemens-mcp-server`, version `2026-03-30`, and listed eight tools. The app
exposes only the reviewed `siemens_search` query contract. No packaged Siemens
plugin was returned by the available plugin search; the project uses its
existing MCP Python SDK directly.

The [Siemens MCP documentation](https://mcp.siemens.com/docs) describes this public
search service. Siemens also documents a separate
[Xcelerator Developer Portal MCP endpoint](https://developer.siemens.com/ai-registry/developer-portal/developer-portal-mcp.html);
that API/developer-focused endpoint was not selected for this integration.

Open `http://127.0.0.1:8000/?page=siemens` or choose **SPS help** in the normal
workbench. Type a public product question and click **Search Siemens**. The
disclosure identifies the external destination. Only the submitted question is
included in tool arguments; standard MCP initialization metadata is also sent.
Case identifiers, files, history, agent output and credentials are never attached.
Nothing runs when an example question is selected until Search is clicked.

Controls implemented in `siemens_mcp.py`:

- Fixed HTTPS endpoint and POST transport; no arbitrary URLs, shell commands,
  environment-proxy inheritance, redirects, retries or REST fallback.
- Real MCP initialization/catalog/call flow. Schema drift prevents tool dispatch.
  Remote instructions, annotations and extra tools do not authorize capabilities.
- One search at a time, two-second minimum interval, 500-character question,
  25-second overall deadline, and 256 KiB uncompressed JSON response cap before
  parsing. SSE/encoded responses are rejected for this JSON-only endpoint.
- Bounded text and eight deduplicated HTTPS Siemens-domain links at most. Invalid
  links and job listings are excluded. Linked pages are not fetched automatically.
- Server and browser URL checks; plain React text rendering; safe external-link
  attributes; no HTML/Markdown execution. Summaries are labeled Siemens-generated
  and unverified. Results are kept in page memory, separate from case evidence.
- The investigation agent receives no new network tool. A malicious PDF cannot
  trigger a Siemens query or select its content. Search does not start Ollama,
  bypass M2 budgets, save a draft, access a PLC or change a production system.

The first live adapter search returned eight eligible Siemens links in about
4.6 seconds. A subsequent real browser search visibly returned the question,
Siemens summary, timestamp and source links. Those results demonstrate connection
and rendering, not correctness of the generated engineering summary or retrieval
of the exact OB1 programming manual.

## Validation

- `uv run pytest -q`: **167 passed in 130.59 seconds**.
- `npm.cmd test`: **20 passed** on Vitest 5.0.5.
- `npm.cmd run build`: TypeScript and Vite production build passed.
- Ruff check/format: passed; frontend Prettier applied to changed files.
- Python advisory audit: no known vulnerabilities reported. Final npm audit: zero.
- Failure cases: invalid Host/Origin, cross-site requests, oversized bodies,
  forged tool schemas, unsafe URLs, mismatched questions, upstream errors,
  redirects, compressed/oversized/SSE responses, concurrency and timeout bounds,
  untrusted HTML, outage and no-result UI states.
- Live loopback API: root HTTP 200, Siemens catalog available, invalid Host 400,
  unrelated Origin 403. The idle server was restarted with the reviewed code.
- Browser: explicit question submission, real MCP response, source links and
  layout inspected. Screenshot retained in
  `reports/security-review/siemens-help.png`.

The public Siemens connection is working. Production suitability and model
quality remain open as documented above.
