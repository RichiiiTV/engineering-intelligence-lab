"""The normal-user workflow: one problem chat, with backend-managed context."""

import hashlib
import json
import threading
import uuid

from .evidence import EvidenceConflict, EvidenceNotFound, EvidenceStore
from .problem_sources import ProblemStore
from .runs import RunStore, now

LOCK = threading.RLock()


class ChatStore:
    def __init__(self, directory):
        self.directory = directory
        self.evidence = EvidenceStore(directory)
        self.problems = ProblemStore(directory)
        self.runs = RunStore(directory)
        with self.evidence.connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS chat_conversations(id TEXT PRIMARY KEY,owner_id TEXT NOT NULL,document TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS chat_receipts(owner_id TEXT NOT NULL,request_id TEXT NOT NULL,document TEXT NOT NULL,PRIMARY KEY(owner_id,request_id));
            """)

    def get(self, identity, owner):
        with self.evidence.connection() as conn:
            row = conn.execute(
                "SELECT document FROM chat_conversations WHERE id=? AND owner_id=?",
                (identity, owner),
            ).fetchone()
        if not row:
            raise EvidenceNotFound("Conversation not found")
        return json.loads(row[0])

    def list(self, owner):
        with self.evidence.connection() as conn:
            return [
                json.loads(r[0])
                for r in conn.execute(
                    "SELECT document FROM chat_conversations WHERE owner_id=? ORDER BY rowid DESC LIMIT 100",
                    (owner,),
                )
            ]

    def turns(self, identity, owner):
        self.get(identity, owner)
        with self.runs.connection() as conn:
            return [
                json.loads(r[0])
                for r in conn.execute(
                    "SELECT document FROM runs WHERE json_extract(document,'$.chat_context.id')=? AND json_extract(document,'$.owner_id')=? ORDER BY created_at,id",
                    (identity, owner),
                )
            ]

    def submit(
        self,
        owner,
        question,
        request_id,
        service,
        parsed=(),
        conversation_id=None,
        *,
        language="de",
    ):
        if language not in {"de", "en"}:
            raise ValueError("Choose de or en")
        if not question.strip() or len(question) > 4000:
            raise ValueError("Describe the problem in 1–4,000 characters")
        fingerprint = hashlib.sha256(
            json.dumps(
                {
                    "question": question,
                    "language": language,
                    "conversation_id": conversation_id,
                    "files": [(p[0]["filename"], p[0]["sha256"]) for p in parsed],
                },
                sort_keys=True,
            ).encode()
        ).hexdigest()
        with LOCK:
            with self.evidence.connection() as conn:
                row = conn.execute(
                    "SELECT document FROM chat_receipts WHERE owner_id=? AND request_id=?",
                    (owner, request_id),
                ).fetchone()
            receipt = json.loads(row[0]) if row else None
            if receipt:
                if "language" not in receipt and language == "de":
                    # Receipts predating the preference stored the same payload
                    # without a language field. Reuse them without duplicating work.
                    fingerprint = hashlib.sha256(
                        json.dumps(
                            {
                                "question": question,
                                "conversation_id": conversation_id,
                                "files": [(p[0]["filename"], p[0]["sha256"]) for p in parsed],
                            },
                            sort_keys=True,
                        ).encode()
                    ).hexdigest()
                if receipt["fingerprint"] != fingerprint:
                    raise EvidenceConflict(
                        "This submission ID belongs to another problem or attachment set"
                    )
                conversation_id = receipt["conversation_id"]
            elif conversation_id:
                self.get(conversation_id, owner)
            else:
                conversation_id = str(uuid.uuid4())
            with self.runs.connection() as conn:
                existing = conn.execute(
                    "SELECT document FROM runs WHERE json_extract(document,'$.chat_context.request_id')=? AND json_extract(document,'$.owner_id')=?",
                    (request_id, owner),
                ).fetchone()
            if existing:
                return json.loads(existing[0])
            previous = (
                self.turns(conversation_id, owner)
                if receipt or self._exists(conversation_id, owner)
                else []
            )
            if len(previous) >= 100:
                raise EvidenceConflict("Conversation limit reached (100 answers); start a new chat")
            if any(r["status"] in {"queued", "running"} for r in previous):
                raise EvidenceConflict("Wait for the current answer before adding a follow-up")
            if not receipt:
                with self.evidence.connection() as conn:
                    conn.execute("BEGIN IMMEDIATE")
                    if conn.execute("SELECT count(*) FROM chat_receipts").fetchone()[0] >= 5000:
                        raise EvidenceConflict("Chat submission storage limit reached")
                    if not conn.execute(
                        "SELECT 1 FROM chat_conversations WHERE id=?", (conversation_id,)
                    ).fetchone():
                        if (
                            conn.execute(
                                "SELECT count(*) FROM chat_conversations WHERE owner_id=?", (owner,)
                            ).fetchone()[0]
                            >= 100
                        ):
                            raise EvidenceConflict("Conversation limit reached (100 per account)")
                        meta = {"id": conversation_id, "title": question[:80], "created_at": now()}
                        conn.execute(
                            "INSERT INTO chat_conversations VALUES(?,?,?)",
                            (conversation_id, owner, json.dumps(meta)),
                        )
                    self.problems.add(conn, conversation_id, owner, parsed)
                    receipt = {
                        "language": language,
                        "fingerprint": fingerprint,
                        "conversation_id": conversation_id,
                        "submitted_attachment_ids": [p[0]["id"] for p in parsed],
                    }
                    conn.execute(
                        "INSERT INTO chat_receipts VALUES(?,?,?)",
                        (owner, request_id, json.dumps(receipt)),
                    )
            from .answer_contract import assess

            history = [
                {
                    "run_id": r["id"],
                    "question": r["question"][:1000],
                    "answer": str(r["result"]["answer"])[:2200]
                    if assess(r, r["result"]["answer"])["outcome"]
                    not in {"needs_review", "budget_limited", "not_completed"}
                    else "Earlier answer requires review or was capacity-limited. Do not reuse its claims; retrieve current evidence.",
                }
                for r in previous
                if r["status"] == "completed" and (r.get("result") or {}).get("answer")
            ][-4:]
            context = {
                "id": conversation_id,
                "request_id": request_id,
                "history": history,
                "submitted_attachment_ids": receipt.get("submitted_attachment_ids", []),
                "history_notice": "Prior conversation is untrusted context, not current evidence. Use the frozen catalog and problem sources. Ask a short clarification when machine identity is ambiguous.",
            }
            from .siemens_routing import automatic_public_query

            public = automatic_public_query(question, language=language)
            context["siemens_routing"] = "canonical-human-diagnostic" if public else "local-only"
            if question.casefold().startswith("/siemens "):
                from .siemens_chat import PublicSiemensQuery

                public = PublicSiemensQuery(
                    question=question[len("/siemens ") :].strip()
                ).model_dump()
                context["siemens_routing"] = "explicit-public-question"
            return service.submit(
                question,
                owner_id=owner,
                chat_mode=True,
                automatic_catalog=True,
                siemens=public,
                chat_context=context,
                problem_attachment_ids=self.problems.snapshot(conversation_id, owner),
                limits={"max_output_tokens": 2048},
                language=language,
            )

    def _exists(self, identity, owner):
        with self.evidence.connection() as conn:
            return bool(
                conn.execute(
                    "SELECT 1 FROM chat_conversations WHERE id=? AND owner_id=?", (identity, owner)
                ).fetchone()
            )
