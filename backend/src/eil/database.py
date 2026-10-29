"""Installation-wide SQLite and row limits, independent of individual cases."""

import sqlite3

DATABASE_BYTES = {
    "evidence": 256 * 1024**2,
    "runs": 128 * 1024**2,
    "checkpoints": 512 * 1024**2,
    "auth": 16 * 1024**2,
    "audit": 64 * 1024**2,
}
MAX_CASES = 500
MAX_RUNS = 5000
MAX_EVENT_BYTES = 128 * 1024


class StorageFull(RuntimeError):
    pass


def configure(conn, kind):
    conn.execute("PRAGMA trusted_schema=OFF")
    page_size = conn.execute("PRAGMA page_size").fetchone()[0]
    pages = max(32, DATABASE_BYTES[kind] // page_size)
    conn.execute(f"PRAGMA max_page_count={pages}")
    conn.execute("PRAGMA journal_size_limit=8388608")
    conn.execute("PRAGMA wal_autocheckpoint=256")


def storage_error(exc):
    return (
        isinstance(exc, sqlite3.DatabaseError)
        and getattr(exc, "sqlite_errorcode", None) == sqlite3.SQLITE_FULL
    )
