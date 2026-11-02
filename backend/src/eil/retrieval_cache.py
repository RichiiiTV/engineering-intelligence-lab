"""Bounded derived indexes keyed by an authorized immutable source snapshot.

This caches indexes, never permissions, queries, query embeddings or search results.
An optional fixed-state content-addressed file cache allows supervised workers to
reuse indexes. Query bindings are never retained. Expiry is checked on access;
busy memory leases are closed on release rather than underneath a reader.
"""

import hashlib
import json
import os
import re
import sqlite3
import threading
import time
import uuid
from collections import OrderedDict
from contextlib import closing, contextmanager
from dataclasses import dataclass, field
from pathlib import Path

import sqlite_vec

from .performance import record_timing, timed

FILE_SCHEMA = "eil-derived-retrieval-v1"
FILE_LIMIT = 8
BYTE_LIMIT = 64 * 1024**2
FILE_TTL = 300


class SnapshotFiles:
    """Fixed derived-data folder only; backups deliberately allowlist other files.

    Knowledge sources currently support archival, not permanent deletion. Case and
    problem-attachment content never enters these indexes. Source mutations clear
    this derived folder; frozen source selections can then rebuild their index.
    """

    def __init__(self, scope):
        evidence = Path(scope[0])
        if (
            not evidence.is_absolute()
            or evidence.name != "evidence.sqlite3"
            or evidence.parent.name != "data"
        ):
            raise ValueError("Use the fixed evidence store scope")
        self.state = evidence.parent.parent.resolve()
        self.root = self.state / "retrieval-cache"
        self.root.mkdir(exist_ok=True)
        if self.root.is_symlink() or self.root.resolve().parent != self.state:
            raise ValueError("Derived cache must stay inside its state directory")

    @contextmanager
    def locked(self):
        owner = self.root / "owner.sqlite3"
        if owner.is_symlink():
            raise ValueError("Invalid derived-cache lock path")
        with closing(sqlite3.connect(owner, timeout=0.25, cached_statements=0)) as lock:
            try:
                lock.execute("CREATE TABLE IF NOT EXISTS owner(id INTEGER)")
                lock.execute("BEGIN EXCLUSIVE")
                yield
            finally:
                lock.rollback()

    def _files(self):
        return [
            p
            for p in self.root.iterdir()
            if re.fullmatch(r"[0-9a-f]{64}\.sqlite3", p.name) and p.is_file() and not p.is_symlink()
        ]

    def _remove(self, path):
        if path.parent != self.root or path.is_symlink():
            return False
        try:
            path.unlink(missing_ok=True)
            return True
        except OSError:
            return False  # A Windows reader can pin a file; never close its handle.

    def _cleanup(self, needed=0):
        for partial in self.root.glob("building-*.sqlite3"):
            if re.fullmatch(r"building-[0-9a-f]{32}\.sqlite3", partial.name):
                self._remove(partial)
        files = sorted(self._files(), key=lambda p: (p.stat().st_mtime, p.name))
        for path in files:
            if path.stat().st_mtime + FILE_TTL <= time.time():
                self._remove(path)
        files = sorted(self._files(), key=lambda p: (p.stat().st_mtime, p.name))
        count, size = len(files), sum(p.stat().st_size for p in files)
        for path in files:
            if count + bool(needed) <= FILE_LIMIT and size + needed <= BYTE_LIMIT:
                break
            amount = path.stat().st_size
            if self._remove(path):
                count, size = count - 1, size - amount
        return count + bool(needed) <= FILE_LIMIT and size + needed <= BYTE_LIMIT

    @staticmethod
    def _read(path, key, model, count):
        connection = sqlite3.connect(
            path.as_uri() + "?mode=ro&immutable=1",
            uri=True,
            check_same_thread=False,
            cached_statements=0,
        )
        try:
            connection.execute("PRAGMA query_only=ON")
            connection.execute("PRAGMA trusted_schema=OFF")
            identity = connection.execute(
                "SELECT schema,key,passages FROM cache_identity"
            ).fetchall()
            if identity != [(FILE_SCHEMA, key, count)]:
                raise sqlite3.DatabaseError("Derived index identity mismatch")
            if connection.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise sqlite3.DatabaseError("Derived index failed its integrity check")
            if model is not None:
                connection.enable_load_extension(True)
                try:
                    sqlite_vec.load(connection)
                finally:
                    connection.enable_load_extension(False)
            pages = connection.execute("PRAGMA page_count").fetchone()[0]
            page_size = connection.execute("PRAGMA page_size").fetchone()[0]
            return _Entry(connection, pages * page_size * 2 + 65536, 0)
        except BaseException:
            connection.close()
            raise

    def get(self, key, corpus, model, build):
        """Return a verified read-only file hit, or atomically publish a new index."""
        if not re.fullmatch(r"[0-9a-f]{64}", key):
            raise ValueError("Use a content-addressed derived-cache key")
        path = self.root / (key + ".sqlite3")
        with self.locked():
            self._cleanup()
            if (
                path.is_file()
                and not path.is_symlink()
                and path.stat().st_mtime + FILE_TTL > time.time()
                and 0 < path.stat().st_size <= BYTE_LIMIT
            ):
                try:
                    return self._read(path, key, model, len(corpus)), True
                except (OSError, sqlite3.Error):
                    self._remove(path)
            entry = build()
            partial = self.root / ("building-" + uuid.uuid4().hex + ".sqlite3")
            try:
                size = (
                    entry.connection.execute("PRAGMA page_count").fetchone()[0]
                    * entry.connection.execute("PRAGMA page_size").fetchone()[0]
                    + 4096
                )
                if not self._cleanup(size):
                    return entry, False
                with closing(sqlite3.connect(partial, cached_statements=0)) as destination:
                    destination.execute("PRAGMA journal_mode=OFF")
                    entry.connection.backup(destination)
                    destination.execute(
                        "CREATE TABLE cache_identity(schema TEXT,key TEXT,passages INTEGER)"
                    )
                    destination.execute(
                        "INSERT INTO cache_identity VALUES(?,?,?)", (FILE_SCHEMA, key, len(corpus))
                    )
                    destination.commit()
                partial.replace(path)
                readonly = self._read(path, key, model, len(corpus))
                entry.connection.close()
                return readonly, False
            except (OSError, sqlite3.Error):
                self._remove(partial)
                return (
                    entry,
                    False,
                )  # Caching is optional; fresh authorized retrieval remains usable.

    def clear(self):
        with self.locked():
            for path in self._files():
                self._remove(path)
            self._cleanup()


def snapshot_digest(documents, corpus):
    digest = hashlib.sha256()

    def append(value):
        data = (
            value
            if isinstance(value, bytes)
            else json.dumps(
                value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
        )
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)

    for document in sorted(documents, key=lambda d: d["id"]):
        append({k: v for k, v in document.items() if k != "raw"})
    for passage in corpus:
        append({k: passage[k] for k in passage.keys() if k != "vector"})
        append(passage["vector"] or b"")
    return digest.hexdigest()


@dataclass
class _Entry:
    connection: sqlite3.Connection
    size: int
    expires: float
    references: int = 0
    retained: bool = False
    lock: threading.RLock = field(default_factory=threading.RLock)


class IndexCache:
    def __init__(self, *, max_entries=8, max_bytes=64 * 1024**2, ttl_seconds=300, persistent=False):
        if max_entries < 0 or max_bytes < 0 or ttl_seconds <= 0:
            raise ValueError("Invalid retrieval cache limits")
        self.max_entries, self.max_bytes, self.ttl = max_entries, max_bytes, ttl_seconds
        self.persistent = persistent
        self._lock = threading.RLock()
        self._entries = OrderedDict()
        self._bytes = 0
        self._disk_states = OrderedDict()

    @staticmethod
    def _build(corpus, model, dimensions):
        connection = sqlite3.connect(":memory:", check_same_thread=False, cached_statements=0)
        try:
            connection.execute("CREATE VIRTUAL TABLE terms USING fts5(text,id UNINDEXED)")
            connection.executemany(
                "INSERT INTO terms VALUES (?,?)", [(p["text"], p["id"]) for p in corpus]
            )
            if model is not None:
                connection.enable_load_extension(True)
                try:
                    sqlite_vec.load(connection)
                finally:
                    connection.enable_load_extension(False)
                connection.execute("CREATE TABLE vectors(id TEXT, vector BLOB)")
                connection.executemany(
                    "INSERT INTO vectors VALUES (?,?)",
                    [
                        (p["id"], p["vector"])
                        for p in corpus
                        if p["model"] == model
                        and p["vector"] is not None
                        and len(p["vector"]) == dimensions
                    ],
                )
            connection.commit()
            pages = connection.execute("PRAGMA page_count").fetchone()[0]
            page_size = connection.execute("PRAGMA page_size").fetchone()[0]
            # Conservative allowance for SQLite/page and Python entry overhead.
            size = pages * page_size * 2 + 65536
            return _Entry(connection, size, 0)
        except BaseException:
            connection.close()
            raise

    def _discard(self, key):
        entry = self._entries.pop(key)
        self._bytes -= entry.size
        entry.retained = False
        if not entry.references:
            entry.connection.close()

    def invalidate(self, scope=None):
        """Drop retained entries; existing readers finish with their leased snapshot."""
        with self._lock:
            for key in list(self._entries):
                if scope is None or key[0] == scope:
                    self._discard(key)
            if self.persistent:
                states = (
                    [scope]
                    if scope is not None
                    else [
                        (str(state / "data/evidence.sqlite3"), None, None)
                        for state in self._disk_states
                    ]
                )
                for state_scope in states:
                    try:
                        SnapshotFiles(state_scope).clear()
                    except (OSError, sqlite3.Error, ValueError):
                        pass  # Archived originals remain authorized for frozen runs; no hard-delete occurs.

    def stats(self):
        with self._lock:
            return {"entries": len(self._entries), "estimated_bytes": self._bytes}

    @contextmanager
    def acquire(self, scope, fingerprint, corpus, *, model=None, dimensions=None):
        started = time.perf_counter()
        key = (scope, fingerprint, model, dimensions)
        with self._lock:
            current = time.monotonic()
            for prior in list(self._entries):
                if self._entries[prior].expires <= current:
                    self._discard(prior)
            hit = key in self._entries
            if hit:
                entry = self._entries.pop(key)
                self._entries[key] = entry
            else:
                built = False

                def build():
                    nonlocal built
                    built = True
                    with timed("index_build"):
                        return self._build(corpus, model, dimensions)

                if self.persistent:
                    try:
                        files = SnapshotFiles(scope)
                        self._disk_states[files.state] = None
                        self._disk_states.move_to_end(files.state)
                        while len(self._disk_states) > 16:
                            self._disk_states.popitem(last=False)
                        file_key = hashlib.sha256(
                            json.dumps((FILE_SCHEMA, key), separators=(",", ":")).encode()
                        ).hexdigest()
                        entry, hit = files.get(file_key, corpus, model, build)
                    except (OSError, sqlite3.Error, ValueError):
                        if built:
                            raise
                        entry = build()
                else:
                    entry = build()
                entry.expires = time.monotonic() + self.ttl
                if self.max_entries and entry.size <= self.max_bytes:
                    for prior in list(self._entries):
                        if (
                            len(self._entries) < self.max_entries
                            and self._bytes + entry.size <= self.max_bytes
                        ):
                            break
                        if not self._entries[prior].references:
                            self._discard(prior)
                    if (
                        len(self._entries) < self.max_entries
                        and self._bytes + entry.size <= self.max_bytes
                    ):
                        entry.retained = True
                        self._entries[key] = entry
                        self._bytes += entry.size
            entry.references += 1
        try:
            with entry.lock:
                record_timing(
                    "index_lookup",
                    duration_ms=(time.perf_counter() - started) * 1000,
                    cache_hit=hit,
                )
                yield entry.connection
        finally:
            with self._lock:
                entry.references -= 1
                if not entry.retained and not entry.references:
                    entry.connection.close()


# Only the explicit operator value "1" enables private derived files. Unknown
# values fail safe to memory; small libraries did not show a robust disk speedup.
INDEXES = IndexCache(persistent=os.environ.get("EIL_RETRIEVAL_DISK_CACHE", "0") == "1")
