# Simpler user experience — approved M4 refinement

The user approved the GPT Image mockups in `output/design/simple-user-flow-v1/` on
2026-10-29. This refines M4's presentation; it does not begin M5 or change the agent/runtime.

## User flow

- `/` is the simple entry point: attach CSV/PDF files, enter a question, and click Investigate.
  The app creates the underlying case automatically; no separate case-name or model form is required.
- The generated demo fixtures can be loaded with one explicit action. Other uploads retain the
  synthetic/licensed-public category and explicit confirmation before they are sent to the API.
- Preparation shows which file is being added. A failed preparation keeps successful uploads;
  retry uses the same case and compares SHA-256 content hashes to recover lost upload responses.
  Matching filenames alone are never treated as matching evidence.
- The running view uses plain-language status plus pause/cancel/resume controls. It does not show
  fake progress percentages, tool names, token counters or UUIDs by default.
- Completed results lead with deterministic per-CSV findings and a before/incident comparison.
  Each file is calculated separately, from the selected run's frozen source list. Later case
  uploads do not silently change the displayed finding. Multiple CSVs have an explicit file selector.
- Source rows and PDF excerpts open in a small evidence dialog. Related excerpts come from actual
  returned citations, not hardcoded maintenance text from the mockup. Model notes remain separate
  from calculated rates, with source-reference warnings and a clear uncertainty statement.
- Download report produces an escaped, script-free, readable HTML artifact. It contains the
  original model answer, source references, uncertainty and full evidence/calculation record, and
  can be printed or saved as PDF from the browser. Download does not save or approve a server draft.
- My investigations and Ask another question reuse the existing case/run APIs. A new question
  starts a new bounded run; it does not silently extend a previous conversation or reset its budgets.

## Advanced workspace

The original M4 interface is preserved in `frontend/src/AdvancedApp.tsx` and is available at
`/?view=advanced`. Its case navigation retains the mode parameter. Simple view returns to the
same selected case/run. Tool activity, budgets, complete provenance, JSON exports, mock MCP
opt-in and explicit report-draft approval remain there. This is a presentation switch, not
authenticated admin access or a new permission boundary.

New simple runs use existing server defaults with the already-supported 2,048 output-token
allowance; mock MCP remains off. No backend endpoint, model loop, evidence policy, checkpoint,
approval transaction or dependency was changed. `@types/node` was added only for frontend tests
that use real WebCrypto hashing.

## Validation

Commands from `frontend/`:

```powershell
npm.cmd test
npm.cmd run build
npx.cmd prettier --check src package.json tsconfig.json vite.config.ts index.html
```

The suite includes the original advanced-workspace tests and new checks for the simple entry
point, automatic case creation, category confirmation, upload failure/retry, content-based
recovery, run/source snapshot isolation, foreign-case rejection, controlled run failure,
untrusted-text rendering and safe readable exports. A different station (S04) is used in the
new fixtures to guard against copying the S03 mockup into the implementation.

Final results: **16 frontend tests passed**; TypeScript/production build and Prettier checks
passed. The original backend code and endpoints were unchanged. Its 111-test M4 baseline is
documented in `m4-results.md`; this refinement exercised the backend through the live UI.

Live browser acceptance used the existing loopback API and actual local Docling/Ollama:

- Loaded both generated demo files, asked a question, and started with the single Investigate action.
- Automatically created case `dc360dd8-4724-4425-868f-492e575de1cd` and completed run
  `f1795018-3844-4089-88b0-0fd7c77d48e3`.
- The run used 4 model calls, 4 tool calls, 16,708 charged tokens and 48.110 seconds active time;
  mock MCP was off. The displayed deterministic result was S03, 1.61% to 14.11%, +12.50 pp.
- PDF page excerpts and source rows were presented as evidence rather than causal proof.
- Downloaded the 49,210-byte readable HTML report and checked that it contained the comparison,
  S03/source evidence and a CSP, with no executable script element.
- Verified that advanced case navigation keeps advanced mode, and Simple view returns to the
  same case/run. Checked the mobile results layout at a 390-pixel viewport with no horizontal
  document overflow, then restored the normal viewport.
- Starting a fresh investigation clears the previous case's form attachments; a regression
  test covers the stale-detail transition discovered during mobile navigation checks.

This remains a single-user loopback demo, with the model and native-parser limitations
documented in the M3/M4 reports. No production deployment or M5 work was performed.
