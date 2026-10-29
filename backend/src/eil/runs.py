"""Durable development run records and budgets; never exposed as agent tools."""

from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field

from .settings import OLLAMA_BASE_URL, OLLAMA_MODEL

STOPPED = frozenset(
    {"completed", "failed", "paused", "cancelled", "interrupted", "timed_out", "budget_exceeded"}
)
RESUMABLE = frozenset({"paused", "interrupted", "failed"})


class RunLimits(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    max_steps: int = Field(default=35, ge=1, le=100)
    max_model_calls: int = Field(default=8, ge=1, le=20)
    max_tool_calls: int = Field(default=16, ge=1, le=40)
    max_total_tokens: int = Field(default=32768, ge=1, le=131072)
    max_output_tokens: int = Field(default=1024, ge=1, le=2048)
    timeout_seconds: float = Field(default=120, ge=1, le=600)


class RunNotFound(LookupError):
    pass


class RunConflict(RuntimeError):
    pass


class QueueFull(RunConflict):
    pass


class BudgetExceeded(RuntimeError):
    def __init__(self, message, resource=None):
        super().__init__(message)
        self.resource = resource


class RunStopped(RuntimeError):
    pass


def now():
    return datetime.now(timezone.utc).isoformat()


class RunStore:
    def __init__(self, directory: Path):
        self.directory = Path(directory).resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / "runs.sqlite3"
        with self.connection() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY, status TEXT NOT NULL,
                    created_at TEXT NOT NULL, document TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL REFERENCES runs(id),
                    at TEXT NOT NULL, type TEXT NOT NULL, data TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS events_run ON events(run_id, id);
            """)

    @contextmanager
    def connection(self):
        conn = sqlite3.connect(self.path, timeout=10)
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def _read(conn, run_id):
        row = conn.execute("SELECT document FROM runs WHERE id=?", (run_id,)).fetchone()
        if row is None:
            raise RunNotFound("Investigation not found")
        return json.loads(row[0])

    @staticmethod
    def _write(conn, run):
        run["updated_at"] = now()
        conn.execute(
            "UPDATE runs SET status=?, document=? WHERE id=?",
            (run["status"], json.dumps(run), run["id"]),
        )

    @staticmethod
    def _event(conn, run_id, kind, data):
        conn.execute(
            "INSERT INTO events(run_id,at,type,data) VALUES (?,?,?,?)",
            (run_id, now(), kind, json.dumps(data)),
        )

    def change(self, run_id, update):
        with self.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            run = self._read(conn, run_id)
            update(run, conn)
            self._write(conn, run)
            return run

    def get(self, run_id):
        with self.connection() as conn:
            return self._read(conn, run_id)

    def list(self, limit=50, *, case_id=None):
        with self.connection() as conn:
            return [
                json.loads(r[0])
                for r in conn.execute(
                    "SELECT document FROM runs WHERE (? IS NULL OR json_extract(document, '$.case_id')=?) "
                    "ORDER BY created_at DESC LIMIT ?",
                    (case_id, case_id, limit),
                )
            ]

    def create(self, question, limits=None, *, case_id=None, use_mock_mcp=False):
        if not question.strip() or len(question) > 4000:
            raise ValueError("Question must contain 1-4000 characters")
        limits = RunLimits.model_validate(limits or {})
        url = urlsplit(OLLAMA_BASE_URL)
        if url.scheme not in {"http", "https"} or not url.hostname or url.username or url.password:
            raise ValueError("Configure an HTTP Ollama URL without embedded credentials")
        run_id = str(uuid.uuid4())
        source_ids = None
        if case_id is not None:
            from .evidence import EvidenceStore

            source_ids = EvidenceStore(self.directory).snapshot(case_id)
        if use_mock_mcp and case_id is None:
            raise ValueError("Mock MCP requires a case-backed investigation")
        run = dict(
            id=run_id,
            thread_id=run_id,
            question=question,
            use_mock_mcp=use_mock_mcp,
            status="queued",
            created_at=now(),
            updated_at=now(),
            started_at=None,
            finished_at=None,
            attempt_started_at=None,
            attempts=0,
            control=None,
            result=None,
            error=None,
            elapsed_seconds=0.0,
            steps=0,
            model_calls=0,
            tool_calls=0,
            tokens=0,
            limits=limits.model_dump(),
            model=OLLAMA_MODEL,
            base_url=OLLAMA_BASE_URL,
            worker_pid=None,
            case_id=case_id,
            source_ids=source_ids,
        )
        with self.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            pending = conn.execute("SELECT count(*) FROM runs WHERE status='queued'").fetchone()[0]
            if pending >= 20:
                raise QueueFull("The local queue is full; wait for an investigation to finish")
            conn.execute(
                "INSERT INTO runs VALUES (?,?,?,?)",
                (run_id, "queued", run["created_at"], json.dumps(run)),
            )
            self._event(conn, run_id, "queued", {"limits": run["limits"]})
        return run

    def claim(self):
        with self.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT id FROM runs WHERE status='queued' ORDER BY created_at LIMIT 1"
            ).fetchone()
            if row is None:
                return None
            run = self._read(conn, row[0])
            run.update(
                status="running",
                attempts=run["attempts"] + 1,
                error=None,
                attempt_started_at=now(),
                finished_at=None,
            )
            run["started_at"] = run["started_at"] or now()
            self._write(conn, run)
            self._event(conn, run["id"], "running", {"attempt": run["attempts"]})
            return run

    def event(self, run_id, kind, data):
        with self.connection() as conn:
            self._read(conn, run_id)
            self._event(conn, run_id, kind, data)

    def events(self, run_id, after=0):
        with self.connection() as conn:
            self._read(conn, run_id)
            return [
                dict(id=r[0], run_id=run_id, at=r[1], type=r[2], data=json.loads(r[3]))
                for r in conn.execute(
                    "SELECT id,at,type,data FROM events WHERE run_id=? AND id>? ORDER BY id LIMIT 100",
                    (run_id, after),
                )
            ]

    def control(self, run_id, action):
        def update(run, conn):
            status = run["status"]
            if action == "resume":
                if status not in RESUMABLE:
                    raise RunConflict(
                        "Only paused, interrupted or failed investigations can resume"
                    )
                if run["elapsed_seconds"] >= run["limits"]["timeout_seconds"]:
                    raise RunConflict("Time budget exhausted; create a new investigation")
                pending = conn.execute(
                    "SELECT count(*) FROM runs WHERE status='queued'"
                ).fetchone()[0]
                if pending >= 20:
                    raise QueueFull("The local queue is full; wait before resuming")
                run.update(status="queued", control=None, error=None, finished_at=None)
            elif action in {"pause", "cancel"}:
                target = "paused" if action == "pause" else "cancelled"
                if status == target:
                    return
                if status == "completed" or (status in STOPPED and status not in RESUMABLE):
                    raise RunConflict("This investigation has already ended")
                if status == "running":
                    run["control"] = action
                else:
                    run.update(status=target, control=None, finished_at=now())
            else:
                raise ValueError("Unknown run action")
            self._event(conn, run_id, action + "_requested", {"status": run["status"]})

        return self.change(run_id, update)

    def finish(self, run_id, status, *, result=None, error=None, force=False):
        def update(run, conn):
            if run["status"] != "running" or (run["control"] and not force):
                return
            run.update(
                status=status,
                result=result,
                error=error,
                control=None,
                finished_at=now(),
                worker_pid=None,
            )
            self._event(conn, run_id, status, {"error": error})

        return self.change(run_id, update)

    def recover(self):
        with self.connection() as conn:
            ids = [r[0] for r in conn.execute("SELECT id FROM runs WHERE status='running'")]
        for run_id in ids:
            self.finish(
                run_id,
                "interrupted",
                force=True,
                error={
                    "code": "service_restarted",
                    "message": "Service restarted. Resume from the latest durable checkpoint.",
                },
            )

    def charge(self, run_id, kind, amount=1):
        """Reserve before work; counts survive failure, interruption and resume."""

        def update(run, conn):
            if run["status"] != "running" or run["control"]:
                raise RunStopped("Investigation was stopped")
            key = {
                "steps": "max_steps",
                "model_calls": "max_model_calls",
                "tool_calls": "max_tool_calls",
                "tokens": "max_total_tokens",
            }[kind]
            if run[kind] + amount > run["limits"][key]:
                raise BudgetExceeded(f"{kind} budget exhausted; create a new investigation", kind)
            run[kind] += amount

        return self.change(run_id, update)

    def reserve_model(self, run_id, context_tokens):
        """Atomically admit one actual request, fitting its output cap to remaining capacity."""
        reservation = {}

        def update(run, conn):
            if run["status"] != "running" or run["control"]:
                raise RunStopped("Investigation was stopped")
            limits = run["limits"]
            if run["model_calls"] >= limits["max_model_calls"]:
                raise BudgetExceeded("Model call limit reached", "model_calls")
            remaining = limits["max_total_tokens"] - run["tokens"]
            output = min(limits["max_output_tokens"], remaining - context_tokens)
            if output < min(limits["max_output_tokens"], 256):
                raise BudgetExceeded(
                    "Token allowance reached. Continue with extra capacity to keep this investigation's progress.",
                    "tokens",
                )
            reserved = context_tokens + output
            finalizing = (
                run["model_calls"] + 1 >= limits["max_model_calls"]
                or run["tool_calls"] >= limits["max_tool_calls"]
                or remaining - reserved < context_tokens + limits["max_output_tokens"]
            )
            run["model_calls"] += 1
            run["tokens"] += reserved
            reservation.update(reserved=reserved, output_tokens=output, finalizing=finalizing)

        run = self.change(run_id, update)
        return run, reservation

    def continue_tokens(self, run_id, additional_tokens=0):
        """Explicit user action: extend tokens within the hard cap, never reset usage or other limits."""
        if (
            isinstance(additional_tokens, bool)
            or not isinstance(additional_tokens, int)
            or not 0 <= additional_tokens <= 65536
        ):
            raise ValueError("Additional tokens must be an integer between 0 and 65,536")

        def update(run, conn):
            error = run.get("error") or {}
            token_stop = error.get("resource") == "tokens" or (
                error.get("resource") is None
                and str(error.get("message", "")).startswith("tokens budget exhausted")
            )
            if run["status"] != "budget_exceeded" or not token_stop:
                raise RunConflict(
                    "Only an investigation stopped by its token allowance can continue this way"
                )
            limits = run["limits"]
            if any(
                run[counter] >= limits[limit]
                for counter, limit in (
                    ("model_calls", "max_model_calls"),
                    ("tool_calls", "max_tool_calls"),
                    ("steps", "max_steps"),
                    ("elapsed_seconds", "timeout_seconds"),
                )
            ):
                raise RunConflict("Another run limit is exhausted; start a new question")
            new_limit = limits["max_total_tokens"] + additional_tokens
            if new_limit > 131072:
                raise RunConflict("The maximum token allowance for one investigation is 131,072")
            from .agent import MODEL_CONTEXT_TOKENS

            if new_limit - run["tokens"] < MODEL_CONTEXT_TOKENS + min(
                limits["max_output_tokens"], 256
            ):
                raise RunConflict(
                    "Request additional token capacity to continue this investigation"
                )
            if conn.execute("SELECT count(*) FROM runs WHERE status='queued'").fetchone()[0] >= 20:
                raise QueueFull("The local queue is full; wait before continuing")
            run.setdefault("initial_limits", dict(limits))
            previous = limits["max_total_tokens"]
            run["limits"] = {**limits, "max_total_tokens": new_limit}
            run.update(status="queued", control=None, error=None, finished_at=None)
            self._event(
                conn,
                run_id,
                "token_allowance_extended" if additional_tokens else "investigation_continued",
                {
                    "previous_limit": previous,
                    "new_limit": new_limit,
                    "additional_tokens": additional_tokens,
                    "tokens_already_used": run["tokens"],
                    "reason": "explicit_user_continuation",
                },
            )

        return self.change(run_id, update)

    def settle_tokens(self, run_id, reserved, actual):
        def update(run, conn):
            if actual < 0 or actual > reserved:
                raise BudgetExceeded("Model usage exceeded its reserved token envelope")
            run["tokens"] -= reserved - actual

        return self.change(run_id, update)
