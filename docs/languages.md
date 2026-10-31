# Deutsch / English

Implemented and locally validated on 2026-10-31.

Use **Sprache / Language** at the top of the page, before or after sign-in. Choose
Deutsch or English. The choice updates chat, administration, sources, account
controls and Advanced immediately, without clearing a draft question or its files.
It is saved in this browser (`eil-language-v1`) and restored after reloading.
German remains the default. When browser storage is disabled, switching still works
for the current page; the preference cannot survive a reload.

The selected language applies to **new answers**. Each investigation freezes `de`
or `en` when submitted, including normal chat, notebooks and Advanced. Switching
while an answer runs changes presentation only. It does not regenerate that answer,
reset budgets or change its saved language. New follow-ups use the new preference.
Request fingerprints include the language; retries cannot accidentally reuse a run
with a different language. Older German receipts remain retryable.

Existing answers, source quotations, uploaded text/code, error codes, machine names,
filenames and vendor titles stay unchanged. Only authored interface text and known
application notices are translated. There is no remote translation service and no
additional model call on a language switch. Dates and numbers follow the selection;
readable report headings follow it while the answer and evidence remain original.

The backend validates both language values. Public Siemens diagnostic queries use
a fixed German or English template with the same canonical-only boundary. Language
selection never permits private content, history or model output in that query.

## Validation

- `.venv\Scripts\python.exe -m pytest -q`: **281 passed in 241.56 seconds**.
- In `frontend`, `npm test -- --reporter=dot`: **46 passed**; `npm run build` passed.
- Ruff check/format, whitespace checks and `uv lock --check` passed. No dependencies
  were added. The preference uses React's documented
  [external-store subscription](https://react.dev/reference/react/useSyncExternalStore).
- New checks cover switching without remounting the draft or losing files, saved
  preferences, pre-login selection, unchanged original answers, escaped English
  report output, invalid language rejection, language-bound retry identity, legacy
  receipts, frozen budgets on resume, English machine clarification and canonical
  English Siemens query construction.
- Real browser/Ollama check using generated XR7 knowledge: an English question
  completed with **3 model calls, 1 tool call and 7,173 tokens**, with exact manual/
  code citations. Switching the interface to German during generation left the
  response language English. Switching back to English and reloading retained
  the preference and the same answer. No Siemens request was made for this local
  question; the earlier live MCP result is recorded in `german-siemens-routing.md`.

This is language/workflow validation, not a general engineering-quality guarantee.
Earlier quality limits and deferred hosted validation remain unchanged.

Ignored local evidence: `reports/language-full-backend.log`, `language-frontend.log`,
`language-live-result.json`, `language-switch-proof.png` and the generated QA state.
