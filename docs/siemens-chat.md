# Siemens documentation inside the normal conversation

Implemented at the user's request on 2026-10-29. Siemens lookup is part of the
normal question/answer flow; the main navigation no longer sends people to a
separate SPS search page.

## Usage

1. Type a public Siemens, SIMATIC, S7, SPS/PLC, OB or TIA Portal question in the
   normal question box. Documentation lookup is selected visibly. No upload is
   required. It can be switched off before submitting.
2. Optionally specify public CPU, firmware and TIA version fields, then **Ask**.
   The regular Ollama agent calls Siemens through its graph tool and returns an
   answer in the same results view.
3. Cited references and reviewed manual candidates appear below the answer.
   Other search results are collapsed. **What was sent to Siemens** shows the
   exact outbound query. The report download preserves the references.
4. **My investigations** includes standalone questions as well as file cases,
   with pagination. **Ask another question** returns to the same normal composer.

With files attached, external lookup starts off. Enable Siemens documentation
and enter a separate public product question in the composer. The investigation
question/file contents may remain local. A document or model cannot construct
the external query. This is one conversation flow with an explicit data boundary.

Old `/?page=siemens` links open the normal composer. The protocol diagnostic
page is retained only at `/?view=advanced&page=siemens`; Advanced workspace and
the existing file-investigation/draft-approval tools remain available.

## Implementation and boundaries

- The existing authenticated `/api/investigations` queue accepts a bounded
  `siemens` public-query object and standalone `chat_mode`. No provider, MCP URL,
  tool catalog or arbitrary network request is accepted from the client/model.
- `read_siemens_reference()` has no model-controlled arguments. It is closed over
  the human's stored public query and optional product fields. It reuses the
  reviewed MCP SDK transport at `https://mcp.siemens.com/mcp` and only the
  `siemens_search` remote tool. No case ID, file text, history, credentials or
  model-generated query is sent in its arguments.
- Model/tool calls, time, tokens, checkpoints, pause/cancel and ownership use
  the existing cumulative run limits. A required lookup cannot be skipped
  silently by a premature final answer. A single citation reminder, if needed,
  goes through the same metered graph; it does not repeat the search.
- One external search is reserved durably per run before dispatch. Repeated
  calls and checkpoint recovery reuse the saved observation. A killed lookup
  with unknown external outcome is not resent automatically. Outages are saved
  once and can still expose reviewed local manual candidates.
- The existing 500-character combined query, 25-second MCP deadline, response
  byte cap, fixed transport, schema checks and checked HTTPS source hosts remain.
- Public reference IDs/URLs and query provenance are exported separately from
  immutable case evidence. The model receives compact title/excerpt/ID data;
  the browser renders the independently checked URLs. Unknown citations are
  flagged. HTML and unsafe URLs are not executed/rendered as active content.
- When reviewed manual candidates match, the model receives those candidates
  ahead of remote search references. Upstream AI summaries stay in the audit
  snapshot, outside the model observation. Manual contents are not fetched and
  technical claims remain unverified. Hyphenated terms such as `cycle-time`
  match the reviewed manual index.
- Standalone questions have no demo inspection tools or implicit CSV dataset.
  Existing file cases, legacy demo API behavior and historical run data remain
  compatible. No production device or PLC connection was added.

Siemens search summaries are unverified. A manual title or excerpt does not
prove facts absent from that excerpt, or compatibility with an exact CPU or
firmware. Users must check the linked document's validity section. Hosted model
validation remains pending under the user's earlier instruction; this feature
uses the local Ollama default.

The tool follows the documented
[Deep Agents extension point](https://docs.langchain.com/oss/python/deepagents/customization)
and [typed LangChain tool contract](https://docs.langchain.com/oss/python/langchain/tools).
The existing harness performs tool calling; no replacement tool loop was added.

## Validation

- `uv run pytest -q`: **204 passed in 155.77 seconds**.
- `npm.cmd test`: **29 passed**; TypeScript/Vite production build passed.
- Ruff checks/format passed; lockfile dependencies are unchanged.
- Real graph tests cover standalone and file-backed questions, immutable public
  query binding despite injected/private case text, no filesystem/demo tools in
  standalone chat, skipped-lookup enforcement, metered citation correction,
  cache/recovery, unknown interrupted outcomes, budget refusal before network,
  outage/manual fallback, payload validation and cross-account export denial.
- UI tests cover automatic detection/opt-out, no upload requirement, inline
  answers/references, private file question vs public query, saved standalone
  history, legacy route behavior and safe downloaded links.
- A real local Ollama + Siemens run completed using **two model calls, one tool
  call and 2,471 reported tokens**, returning eight reference links and no
  unresolved external citation IDs. State was isolated generated test state.
- Browser validation submitted public S7-1200 and S7-1500 questions through the
  normal input. The final hyphenated cycle-time question completed with **two
  model calls, one tool call and 1,810 reported tokens**, citing the reviewed
  cycle/response-time manual and explaining CPU/firmware validity checks. The
  connection was verified and no citation IDs were unresolved. No real workspace
  credentials or files were used for those test mutations.

Local detailed observations, test output and screenshots are in ignored
`reports/siemens-chat/`. The actual workspace remains at
`http://127.0.0.1:8000/`, with its account setup and existing cases preserved.
