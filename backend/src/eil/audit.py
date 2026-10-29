"""Append-only application audit records, with a verifiable local hash chain."""

import hashlib
import json
import re
import sqlite3
import threading
import time
import uuid
from contextlib import closing, contextmanager
from pathlib import Path

from .database import StorageFull, configure

_flush_lock = threading.RLock()
MAX_PENDING = 500


class AuditUnavailable(StorageFull):
    pass


def enqueue(conn, actor, kind, subject=None, details=None):
    if not conn.in_transaction:
        conn.execute("BEGIN IMMEDIATE")
    # Anonymous failures retain bounded counters and periodic aggregate events.
    anonymous = actor is None and kind in {"authorization_denied", "login_failed"}
    current = time.time()
    if anonymous:
        row = conn.execute("SELECT * FROM audit_counters WHERE kind=?", (kind,)).fetchone()
        conn.execute(
            "INSERT INTO audit_counters VALUES (?,1,?,?) ON CONFLICT(kind) DO UPDATE SET count=count+1,last=excluded.last",
            (kind, current, current),
        )
        if row and current - row["first"] < 60:
            return
        details = {
            "aggregated_count": row["count"] if row else 1,
            "status": (details or {}).get("status"),
        }
        conn.execute("UPDATE audit_counters SET count=0,first=? WHERE kind=?", (current, kind))
    if conn.execute("SELECT count(*) FROM audit_outbox").fetchone()[0] >= MAX_PENDING:
        if kind in {
            "account_created",
            "account_enrolled",
            "bootstrap_issued",
            "password_changed",
            "user_updated",
            "sessions_revoked",
        }:
            raise AuditUnavailable(
                "Audit backlog is full. Export/archive the audit store before changing account security."
            )
        conn.execute(
            "INSERT INTO audit_counters VALUES (?,1,?,?) ON CONFLICT(kind) DO UPDATE SET count=count+1,last=excluded.last",
            ("overflow:" + kind, current, current),
        )
        return
    payload = json.dumps(details or {}, sort_keys=True, separators=(",", ":"))
    if len(payload) > 2000:
        raise ValueError("Audit metadata is too large")
    conn.execute(
        "INSERT INTO audit_outbox VALUES (?,?,?,?,?,?)",
        (str(uuid.uuid4()), current, actor, kind, subject, payload),
    )


class AuditStore:
    def __init__(self, directory):
        self.directory = Path(directory).resolve()
        self.path = self.directory / "audit.sqlite3"
        self.directory.mkdir(parents=True, exist_ok=True)
        with self.connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS auth_audit(id INTEGER PRIMARY KEY,at REAL,actor_id TEXT,kind TEXT,subject_id TEXT);
                CREATE TABLE IF NOT EXISTS audit_keys(key TEXT PRIMARY KEY);
                CREATE TABLE IF NOT EXISTS audit_meta(key TEXT PRIMARY KEY,value TEXT);
            """)
            migrate(conn)

    @contextmanager
    def connection(self):
        conn = sqlite3.connect(self.path, timeout=5)
        conn.row_factory = sqlite3.Row
        configure(conn, "audit")
        try:
            yield conn
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    def paths(self):
        with self.connection() as conn:
            row = conn.execute("SELECT value FROM audit_meta WHERE key='archives'").fetchone()
        names = json.loads(row[0]) if row else []
        if len(names) > 8 or any(
            not re.fullmatch(r"audit-\d{12}\.sqlite3", name) for name in names
        ):
            raise AuditUnavailable("Invalid audit archive registry")
        return [self.directory / "audit-archives" / name for name in names] + [self.path]

    def events(self, after=0, limit=100, actor="", kind=""):
        result = []
        for path in self.paths():
            with closing(sqlite3.connect(path)) as conn:
                conn.row_factory = sqlite3.Row
                result.extend(
                    dict(r)
                    for r in conn.execute(
                        "SELECT * FROM auth_audit WHERE id>? AND (?='' OR actor_id=?) AND (?='' OR kind=?) ORDER BY id LIMIT ?",
                        (after, actor, actor, kind, kind, limit - len(result)),
                    )
                )
            if len(result) >= limit:
                break
        return result

    def integrity(self):
        head, count = "0" * 64, 0
        for path in self.paths():
            with closing(sqlite3.connect(path)) as conn:
                conn.row_factory = sqlite3.Row
                anchor = conn.execute("SELECT value FROM audit_meta WHERE key='anchor'").fetchone()
                if (anchor[0] if anchor else "0" * 64) != head:
                    return {
                        "valid": False,
                        "checked": count,
                        "error": "Archive chain link mismatch",
                    }
                result = verify(conn)
                if not result["valid"]:
                    return result
                head = result["head_hash"]
                count += result["checked"]
        return {"valid": True, "checked": count, "head_hash": head, "segments": len(self.paths())}

    def archive(self):
        with _flush_lock:
            if not self.integrity()["valid"]:
                raise AuditUnavailable("Resolve audit integrity failure before archiving")
            with self.connection() as conn:
                last = conn.execute(
                    "SELECT id,entry_hash FROM auth_audit ORDER BY id DESC LIMIT 1"
                ).fetchone()
                if not last:
                    return {"archived": False, "reason": "Current audit segment is empty"}
                row = conn.execute("SELECT value FROM audit_meta WHERE key='archives'").fetchone()
                names = json.loads(row[0]) if row else []
                if len(names) >= 8:
                    raise AuditUnavailable(
                        "Eight audit archives are retained. Export and arrange operator archival before creating more."
                    )
                name = f"audit-{last['id']:012d}.sqlite3"
                folder = self.directory / "audit-archives"
                folder.mkdir(exist_ok=True)
                path = folder / name
                with closing(sqlite3.connect(path)) as target:
                    conn.backup(target)
                    if target.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                        raise AuditUnavailable("Archive verification failed")
                conn.execute("BEGIN IMMEDIATE")
                conn.execute("DROP TRIGGER audit_no_update")
                conn.execute("DROP TRIGGER audit_no_delete")
                conn.execute("DELETE FROM auth_audit")
                conn.execute("DELETE FROM audit_keys")
                for key, value in [
                    ("anchor", last["entry_hash"]),
                    ("base_id", str(last["id"])),
                    ("archives", json.dumps([*names, name])),
                ]:
                    conn.execute("INSERT OR REPLACE INTO audit_meta VALUES (?,?)", (key, value))
                conn.execute(
                    "CREATE TRIGGER audit_no_update BEFORE UPDATE ON auth_audit BEGIN SELECT RAISE(ABORT,'Audit records are append-only'); END"
                )
                conn.execute(
                    "CREATE TRIGGER audit_no_delete BEFORE DELETE ON auth_audit BEGIN SELECT RAISE(ABORT,'Audit records are append-only'); END"
                )
            flush(self.directory)
            return {
                "archived": True,
                "name": name,
                "head_hash": last["entry_hash"],
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }


def migrate_history(directory):
    path = Path(directory) / "auth.sqlite3"
    with _flush_lock, closing(sqlite3.connect(path, timeout=5)) as source:
        source.row_factory = sqlite3.Row
        marker = source.execute(
            "SELECT value FROM auth_meta WHERE key='audit_separated'"
        ).fetchone()
        if marker:
            return
        rows = source.execute("SELECT * FROM auth_audit ORDER BY id").fetchall()
        target = AuditStore(directory)
        with target.connection() as dest:
            dest.execute("BEGIN IMMEDIATE")
            for row in rows:
                key = "legacy:" + str(row["id"])
                if not dest.execute("SELECT 1 FROM audit_keys WHERE key=?", (key,)).fetchone():
                    dest.execute(
                        "INSERT INTO auth_audit(id,at,actor_id,kind,subject_id,details,previous_hash,entry_hash) VALUES (?,?,?,?,?,?,?,?)",
                        tuple(
                            row[k]
                            for k in (
                                "id",
                                "at",
                                "actor_id",
                                "kind",
                                "subject_id",
                                "details",
                                "previous_hash",
                                "entry_hash",
                            )
                        ),
                    )
                    dest.execute("INSERT INTO audit_keys VALUES (?)", (key,))
        source.execute("DROP TRIGGER IF EXISTS audit_no_delete")
        source.execute("DELETE FROM auth_audit")
        source.execute("INSERT INTO auth_meta VALUES ('audit_separated','1')")
        source.commit()
    flush(directory)


def flush(directory):
    path = Path(directory) / "auth.sqlite3"
    if not path.exists():
        return
    try:
        with _flush_lock, closing(sqlite3.connect(path, timeout=2)) as source:
            source.row_factory = sqlite3.Row
            rows = source.execute("SELECT * FROM audit_outbox ORDER BY at,id LIMIT 500").fetchall()
            if not rows:
                return
            store = AuditStore(directory)
            keys = set()
            placeholders = ",".join("?" for _ in rows)
            for archive in store.paths():
                with closing(sqlite3.connect(archive)) as delivered:
                    keys.update(
                        r[0]
                        for r in delivered.execute(
                            f"SELECT key FROM audit_keys WHERE key IN ({placeholders})",
                            [r["id"] for r in rows],
                        )
                    )
            with store.connection() as conn:
                conn.execute("BEGIN IMMEDIATE")
                for row in rows:
                    if row["id"] in keys:
                        continue
                    append(
                        conn,
                        row["actor"],
                        row["kind"],
                        row["subject"],
                        json.loads(row["details"]),
                        recorded_at=row["at"],
                    )
                    conn.execute("INSERT INTO audit_keys VALUES (?)", (row["id"],))
            source.executemany("DELETE FROM audit_outbox WHERE id=?", [(r["id"],) for r in rows])
            source.commit()
    except (sqlite3.Error, OSError):
        # Identity commits remain valid. Pending entries/counters expose degradation.
        return


def status(directory):
    with closing(sqlite3.connect(Path(directory) / "auth.sqlite3")) as conn:
        pending = conn.execute("SELECT count(*) FROM audit_outbox").fetchone()[0]
        overflow = conn.execute(
            "SELECT coalesce(sum(count),0) FROM audit_counters WHERE kind LIKE 'overflow:%'"
        ).fetchone()[0]
    path = Path(directory) / "audit.sqlite3"
    return {
        "pending": pending,
        "overflow_events": overflow,
        "healthy": pending < MAX_PENDING and overflow == 0,
        "history_bytes": path.stat().st_size if path.exists() else 0,
    }


def checksum(row):
    value = [
        row[k] for k in ("id", "at", "actor_id", "kind", "subject_id", "details", "previous_hash")
    ]
    return hashlib.sha256(
        json.dumps(value, separators=(",", ":"), ensure_ascii=True).encode()
    ).hexdigest()


def migrate(conn):
    columns = {r[1] for r in conn.execute("PRAGMA table_info(auth_audit)")}
    if {"details", "previous_hash", "entry_hash"} <= columns:
        return
    for name, definition in (
        ("details", "TEXT NOT NULL DEFAULT '{}'"),
        ("previous_hash", "TEXT"),
        ("entry_hash", "TEXT"),
    ):
        if name not in columns:
            conn.execute(f"ALTER TABLE auth_audit ADD COLUMN {name} {definition}")
    previous = "0" * 64
    for raw in conn.execute("SELECT * FROM auth_audit ORDER BY id").fetchall():
        row = dict(raw)
        if not row["entry_hash"]:
            row["previous_hash"] = previous
            row["entry_hash"] = checksum(row)
            conn.execute(
                "UPDATE auth_audit SET previous_hash=?,entry_hash=? WHERE id=?",
                (previous, row["entry_hash"], row["id"]),
            )
        previous = row["entry_hash"]
    conn.executescript("""
        CREATE TRIGGER IF NOT EXISTS audit_no_update BEFORE UPDATE ON auth_audit
        BEGIN SELECT RAISE(ABORT, 'Audit records are append-only'); END;
        CREATE TRIGGER IF NOT EXISTS audit_no_delete BEFORE DELETE ON auth_audit
        BEGIN SELECT RAISE(ABORT, 'Audit records are append-only'); END;
    """)


def append(conn, actor, kind, subject=None, details=None, *, recorded_at=None):
    if not conn.in_transaction:
        conn.execute("BEGIN IMMEDIATE")
    last = conn.execute("SELECT id,entry_hash FROM auth_audit ORDER BY id DESC LIMIT 1").fetchone()
    meta = (
        dict(conn.execute("SELECT key,value FROM audit_meta"))
        if conn.execute("SELECT 1 FROM sqlite_master WHERE name='audit_meta'").fetchone()
        else {}
    )
    row = dict(
        id=last["id"] + 1 if last else int(meta.get("base_id", 0)) + 1,
        at=recorded_at if recorded_at is not None else time.time(),
        actor_id=actor,
        kind=kind,
        subject_id=subject,
        details=json.dumps(details or {}, sort_keys=True, separators=(",", ":")),
        previous_hash=last["entry_hash"] if last else meta.get("anchor", "0" * 64),
    )
    if len(row["details"]) > 2000:
        raise ValueError("Audit metadata is too large")
    conn.execute(
        "INSERT INTO auth_audit(id,at,actor_id,kind,subject_id,details,previous_hash,entry_hash) VALUES (?,?,?,?,?,?,?,?)",
        (*row.values(), checksum(row)),
    )


def verify(conn):
    previous, count = "0" * 64, 0
    if conn.execute("SELECT 1 FROM sqlite_master WHERE name='audit_meta'").fetchone():
        anchor = conn.execute("SELECT value FROM audit_meta WHERE key='anchor'").fetchone()
        previous = anchor[0] if anchor else previous
    for raw in conn.execute("SELECT * FROM auth_audit ORDER BY id"):
        row = dict(raw)
        if row["previous_hash"] != previous or checksum(row) != row["entry_hash"]:
            return {"valid": False, "checked": count, "failed_id": row["id"]}
        previous, count = row["entry_hash"], count + 1
    return {
        "valid": True,
        "checked": count,
        "head_hash": previous,
        "boundary": "Local application integrity check; an OS/database administrator can replace the database. Export and retain the head hash independently for stronger assurance.",
    }
