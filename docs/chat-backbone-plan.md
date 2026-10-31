# Admin knowledge ingestion and automatic problem chat

Authorized clarification: 2026-10-30. The admin uploads machine data; the backbone
sorts it automatically. A regular user describes a problem in one chat box and
may add images/error logs. Machine/source/notebook management is not a user task.

1. **Admin catalog:** reuse bounded ingestion; extract evidence-backed machine
   identity/profile through a local structured LLM call, compare local embeddings,
   then atomically publish into an automatic machine group. Unknown identities
   stay explicitly unidentified. Admin can inspect/archive exceptional assignments
   and supply corrected source editions without changing existing snapshots.
2. **Problem chat:** owner-scoped conversations and attachments, frozen published
   catalog snapshots, automatic local machine retrieval, bounded follow-up context
   and existing Deep Agents/LangGraph run budgets. Ambiguity produces a short
   clarification in chat. Images use local vision; error logs use line citations.
3. **Simple interface and validation:** one user composer with optional files,
   administrator-only ingestion/review controls, safe source navigation, isolation,
   malformed-file/uncertain-match tests, live local-model/browser checks, verified
   backup and local app restart.

New admin uploads are explicitly published to active accounts in this one local
workspace. Existing owner-private documents are not migrated into the catalog.
Problem attachments remain private to their conversation owner. Catalog creation,
management and publication are not agent tools. The agent cannot execute code,
write to equipment, expand budgets or send machine context to Siemens. Public
Siemens lookup retains its separate human-authored public-query boundary.

Acceptance: two admin files about the same evidenced machine are automatically
grouped without machine selection; another machine stays separate; a member can
ask a matching question and receive cited evidence; ambiguous matches ask a chat
clarification; new uploads cannot enter an existing run; another user cannot read
problem attachments/history; regular users cannot upload/publish machine knowledge;
image/log input never invokes synthetic inspection tools or external services.

Implemented and locally validated on 2026-10-30. See [results and operator
workflow](chat-backbone.md): 254 backend tests, 41 frontend tests, real automatic
classification, private problem chat/vision and verified backup/restore. Stop after
reporting; hosted validation and production deployment remain out of scope.
