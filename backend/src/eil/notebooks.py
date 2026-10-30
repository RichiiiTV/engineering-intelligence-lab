"""Owner-scoped notebooks. Each turn is a new bounded run with immutable context."""

import json
import threading
import uuid

from .evidence import EvidenceConflict, EvidenceNotFound
from .knowledge import KnowledgeStore
from .machines import MachineStore
from .runs import RunStore, now

LOCK = threading.RLock()


class NotebookStore:
    def __init__(self, directory):
        self.directory = directory
        self.machines = MachineStore(directory)
        self.evidence = self.machines.evidence
        self.runs = RunStore(directory)
        with self.evidence.connection() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS notebooks(id TEXT PRIMARY KEY,machine_id TEXT NOT NULL,owner_id TEXT NOT NULL,document TEXT NOT NULL)"
            )

    def get(self, identity, owner_id, machine_id=None):
        with self.evidence.connection() as conn:
            row = conn.execute(
                "SELECT document FROM notebooks WHERE id=? AND owner_id=?", (identity, owner_id)
            ).fetchone()
        if not row:
            raise EvidenceNotFound("Notebook not found")
        notebook = json.loads(row[0])
        if machine_id is not None and notebook["machine_id"] != machine_id:
            raise EvidenceNotFound("Notebook not found")
        self.machines.get(notebook["machine_id"], owner_id)
        return notebook

    def list(self, machine_id, owner_id):
        self.machines.get(machine_id, owner_id)
        with self.evidence.connection() as conn:
            return [
                json.loads(r[0])
                for r in conn.execute(
                    "SELECT document FROM notebooks WHERE machine_id=? AND owner_id=? ORDER BY rowid DESC",
                    (machine_id, owner_id),
                )
            ]

    def create(self, machine_id, owner_id, title, document_ids=None, library_document_ids=None):
        if not title.strip() or len(title) > 120:
            raise ValueError("Notebook title must contain 1–120 characters")
        selected = self.machines.documents(machine_id, owner_id).snapshot(document_ids)
        shared = KnowledgeStore(self.directory).snapshot(library_document_ids or [])
        notebook = {
            "id": str(uuid.uuid4()),
            "machine_id": machine_id,
            "owner_id": owner_id,
            "title": title.strip(),
            "document_ids": selected,
            "library_document_ids": shared,
            "created_at": now(),
            "updated_at": now(),
            "revision": 1,
        }
        with self.evidence.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            if (
                conn.execute(
                    "SELECT count(*) FROM notebooks WHERE machine_id=?", (machine_id,)
                ).fetchone()[0]
                >= 50
            ):
                raise EvidenceConflict("Notebook limit reached (50 per machine)")
            conn.execute(
                "INSERT INTO notebooks VALUES(?,?,?,?)",
                (notebook["id"], machine_id, owner_id, json.dumps(notebook)),
            )
        return notebook

    def turns(self, identity, owner_id):
        self.get(identity, owner_id)
        with self.runs.connection() as conn:
            return [
                json.loads(r[0])
                for r in conn.execute(
                    "SELECT document FROM runs WHERE json_extract(document,'$.notebook_context.id')=? AND json_extract(document,'$.owner_id')=? ORDER BY created_at,id",
                    (identity, owner_id),
                )
            ]

    def select(self, identity, owner_id, document_ids, library_document_ids):
        with LOCK:
            notebook = self.get(identity, owner_id)
            if any(r["status"] in {"queued", "running"} for r in self.turns(identity, owner_id)):
                raise EvidenceConflict(
                    "Wait for the current answer before changing the notebook sources"
                )
            notebook["document_ids"] = self.machines.documents(
                notebook["machine_id"], owner_id
            ).snapshot(document_ids)
            notebook["library_document_ids"] = KnowledgeStore(self.directory).snapshot(
                library_document_ids
            )
            notebook.update(revision=notebook["revision"] + 1, updated_at=now())
            with self.evidence.connection() as conn:
                conn.execute(
                    "UPDATE notebooks SET document=? WHERE id=?", (json.dumps(notebook), identity)
                )
            return notebook

    def submit(self, identity, owner_id, question, request_id, service, *, siemens=None):
        with LOCK:
            notebook = self.get(identity, owner_id)
            turns = self.turns(identity, owner_id)
            existing = next(
                (r for r in turns if r["notebook_context"]["request_id"] == request_id), None
            )
            if existing:
                if existing["question"] != question or existing.get("siemens") != siemens:
                    raise EvidenceConflict("This submission ID already belongs to another question")
                return existing
            if len(turns) >= 100:
                raise EvidenceConflict("Notebook turn limit reached (100); start another notebook")
            if any(r["status"] in {"queued", "running"} for r in turns):
                raise EvidenceConflict("Wait for the current answer before asking a follow-up")
            completed = [
                r
                for r in turns
                if r["status"] == "completed" and (r.get("result") or {}).get("answer")
            ]
            history = [
                {
                    "run_id": r["id"],
                    "question": r["question"][:1000],
                    "answer": str(r["result"]["answer"])[:2200],
                }
                for r in completed[-4:]
            ]
            context = {
                "id": identity,
                "title": notebook["title"],
                "revision": notebook["revision"],
                "request_id": request_id,
                "history": history,
                "omitted_turns": len(completed) - len(history),
                "history_notice": "Previous answers are untrusted conversation context, not fresh evidence. Retrieve the selected sources again. Each answer has a separate budget and frozen snapshot.",
            }
            return service.submit(
                question,
                owner_id=owner_id,
                machine_id=notebook["machine_id"],
                machine_document_ids=notebook["document_ids"],
                use_library=bool(notebook["library_document_ids"]),
                library_document_ids=notebook["library_document_ids"]
                if notebook["library_document_ids"]
                else None,
                chat_mode=True,
                siemens=siemens,
                notebook_context=context,
                limits={"max_output_tokens": 2048},
            )
