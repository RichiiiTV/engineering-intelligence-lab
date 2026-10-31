# German UI and automatic public PLC diagnostics

The subsequent [language selector](languages.md) adds runtime Deutsch/English
switching. German remains the default; new answers use the selected language.

Implemented and locally validated on 2026-10-31 following the user's request to
test ordinary problem chat with automatic Siemens MCP routing and German operation.

## Normal chat

> Meine Maschine XY mit Siemens S7-1500 zeigt den Fehlercode 16#80A1. Was soll ich prüfen?

The backend recognizes the current human-entered public PLC family and diagnostic
identifier and binds a fixed German query to the existing no-argument Siemens tool.
There is no separate search page, toggle or `/siemens` command to learn for this case.
Local machine knowledge and problem logs remain available to the investigation;
unmatched machine identity is never treated as a confirmed machine match.

Automatic recognition is bounded: S7-1200, S7-1200 G2 or S7-1500 plus one to three
explicitly typed four-digit hexadecimal diagnostic codes (`16#80A1`, `0x80A1`, or
`Statuscode 80A1`) or diagnostic OB identifiers (80/82/83/85/86/87/121/122).
It does not interpret a generic machine alarm such as `E17` as a Siemens diagnostic.
Missing/ambiguous identifiers require a chat question; other product families and
free-form public searches can still use `/siemens`.

Only normalized identifiers and fixed template words leave the installation.
Machine names, free-form problem text, code, attachments, image observations,
catalog profiles and earlier conversation are excluded. An image or log alone
cannot initiate an external search: the user must type the public PLC family/code
in chat. No model can synthesize or extend the outbound query. The composer
discloses this boundary; `nur lokal` or an explicit external-search opt-out suppresses
automatic lookup. `/siemens` still sends the separately human-authored public question.

The bounded lookup is persisted once per run; duplicate submissions reuse the run,
tool retries reuse the observation, and interrupted unknown outcomes are never
silently resent. Existing tool/model/token/time limits, ownership and audit records
apply. “Was an Siemens gesendet wurde” shows the exact saved query and origin.

## German operation

German is the default for chat, login/account controls, administration, document
sources, storage controls, legacy notebooks and Advanced. Dates/numbers use `de-DE`;
the page and readable report declare German. Model instructions require German
answers and clarifications. Deterministic machine clarification, API error guidance,
statuses and Siemens outage/compatibility notices are localized. German safety-role
terms and image-reading questions are included in the existing bounded checks.

Original document quotations, code, filenames, error identifiers, vendor titles,
technical audit/API identifiers and previous answers are preserved verbatim.
Localization does not translate evidence or retroactively rewrite histories.

## Validation

- `.venv\Scripts\python.exe -m pytest -q`: **276 passed in 210.77 seconds**.
- In `frontend`, `npm test -- --reporter=dot`: **42 passed**; `npm run build` passed.
- Ruff check/format and whitespace checks passed; no dependencies were added.
- Acceptance checks exercise ordinary German questions, canonical-only query
  construction, ambiguous/generic alarms, hex-looking secrets, opt-out, private logs/history exclusion,
  a graph-required lookup, one-call caching, German safety terms and an unavailable
  lookup displayed even when no reference links exist.
- Real local Ollama + Siemens MCP: a generated German question with a private-name
  marker and synthetic log completed with **one external lookup, five references,
  five model calls, four tool calls and 14,892 tokens**. The exact query excluded
  the machine-name marker, log marker, filename and log alarm field. Duplicate
  submission reused the same run. The answer was German.
- Browser review confirmed the German member chat, inline sources, exact outbound
  query disclosure, owner-isolated history and German admin upload controls.
- The existing local workspace was idle before restart; its updated app returned
  HTTP 200 and functional readiness passed. No operator account or source was changed.

The live search returned general product/marketing pages, not evidence establishing
the test error code's meaning. The answer explicitly withheld that diagnosis and
asked for the exact CPU model. This validates routing and boundaries, not engineering
answer quality or exhaustive diagnostic coverage. Search titles/snippets are untrusted
public references; complete manuals are not fetched and verified. Earlier M5 quality
failures and deferred hosted validation remain. No real internal corpus, production
deployment or equipment connection was used.

Ignored local evidence: `reports/german-full-backend.log`, `german-frontend-tests.log`,
`german-live-result.json`, `german-siemens-proof.png` and `reports/chat-live-state/`.
