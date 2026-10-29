"""Immutable report proposals. Saving requires a separate, content-bound human decision."""

import hashlib
import json
import uuid

from .evidence import EvidenceStore
from .runs import RunConflict, RunNotFound, now


class DraftStore:
    def __init__(self, runs):
        self.runs = runs
        with runs.connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS report_proposals (
                    id TEXT PRIMARY KEY, case_id TEXT NOT NULL, run_id TEXT NOT NULL,
                    document TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS report_drafts (
                    id TEXT PRIMARY KEY, case_id TEXT NOT NULL, proposal_id TEXT UNIQUE NOT NULL,
                    document TEXT NOT NULL
                );
            """)

    def propose(self, run_id, title, body):
        run = self.runs.get(run_id)
        if not run.get("case_id") or run["status"] != "completed":
            raise RunConflict("Report proposals require a completed case investigation")
        if not title.strip() or len(title) > 120 or not body.strip() or len(body) > 20000:
            raise ValueError("Draft requires a title (1-120) and body (1-20,000 characters)")
        digest = hashlib.sha256(
            json.dumps({"title": title, "body": body}, sort_keys=True).encode()
        ).hexdigest()
        proposal = dict(
            id=str(uuid.uuid4()),
            case_id=run["case_id"],
            run_id=run_id,
            title=title,
            body=body,
            sha256=digest,
            status="pending",
            created_at=now(),
            decided_at=None,
            draft_id=None,
            action="save_report_draft",
        )
        with self.runs.connection() as conn:
            conn.execute(
                "INSERT INTO report_proposals VALUES (?,?,?,?)",
                (
                    proposal["id"],
                    run["case_id"],
                    run_id,
                    json.dumps(proposal),
                ),
            )
            self.runs._event(
                conn,
                run_id,
                "approval_requested",
                {"proposal_id": proposal["id"], "sha256": digest, "action": proposal["action"]},
            )
        return proposal

    @staticmethod
    def _get(conn, proposal_id):
        row = conn.execute(
            "SELECT document FROM report_proposals WHERE id=?", (proposal_id,)
        ).fetchone()
        if row is None:
            raise RunNotFound("Report proposal not found")
        return json.loads(row[0])

    def get(self, proposal_id):
        with self.runs.connection() as conn:
            return self._get(conn, proposal_id)

    def proposals(self, case_id):
        EvidenceStore(self.runs.directory).case(case_id)
        with self.runs.connection() as conn:
            return [
                json.loads(r[0])
                for r in conn.execute(
                    "SELECT document FROM report_proposals WHERE case_id=? ORDER BY rowid DESC LIMIT 50",
                    (case_id,),
                )
            ]

    def decide(self, proposal_id, decision, expected_sha256, *, actor=None):
        if decision not in {"approve", "reject"}:
            raise ValueError("Decision must be approve or reject")
        with self.runs.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            proposal = self._get(conn, proposal_id)
            if expected_sha256 != proposal["sha256"]:
                raise RunConflict("Proposal content changed; review it again before deciding")
            status = "approved" if decision == "approve" else "rejected"
            if proposal["status"] == status:
                return proposal
            if proposal["status"] != "pending":
                raise RunConflict("This proposal has already been decided")
            proposal.update(
                status=status,
                decided_at=now(),
                reviewer=actor,
                reviewer_authentication="authenticated-session" if actor else "trusted-local-call",
            )
            if decision == "approve":
                draft = {**proposal, "id": str(uuid.uuid4()), "proposal_id": proposal_id}
                proposal["draft_id"] = draft["id"]
                conn.execute(
                    "INSERT INTO report_drafts VALUES (?,?,?,?)",
                    (
                        draft["id"],
                        proposal["case_id"],
                        proposal_id,
                        json.dumps(draft),
                    ),
                )
            conn.execute(
                "UPDATE report_proposals SET document=? WHERE id=?",
                (
                    json.dumps(proposal),
                    proposal_id,
                ),
            )
            self.runs._event(
                conn,
                proposal["run_id"],
                "approval_decided",
                {
                    "proposal_id": proposal_id,
                    "decision": decision,
                    "sha256": expected_sha256,
                    "draft_id": proposal["draft_id"],
                    "reviewer": actor,
                },
            )
            return proposal

    def drafts(self, case_id):
        EvidenceStore(self.runs.directory).case(case_id)
        with self.runs.connection() as conn:
            return [
                json.loads(r[0])
                for r in conn.execute(
                    "SELECT document FROM report_drafts WHERE case_id=? ORDER BY rowid DESC LIMIT 50",
                    (case_id,),
                )
            ]
