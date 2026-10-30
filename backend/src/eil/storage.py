"""Recoverable case lifecycle and bounded, verified local backups. No agent access."""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import tempfile
import threading
import uuid
import zipfile
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .auth import AuthStore
from .database import DATABASE_BYTES, StorageFull
from .evidence import EvidenceNotFound, EvidenceStore
from .runs import RunConflict, RunStore, now

CASE_LOCK = threading.RLock()
DATABASES = {
    "runs.sqlite3": "runs",
    "data/evidence.sqlite3": "evidence",
    "checkpoints.sqlite3": "checkpoints",
    "auth.sqlite3": "auth",
    "audit.sqlite3": "audit",
}
BACKUP_COUNT = 3
BACKUP_BYTES = 2 * 1024**3
TRASH_DAYS = 90


def database_files(directory):
    result = dict(DATABASES)
    folder = Path(directory) / "audit-archives"
    for path in sorted(folder.glob("audit-*.sqlite3")):
        if re.fullmatch(r"audit-\d{12}\.sqlite3", path.name):
            result["audit-archives/" + path.name] = "audit"
    if len(result) > len(DATABASES) + 8:
        raise RunConflict("Audit archive quota exceeded")
    return result


def database_kind(name):
    if name in DATABASES:
        return DATABASES[name]
    if re.fullmatch(r"audit-archives/audit-\d{12}\.sqlite3", name):
        return "audit"
    raise RunConflict("Unapproved backup path")


def checksum(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


class StorageManager:
    def __init__(self, directory):
        self.directory = Path(directory).resolve()
        self.runs = RunStore(self.directory)
        self.evidence = EvidenceStore(self.directory)
        self.auth = AuthStore(self.directory)
        self.backups = self.directory / "backups"
        self.backups.mkdir(exist_ok=True)
        with self.auth.connection() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS retention_plans (id TEXT PRIMARY KEY, digest TEXT NOT NULL, payload TEXT NOT NULL, status TEXT NOT NULL, backup_id TEXT)"
            )

    def assert_idle(self):
        from .evidence import EvidenceStore

        with EvidenceStore(self.directory).connection() as conn:
            if (
                conn.execute("SELECT 1 FROM sqlite_master WHERE name='ingestion_jobs'").fetchone()
                and conn.execute(
                    "SELECT 1 FROM ingestion_jobs WHERE status IN ('queued','running') LIMIT 1"
                ).fetchone()
            ):
                raise RunConflict("Finish or cancel document ingestion before maintenance")
        with self.runs.connection() as conn:
            if conn.execute(
                "SELECT 1 FROM runs WHERE status IN ('running','queued') LIMIT 1"
            ).fetchone():
                raise RunConflict(
                    "Finish or pause queued/running investigations before maintenance"
                )

    def status(self):
        databases = []
        for name, kind in database_files(self.directory).items():
            path = self.directory / name
            if path.exists():
                with closing(sqlite3.connect(path)) as conn:
                    size = (
                        conn.execute("PRAGMA page_count").fetchone()[0]
                        * conn.execute("PRAGMA page_size").fetchone()[0]
                    )
                databases.append(
                    {"name": name, "logical_bytes": size, "limit_bytes": DATABASE_BYTES[kind]}
                )
        return {
            "databases": databases,
            "trash_retention_days": TRASH_DAYS,
            "backup_limit": BACKUP_COUNT,
            "backup_byte_limit": BACKUP_BYTES,
            "backups": self.list_backups(),
        }

    def trash(self, case_id, actor, *, restore=False):
        with CASE_LOCK:
            case = self.evidence.case(case_id, include_deleted=True)
            if case["owner_id"] != actor.id:
                raise EvidenceNotFound("Case not found")
            with self.runs.connection() as conn:
                conn.execute("BEGIN IMMEDIATE")
                if conn.execute(
                    "SELECT 1 FROM runs WHERE json_extract(document,'$.case_id')=? AND status IN ('running','queued') LIMIT 1",
                    (case_id,),
                ).fetchone():
                    raise RunConflict(
                        "Pause or finish this case's investigations before moving it to Trash"
                    )
                conn.execute(
                    "UPDATE runs SET document=json_set(document,'$.case_deleted',?) WHERE json_extract(document,'$.case_id')=?",
                    (int(not restore), case_id),
                )
            deleted = None if restore else (case["deleted_at"] or now())
            with self.evidence.connection() as conn:
                conn.execute("UPDATE cases SET deleted_at=? WHERE id=?", (deleted, case_id))
            with self.auth.connection() as conn:
                self.auth.audit(
                    conn, actor.id, "case_restored" if restore else "case_trashed", case_id
                )
            return self.evidence.case(case_id, include_deleted=True)

    def list_backups(self):
        return [
            {"id": p.stem, "size": p.stat().st_size, "sha256": checksum(p)}
            for p in sorted(self.backups.glob("backup-*.zip"), reverse=True)
        ]

    def create_backup(self, actor):
        self.assert_idle()
        previous = self.list_backups()
        if len(previous) >= BACKUP_COUNT or sum(p["size"] for p in previous) >= BACKUP_BYTES:
            raise StorageFull(
                "Backup quota reached. Archive/review existing backups before creating another; none are deleted automatically."
            )
        identity = "backup-" + uuid.uuid4().hex
        with tempfile.TemporaryDirectory(dir=self.backups) as temporary:
            work = Path(temporary).resolve()
            if not work.is_relative_to(self.backups.resolve()):
                raise RunConflict("Invalid backup workspace")
            entries = {}
            for name, kind in database_files(self.directory).items():
                source = self.directory / name
                if not source.exists():
                    continue
                destination = work / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                with (
                    closing(sqlite3.connect(source)) as original,
                    closing(sqlite3.connect(destination)) as copied,
                ):
                    original.backup(copied)
                    if kind == "auth":
                        copied.execute("DELETE FROM sessions")
                        copied.execute("DELETE FROM bootstrap")
                        copied.execute("DELETE FROM failures")
                        copied.commit()
                    if copied.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                        raise RunConflict("Backup database integrity check failed")
                entries[name] = {
                    "sha256": checksum(destination),
                    "size": destination.stat().st_size,
                }
            manifest = {
                "schema": "eil-backup-v1",
                "created_at": now(),
                "actor": actor.public(),
                "files": entries,
                "sessions_revoked_on_restore": True,
            }
            archive = work / "snapshot.zip"
            with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
                bundle.writestr("manifest.json", json.dumps(manifest))
                for name in entries:
                    bundle.write(work / name, name)
            if archive.stat().st_size + sum(p["size"] for p in previous) > BACKUP_BYTES:
                raise StorageFull("Backup would exceed the backup byte quota")
            destination = self.backups / (identity + ".zip")
            archive.replace(destination)
        with self.auth.connection() as conn:
            self.auth.audit(conn, actor.id, "backup_created", identity)
        return {"id": identity, "size": destination.stat().st_size, "sha256": checksum(destination)}

    def backup_path(self, identity):
        if (
            not isinstance(identity, str)
            or not identity.startswith("backup-")
            or len(identity) != 39
        ):
            raise EvidenceNotFound("Backup not found")
        try:
            uuid.UUID(hex=identity[7:])
        except ValueError as exc:
            raise EvidenceNotFound("Backup not found") from exc
        path = self.backups / (identity + ".zip")
        if not path.is_file():
            raise EvidenceNotFound("Backup not found")
        return path

    def retention_plan(self, actor):
        self.assert_idle()
        cutoff = (datetime.now(timezone.utc) - timedelta(days=TRASH_DAYS)).isoformat()
        with self.evidence.connection() as conn:
            cases = [
                dict(r)
                for r in conn.execute(
                    "SELECT id,title,deleted_at FROM cases WHERE owner_id=? AND deleted_at IS NOT NULL AND deleted_at<? ORDER BY id",
                    (actor.id, cutoff),
                )
            ]
            for case in cases:
                case["sources"] = [
                    dict(r)
                    for r in conn.execute(
                        "SELECT id,sha256,size FROM sources WHERE case_id=? ORDER BY id",
                        (case["id"],),
                    )
                ]
        payload = {
            "schema": "eil-retention-plan-v1",
            "actor_id": actor.id,
            "created_at": now(),
            "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat(),
            "cases": cases,
        }
        with self.runs.connection() as conn:
            for case in cases:
                case["runs"] = [
                    r[0]
                    for r in conn.execute(
                        "SELECT id FROM runs WHERE json_extract(document,'$.case_id')=? ORDER BY id",
                        (case["id"],),
                    )
                ]
        serialized = json.dumps(payload, sort_keys=True)
        digest = hashlib.sha256(serialized.encode()).hexdigest()
        identity = str(uuid.uuid4())
        with self.auth.connection() as conn:
            conn.execute(
                "INSERT INTO retention_plans VALUES (?,?,?,'pending',NULL)",
                (identity, digest, serialized),
            )
        return {"id": identity, "sha256": digest, **payload}

    def apply_retention(self, identity, expected_sha256, actor, confirmation):
        self.assert_idle()
        if confirmation != "PERMANENTLY PURGE REVIEWED TRASH":
            raise RunConflict("Explicit permanent-deletion confirmation is required")
        with self.auth.connection() as conn:
            row = conn.execute("SELECT * FROM retention_plans WHERE id=?", (identity,)).fetchone()
        if not row or row["digest"] != expected_sha256:
            raise RunConflict("Retention plan changed or was not found")
        plan = json.loads(row["payload"])
        if plan["actor_id"] != actor.id or (
            row["status"] == "pending" and plan["expires_at"] < now()
        ):
            raise RunConflict("Retention plan expired or belongs to another account")
        if row["status"] == "completed":
            return {"status": "completed", "backup_id": row["backup_id"]}
        for case in plan["cases"]:
            with self.evidence.connection() as conn:
                current = conn.execute(
                    "SELECT deleted_at FROM cases WHERE id=? AND owner_id=?", (case["id"], actor.id)
                ).fetchone()
                sources = [
                    dict(r)
                    for r in conn.execute(
                        "SELECT id,sha256,size FROM sources WHERE case_id=? ORDER BY id",
                        (case["id"],),
                    )
                ]
            if not current and row["status"] == "applying":
                continue
            if not current or current[0] != case["deleted_at"] or sources != case["sources"]:
                raise RunConflict("Trash changed after review; create a fresh retention plan")
        backup_id = row["backup_id"]
        if row["status"] == "pending":
            backup_id = self.create_backup(actor)["id"]
            with self.auth.connection() as conn:
                conn.execute(
                    "UPDATE retention_plans SET status='applying',backup_id=? WHERE id=?",
                    (backup_id, identity),
                )
        for case in plan["cases"]:
            with self.runs.connection() as conn:
                ids = case["runs"]
                for table in ("report_drafts", "report_proposals"):
                    if conn.execute(
                        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
                    ).fetchone():
                        conn.execute(f"DELETE FROM {table} WHERE case_id=?", (case["id"],))
                for run_id in ids:
                    conn.execute("DELETE FROM events WHERE run_id=?", (run_id,))
                    conn.execute("DELETE FROM runs WHERE id=?", (run_id,))
            checkpoint = self.directory / "checkpoints.sqlite3"
            if checkpoint.exists():
                with closing(sqlite3.connect(checkpoint)) as conn:
                    for table in ("checkpoints", "writes"):
                        if conn.execute(
                            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
                        ).fetchone():
                            for run_id in ids:
                                conn.execute(f"DELETE FROM {table} WHERE thread_id=?", (run_id,))
                    conn.commit()
            with self.evidence.connection() as conn:
                conn.execute("DELETE FROM chunks WHERE case_id=?", (case["id"],))
                conn.execute("DELETE FROM sources WHERE case_id=?", (case["id"],))
                conn.execute("DELETE FROM cases WHERE id=?", (case["id"],))
        with self.auth.connection() as conn:
            conn.execute("UPDATE retention_plans SET status='completed' WHERE id=?", (identity,))
            self.auth.audit(conn, actor.id, "retention_applied", identity)
        return {"status": "completed", "backup_id": backup_id, "purged_cases": len(plan["cases"])}


def restore_backup(archive, destination):
    """Restore into a NEW directory only. Never replace the current installation."""
    archive, destination = Path(archive).resolve(), Path(destination).resolve()
    if destination.exists() or not destination.parent.is_dir():
        raise RunConflict("Restore requires a new directory with an existing parent")
    with zipfile.ZipFile(archive) as bundle:
        names = bundle.namelist()
        if (
            len(names) != len(set(names))
            or not {"manifest.json", "runs.sqlite3", "data/evidence.sqlite3", "auth.sqlite3"}
            <= set(names)
            or any(
                name != "manifest.json"
                and name not in DATABASES
                and not re.fullmatch(r"audit-archives/audit-\d{12}\.sqlite3", name)
                for name in names
            )
            or len(names) > len(DATABASES) + 9
        ):
            raise RunConflict("Backup contains unapproved or duplicate paths")
        if bundle.getinfo("manifest.json").file_size > 65536:
            raise RunConflict("Invalid backup manifest size")
        manifest = json.loads(bundle.read("manifest.json"))
        if manifest.get("schema") != "eil-backup-v1" or set(manifest.get("files", {})) != set(
            names
        ) - {"manifest.json"}:
            raise RunConflict("Invalid backup manifest")
        for name, entry in manifest["files"].items():
            if (
                bundle.getinfo(name).file_size != entry["size"]
                or entry["size"] > DATABASE_BYTES[database_kind(name)]
            ):
                raise RunConflict("Backup database exceeds its size envelope")
        destination.mkdir()
        incomplete = destination / ".restore-incomplete"
        incomplete.write_text("Restore has not completed. Do not start the service here.")
        for name, entry in manifest["files"].items():
            path = destination / name
            path.parent.mkdir(exist_ok=True)
            total = 0
            with bundle.open(name) as original, path.open("xb") as output:
                while chunk := original.read(65536):
                    total += len(chunk)
                    if total > entry["size"]:
                        raise RunConflict("Backup data exceeds its manifest size")
                    output.write(chunk)
            if checksum(path) != entry["sha256"]:
                raise RunConflict("Backup checksum mismatch; restore remains marked incomplete")
            with closing(sqlite3.connect(path)) as conn:
                if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise RunConflict("Restored database integrity check failed")
                if database_kind(name) == "auth":
                    conn.execute("DELETE FROM sessions")
                    conn.execute("DELETE FROM bootstrap")
                    conn.commit()
        incomplete.unlink()
    return {"status": "restored", "destination": str(destination), "sessions_revoked": True}
