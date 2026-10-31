"""Durable, bounded private-source ingestion jobs with supervised trusted workers."""

import json
import multiprocessing
import os
import re
import subprocess
import threading
import time
import uuid
from pathlib import Path

from .evidence import EvidenceConflict, EvidenceNotFound, EvidenceStore, checked_id
from .machines import MachineStore
from .runs import now

TERMINAL = {"completed", "failed", "canceled", "interrupted", "timed_out"}


class JobStore:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.evidence = EvidenceStore(directory)
        with self.evidence.connection() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS ingestion_jobs(id TEXT PRIMARY KEY,machine_id TEXT NOT NULL,owner_id TEXT NOT NULL,status TEXT NOT NULL,document TEXT NOT NULL,content BLOB NOT NULL)"
            )

    def get(self, identity, owner_id=None):
        checked_id(identity)
        with self.evidence.connection() as conn:
            row = conn.execute("SELECT * FROM ingestion_jobs WHERE id=?", (identity,)).fetchone()
        if not row or (owner_id is not None and row["owner_id"] != owner_id):
            raise EvidenceNotFound("Ingestion job not found")
        return json.loads(row["document"]) | {"content": row["content"]}

    def list(self, machine_id, owner_id):
        with self.evidence.connection() as conn:
            return [
                json.loads(r[0])
                for r in conn.execute(
                    "SELECT document FROM ingestion_jobs WHERE machine_id=? AND owner_id=? ORDER BY rowid DESC LIMIT 50",
                    (machine_id, owner_id),
                )
            ]

    def enqueue(
        self, machine_id, owner_id, filename, content, metadata, document_id=None, *, catalog=False
    ):
        MachineStore(self.directory).get(machine_id, owner_id)
        if not document_id and (
            not filename
            or len(filename) > 160
            or any(x in filename for x in "/\\:")
            or not 0 < len(content) <= 10 * 1024**2
        ):
            raise ValueError(
                "Upload a plain, bounded source filename and nonempty file (10 MiB maximum)"
            )
        identity = str(uuid.uuid4())
        job = {
            "id": identity,
            "machine_id": machine_id,
            "owner_id": owner_id,
            "status": "queued",
            "filename": filename,
            "metadata": metadata,
            "document_id": document_id,
            "progress": 0,
            "phase": "queued",
            "created_at": now(),
            "updated_at": now(),
            "cancel_requested": False,
            "error": None,
            "attempt": 1,
            "catalog": catalog,
        }
        with self.evidence.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            queued = conn.execute(
                "SELECT count(CASE WHEN status IN ('queued','running') THEN 1 END),coalesce(sum(length(content)),0) FROM ingestion_jobs"
            ).fetchone()
            if queued[0] >= 4 or queued[1] + len(content) > 30 * 1024**2:
                raise EvidenceConflict("Ingestion queue is full (four jobs / 30 MiB staged)")
            if conn.execute("SELECT count(*) FROM ingestion_jobs").fetchone()[0] >= 500:
                raise EvidenceConflict(
                    "Ingestion job history limit reached (500); operator workspace archival is required. No records are deleted automatically."
                )
            conn.execute(
                "INSERT INTO ingestion_jobs VALUES (?,?,?,?,?,?)",
                (identity, machine_id, owner_id, "queued", json.dumps(job), content),
            )
        return job

    def change(self, identity, **values):
        with self.evidence.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT document FROM ingestion_jobs WHERE id=?", (identity,)
            ).fetchone()
            if not row:
                raise EvidenceNotFound("Ingestion job not found")
            job = json.loads(row[0])
            job.update(values, updated_at=now())
            conn.execute(
                "UPDATE ingestion_jobs SET status=?,document=? WHERE id=?",
                (job["status"], json.dumps(job), identity),
            )
        return job

    def claim(self):
        with self.evidence.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT id,document FROM ingestion_jobs WHERE status='queued' ORDER BY rowid LIMIT 1"
            ).fetchone()
            if not row:
                return None
            job = json.loads(row["document"])
            job.update(status="running", phase="starting", updated_at=now())
            conn.execute(
                "UPDATE ingestion_jobs SET status='running',document=? WHERE id=?",
                (json.dumps(job), row["id"]),
            )
            return row["id"]

    def control(self, identity, owner_id, action):
        with self.evidence.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT document FROM ingestion_jobs WHERE id=? AND owner_id=?",
                (identity, owner_id),
            ).fetchone()
            if not row:
                raise EvidenceNotFound("Ingestion job not found")
            job = json.loads(row[0])
            if job.get("phase") == "discarded":
                raise EvidenceConflict(
                    "This staged upload was discarded; upload the file again to retry"
                )
            if action == "cancel" and job["status"] not in TERMINAL:
                job.update(
                    cancel_requested=True,
                    status="canceled" if job["status"] == "queued" else job["status"],
                )
            elif action == "retry" and job["status"] in TERMINAL - {"completed"}:
                if (
                    conn.execute(
                        "SELECT count(*) FROM ingestion_jobs WHERE status IN ('queued','running')"
                    ).fetchone()[0]
                    >= 4
                ):
                    raise EvidenceConflict("Ingestion queue is full")
                job.update(
                    status="queued",
                    cancel_requested=False,
                    error=None,
                    attempt=job["attempt"] + 1,
                    phase="queued",
                    progress=0,
                )
            else:
                raise EvidenceConflict("Unsupported ingestion transition")
            job["updated_at"] = now()
            conn.execute(
                "UPDATE ingestion_jobs SET status=?,document=? WHERE id=?",
                (job["status"], json.dumps(job), identity),
            )
        return job

    def discard(self, identity, owner_id):
        with self.evidence.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT document FROM ingestion_jobs WHERE id=? AND owner_id=?",
                (identity, owner_id),
            ).fetchone()
            if not row:
                raise EvidenceNotFound("Job not found")
            job = json.loads(row[0])
            if job["status"] not in TERMINAL or job["status"] == "completed":
                raise EvidenceConflict("Only a stopped unsuccessful upload can be discarded")
            job.update(
                phase="discarded",
                updated_at=now(),
                error="Staged upload discarded by its owner. Existing source snapshots were retained; upload the file again to retry.",
            )
            conn.execute(
                "UPDATE ingestion_jobs SET document=?,content=X'' WHERE id=?",
                (json.dumps(job), identity),
            )
        return job


def parse_batches(content, store, identity):
    from .isolated_pdf import convert

    result, chunks = {}, []
    start, total = 1, 200
    while start <= total:
        if store.get(identity)["cancel_requested"]:
            raise RuntimeError("Ingestion canceled")
        container = "eil-ingest-" + identity.replace("-", "") + "-p" + str(start)
        store.change(
            identity, phase="parsing", container=container, progress=round(45 * (start - 1) / total)
        )
        batch = convert(
            content, page_range=(start, min(start + 19, total)), container_name=container
        )
        total = batch["total_page_count"]
        if not 1 <= total <= 200:
            raise ValueError("Machine PDF limit is 200 pages")
        chunks.extend(batch["chunks"])
        if len(chunks) > 2000:
            raise ValueError("Document exceeds 2,000 passages")
        result = {k: v for k, v in batch.items() if k != "chunks"}
        start += 20
    return result | {"chunks": chunks, "page_count": total}


def process_job(directory, identity):
    parent = multiprocessing.parent_process()
    if parent is not None:

        def watch_parent():
            while parent.is_alive():
                time.sleep(0.5)
            # The isolated parser has its own deadline; remove only our generated container.
            cleanup_container(JobStore(directory), identity)
            os._exit(1)

        threading.Thread(target=watch_parent, daemon=True).start()
    store = JobStore(directory)
    job = store.get(identity)
    documents = MachineStore(directory).documents(job["machine_id"], job["owner_id"])
    try:
        if not job["document_id"]:
            # Recover a committed staged source if the worker died before recording its ID.
            with documents.evidence.connection() as conn:
                existing = conn.execute(
                    "SELECT id FROM knowledge_documents WHERE machine_id=? AND json_extract(metadata,'$.ingestion_job_id')=?",
                    (job["machine_id"], identity),
                ).fetchone()
            if existing:
                document_id = existing[0]
            else:
                document = documents.add(
                    job["filename"],
                    job["content"],
                    actor=job["owner_id"],
                    pdf_parser=lambda content: parse_batches(content, store, identity),
                    publish=False,
                    job_id=identity,
                    **job["metadata"],
                )
                document_id = document["id"]
            store.change(identity, document_id=document_id)
        else:
            document_id = job["document_id"]
        store.change(identity, phase="indexing", progress=45)
        documents.index(
            document_id,
            progress=lambda done, total: store.change(
                identity, progress=45 + int(50 * done / total)
            ),
            cancelled=lambda: store.get(identity)["cancel_requested"],
        )
        assignment = None
        catalog = None
        if job.get("catalog"):
            from .catalog import CatalogStore

            catalog = CatalogStore(directory)
            assignment = catalog.classify(documents, document_id, store, identity)
        with documents.evidence.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            current = json.loads(
                conn.execute(
                    "SELECT document FROM ingestion_jobs WHERE id=?", (identity,)
                ).fetchone()[0]
            )
            if current["cancel_requested"]:
                raise RuntimeError("Ingestion canceled before publication")
            current.update(
                status="completed", phase="ready", progress=100, updated_at=now(), error=None
            )
            if assignment is not None:
                target, basis = catalog.publish(
                    conn,
                    document_id,
                    job["owner_id"],
                    assignment,
                    current.get("catalog_candidates", []),
                )
                current.update(assigned_machine_id=target, assignment_basis=basis)
            else:
                conn.execute("UPDATE knowledge_documents SET active=1 WHERE id=?", (document_id,))
            conn.execute(
                "UPDATE ingestion_jobs SET status='completed',document=?,content=X'' WHERE id=?",
                (json.dumps(current), identity),
            )
        from .auth import AuthStore

        auth = AuthStore(directory)
        with auth.connection() as conn:
            auth.audit(
                conn,
                job["owner_id"],
                "machine_source_ready",
                document_id,
                {"machine_id": job["machine_id"], "job_id": identity},
            )
    except Exception as exc:
        current = store.get(identity)
        if current["status"] == "completed":
            return  # Publication succeeded; a later audit delivery failure cannot undo it.
        store.change(
            identity,
            status="canceled" if current["cancel_requested"] else "failed",
            phase="stopped",
            error=f"{type(exc).__name__}: ingestion could not complete. Check source format, parser assets and local embedding/classification model availability; no staged source was published.",
        )


def cleanup_container(store, identity):
    name = store.get(identity).get("container", "")
    if re.fullmatch("eil-ingest-" + identity.replace("-", "") + r"-p\d{1,3}", name):
        from .isolated_pdf import docker, flags

        try:
            subprocess.run(
                [*docker(), "rm", "--force", name], timeout=5, capture_output=True, **flags()
            )
        except (OSError, RuntimeError, subprocess.SubprocessError):
            pass


class IngestionService:
    def __init__(self, directory):
        self.store = JobStore(directory)
        self.stop = threading.Event()
        self.thread = None
        self.fatal_error = None

    def start(self):
        with self.store.evidence.connection() as conn:
            interrupted = [
                r[0] for r in conn.execute("SELECT id FROM ingestion_jobs WHERE status='running'")
            ]
        for identity in interrupted:
            self.store.change(
                identity,
                status="interrupted",
                phase="stopped",
                error="Service restarted. Retry explicitly to continue the staged source.",
            )
        self.thread = threading.Thread(target=self.supervise_loop, daemon=True)
        self.thread.start()
        return self

    def close(self):
        self.stop.set()
        if self.thread:
            self.thread.join(15)
        if self.thread and self.thread.is_alive():
            raise RuntimeError("Ingestion supervisor did not stop")

    def supervise_loop(self):
        try:
            self.loop()
        except Exception as exc:
            self.fatal_error = type(exc).__name__

    def loop(self):
        while not self.stop.is_set():
            identity = self.store.claim()
            if not identity:
                self.stop.wait(0.2)
                continue
            process = multiprocessing.get_context("spawn").Process(
                target=process_job, args=(self.store.directory, identity), daemon=True
            )
            try:
                process.start()
            except (OSError, RuntimeError):
                self.store.change(
                    identity,
                    status="failed",
                    error="Ingestion worker could not start; retry explicitly.",
                )
                continue
            deadline = time.monotonic() + 600
            while process.is_alive() and not self.stop.wait(0.2):
                job = self.store.get(identity)
                if (
                    job["cancel_requested"]
                    or time.monotonic() > deadline
                    or (
                        job.get("phase") == "classifying"
                        and time.time() > job.get("classifier_deadline", float("inf"))
                    )
                ):
                    break
            if process.is_alive():
                process.terminate()
                process.join(5)
                job = self.store.get(identity)
                cleanup_container(self.store, identity)
                if job["status"] == "completed":
                    process.close()
                    continue
                self.store.change(
                    identity,
                    status="interrupted"
                    if self.stop.is_set()
                    else "canceled"
                    if job["cancel_requested"]
                    else "timed_out",
                    phase="stopped",
                    error="Ingestion stopped before completion; retry is explicit.",
                )
            else:
                process.join()
                if self.store.get(identity)["status"] == "running":
                    self.store.change(
                        identity,
                        status="failed",
                        error="Ingestion worker exited unexpectedly; retry explicitly.",
                    )
            process.close()
