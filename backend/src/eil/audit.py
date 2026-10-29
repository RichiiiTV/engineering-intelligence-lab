"""Append-only application audit records, with a verifiable local hash chain."""

import hashlib
import json
import time


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


def append(conn, actor, kind, subject=None, details=None):
    if not conn.in_transaction:
        conn.execute("BEGIN IMMEDIATE")
    last = conn.execute("SELECT id,entry_hash FROM auth_audit ORDER BY id DESC LIMIT 1").fetchone()
    row = dict(
        id=last["id"] + 1 if last else 1,
        at=time.time(),
        actor_id=actor,
        kind=kind,
        subject_id=subject,
        details=json.dumps(details or {}, sort_keys=True, separators=(",", ":")),
        previous_hash=last["entry_hash"] if last else "0" * 64,
    )
    if len(row["details"]) > 2000:
        raise ValueError("Audit metadata is too large")
    conn.execute(
        "INSERT INTO auth_audit(id,at,actor_id,kind,subject_id,details,previous_hash,entry_hash) VALUES (?,?,?,?,?,?,?,?)",
        (*row.values(), checksum(row)),
    )


def verify(conn):
    previous, count = "0" * 64, 0
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
