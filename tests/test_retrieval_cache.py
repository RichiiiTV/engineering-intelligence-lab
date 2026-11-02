"""Generated sources verify cache equivalence, invalidation, isolation and limits."""

import multiprocessing
import os
import sqlite3
import struct
import zipfile
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from eil.evidence import EvidenceNotFound
from eil.knowledge import KnowledgeStore
from eil.machines import MachineStore
from eil.performance import capture_timings
from eil.retrieval_cache import IndexCache, SnapshotFiles


@pytest.fixture
def cache(monkeypatch):
    value = IndexCache()
    monkeypatch.setattr("eil.knowledge.INDEXES", value)
    yield value
    value.invalidate()


def add(store, text, **kwargs):
    return store.add(
        "generated-guide.txt",
        text.encode(),
        title="Generated conveyor guide",
        family="Generated XR7",
        version="V2",
        license_note="CC0 generated fixture",
        data_policy="synthetic",
        actor="generated-owner",
        **kwargs,
    )


def vector(texts):
    return "generated-model@digest-A", [struct.pack("<32f", 1, *([0] * 31)) for _ in texts]


def rows(text="Generated conveyor E17 sensor blocked"):
    return [{"id": "generated-passage", "text": text, "vector": None, "model": None}]


def test_cached_and_uncached_search_have_identical_evidence_and_rankings(
    tmp_path,
    monkeypatch,
    cache,
):
    store = KnowledgeStore(tmp_path)
    first = add(store, "Generated conveyor E17 sensor is blocked.")
    second = add(store, "Generated conveyor E18 drive has no acknowledgement.")
    allowed = [first["id"], second["id"]]
    monkeypatch.setattr("eil.knowledge.embed", vector)
    for identity in allowed:
        store.index(identity)
    with store.evidence.connection() as connection:
        original = [
            tuple(r) for r in connection.execute("SELECT * FROM knowledge_passages ORDER BY id")
        ]
    timings = []
    with capture_timings(timings.append):
        cold = store.search("conveyor E17 sensor", allowed)
        warm = store.search("conveyor E17 sensor", allowed)
        other_question = store.search("drive acknowledgement", allowed)
    assert cold == warm and cold["semantic_available"]
    assert [x["cache_hit"] for x in timings if x["stage"] == "index_lookup"] == [False, True, True]
    assert len([x for x in timings if x["stage"] == "index_build"]) == 1
    assert all(set(x) <= {"stage", "duration_ms", "cache_hit"} for x in timings)
    uncached = IndexCache(max_entries=0)
    monkeypatch.setattr("eil.knowledge.INDEXES", uncached)
    assert store.search("conveyor E17 sensor", allowed) == cold
    assert store.search("drive acknowledgement", allowed) == other_question
    assert uncached.stats()["entries"] == 0
    with store.evidence.connection() as connection:
        assert [
            tuple(r) for r in connection.execute("SELECT * FROM knowledge_passages ORDER BY id")
        ] == original


def test_reindex_model_digest_and_vector_changes_invalidate_snapshot(tmp_path, monkeypatch, cache):
    store = KnowledgeStore(tmp_path)
    doc = add(store, "Generated E17 sensor is blocked.")
    monkeypatch.setattr("eil.knowledge.embed", vector)
    store.index(doc["id"])
    before = store.search("E17", [doc["id"]])
    assert before["semantic_available"] and cache.stats()["entries"] == 1
    monkeypatch.setattr(
        "eil.knowledge.embed", lambda texts: ("generated-model@digest-B", vector(texts)[1])
    )
    mismatch = store.search("E17", [doc["id"]])
    assert not mismatch["semantic_available"] and "changed" in mismatch["notice"]
    store.index(doc["id"])
    assert store.search("E17", [doc["id"]])["semantic_available"]
    with store.evidence.connection() as connection:
        connection.execute(
            "UPDATE knowledge_passages SET vector=? WHERE document_id=?",
            (struct.pack("<32f", 0, 1, *([0] * 30)), doc["id"]),
        )
    changed = store.search("E17", [doc["id"]])
    assert changed["semantic_available"]
    assert cache.stats()["entries"] == 2


def test_archive_upload_and_metadata_changes_preserve_frozen_selection(tmp_path, cache):
    store = KnowledgeStore(tmp_path)
    doc = add(store, "Generated sensor E17 is blocked.")
    frozen = store.snapshot()
    before = store.search("E17", frozen)
    store.set_active(doc["id"], False)
    assert store.snapshot() == []
    assert store.search("E17", []) == {
        "hits": [],
        "method": "empty-library",
        "semantic_available": False,
    }
    assert store.search("E17", frozen) == before
    assert cache.stats()["entries"] == 1  # Archive discarded the previous retained index.
    later = add(store, "Generated sensor E18 is blocked.")
    assert store.search("E17", frozen) == before
    assert store.snapshot() == [later["id"]]
    assert {h["id"] for h in store.search("sensor", store.snapshot())["hits"]} == {later["id"]}
    assert not store.search("E17 V3", frozen)["hits"]


def test_owner_machine_and_state_scopes_never_reuse_another_index(tmp_path, cache):
    machines = MachineStore(tmp_path / "workspace-A")
    machine_a = machines.create("owner-A", "Generated machine A")
    machine_b = machines.create("owner-B", "Generated machine B")
    store_a = machines.documents(machine_a["id"], "owner-A")
    store_b = machines.documents(machine_b["id"], "owner-B")
    doc_a = add(store_a, "Generated owner A sensor E17 blocked")
    doc_b = add(store_b, "Generated owner B drive E18 stopped")
    assert store_a.search("sensor", [doc_a["id"]])["hits"]
    assert not store_b.search("sensor", [doc_b["id"]])["hits"]
    with pytest.raises(EvidenceNotFound):
        store_b.search("sensor", [doc_a["id"]])
    with pytest.raises(EvidenceNotFound):
        machines.documents(machine_a["id"], "owner-B")
    other_state = KnowledgeStore(tmp_path / "workspace-B")
    other = add(other_state, "Generated unrelated document", identity=doc_a["id"])
    assert not other_state.search("sensor", [other["id"]])["hits"]
    assert cache.stats()["entries"] == 3


def test_lru_byte_limits_and_expiry_close_connections(monkeypatch):
    clock = [100.0]
    monkeypatch.setattr("eil.retrieval_cache.time.monotonic", lambda: clock[0])
    cache = IndexCache(max_entries=1, ttl_seconds=10)
    with cache.acquire(("state", None, None), "first", rows()) as old:
        assert old.execute("SELECT count(*) FROM terms").fetchone()[0] == 1
    with cache.acquire(("state", None, None), "second", rows()) as current:
        assert cache.stats()["entries"] == 1
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        old.execute("SELECT 1")
    clock[0] = 111
    with cache.acquire(("state", None, None), "third", rows()):
        with pytest.raises(sqlite3.ProgrammingError, match="closed"):
            current.execute("SELECT 1")
    cache.invalidate()
    small = IndexCache(max_bytes=1)
    with small.acquire(("state", None, None), "oversized", rows()) as temporary:
        assert temporary.execute("SELECT count(*) FROM terms").fetchone()[0] == 1
        assert small.stats() == {"entries": 0, "estimated_bytes": 0}
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        temporary.execute("SELECT 1")


def test_invalidation_and_full_capacity_do_not_close_busy_leases():
    cache = IndexCache(max_entries=1)
    with cache.acquire(("state-A", None, None), "first", rows()) as pinned:
        with cache.acquire(("state-B", None, None), "second", rows()) as temporary:
            assert cache.stats()["entries"] == 1
            cache.invalidate(("state-A", None, None))
            assert pinned.execute("SELECT count(*) FROM terms").fetchone()[0] == 1
        with pytest.raises(sqlite3.ProgrammingError, match="closed"):
            temporary.execute("SELECT 1")
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        pinned.execute("SELECT 1")


def test_concurrent_queries_share_one_index_without_result_contamination():
    cache = IndexCache()
    barrier = Barrier(4)
    corpus = rows("Generated sensor blocked") + [
        {"id": "second", "text": "Generated drive stopped", "vector": None, "model": None}
    ]

    def lookup(term):
        barrier.wait(timeout=5)
        with cache.acquire(("state", "machine", "owner"), "snapshot", corpus) as index:
            return [
                r[0] for r in index.execute("SELECT id FROM terms WHERE terms MATCH ?", (term,))
            ]

    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(lookup, ["sensor", "drive", "sensor", "drive"]))
    assert results == [["generated-passage"], ["second"], ["generated-passage"], ["second"]]
    assert cache.stats()["entries"] == 1
    cache.invalidate()


def test_failed_index_build_closes_connection_and_can_be_retried(monkeypatch):
    cache = IndexCache()
    import eil.retrieval_cache as module

    original_connect, original_load = sqlite3.connect, module.sqlite_vec.load
    connections = []

    def connect(*args, **kwargs):
        connection = original_connect(*args, **kwargs)
        connections.append(connection)
        return connection

    def failed_load(connection):
        raise sqlite3.OperationalError("Generated extension-load failure")

    monkeypatch.setattr(module.sqlite3, "connect", connect)
    monkeypatch.setattr(module.sqlite_vec, "load", failed_load)
    with pytest.raises(sqlite3.OperationalError, match="Generated"):
        with cache.acquire(
            ("state", None, None), "snapshot", rows(), model="local", dimensions=128
        ):
            pytest.fail("A failed index must not be leased")
    assert cache.stats()["entries"] == 0
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        connections[0].execute("SELECT 1")
    monkeypatch.setattr(module.sqlite_vec, "load", original_load)
    with cache.acquire(("state", None, None), "snapshot", rows(), model="local", dimensions=128):
        assert cache.stats()["entries"] == 1
    cache.invalidate()


def test_semantic_extension_failure_falls_back_then_recovers(tmp_path, monkeypatch, cache):
    store = KnowledgeStore(tmp_path)
    doc = add(store, "Generated E17 sensor blocked")
    monkeypatch.setattr("eil.knowledge.embed", vector)
    store.index(doc["id"])
    import eil.retrieval_cache as module

    original = module.sqlite_vec.load

    def unavailable(connection):
        raise sqlite3.OperationalError("Generated unavailable extension")

    monkeypatch.setattr(module.sqlite_vec, "load", unavailable)
    fallback = store.search("E17 sensor", [doc["id"]])
    assert fallback["hits"] and not fallback["semantic_available"]
    assert "unavailable" in fallback["notice"]
    monkeypatch.setattr(module.sqlite_vec, "load", original)
    recovered = store.search("E17 sensor", [doc["id"]])
    assert recovered["semantic_available"]
    assert recovered["hits"] == fallback["hits"]


def test_changed_dimensions_and_replaced_vectors_do_not_reuse_a_stale_index(
    tmp_path, monkeypatch, cache
):
    store = KnowledgeStore(tmp_path)
    doc = add(store, "Generated E17 sensor blocked")
    monkeypatch.setattr("eil.knowledge.embed", vector)
    store.index(doc["id"])
    assert store.search("E17", [doc["id"]])["semantic_available"]

    monkeypatch.setattr(
        "eil.knowledge.embed",
        lambda texts: (
            "generated-model@digest-A",
            [struct.pack("<64f", 1, *([0] * 63)) for _ in texts],
        ),
    )
    assert "changed" in store.search("E17", [doc["id"]])["notice"]
    store.index(doc["id"])
    assert store.search("E17", [doc["id"]])["semantic_available"]
    with store.evidence.connection() as connection:
        connection.execute(
            "UPDATE knowledge_passages SET vector=? WHERE document_id=?",
            (struct.pack("<64f", *([float("nan")] * 64)), doc["id"]),
        )
    replaced = store.search("E17", [doc["id"]])
    assert replaced["hits"] and cache.stats()["entries"] == 2
    # sqlite-vec treats NaN distances as non-matches. Caching preserves the
    # original available-index flag and lexical results rather than old vectors.
    uncached = IndexCache(max_entries=0)
    monkeypatch.setattr("eil.knowledge.INDEXES", uncached)
    assert store.search("E17", [doc["id"]]) == replaced
    monkeypatch.setattr("eil.knowledge.INDEXES", cache)
    store.index(doc["id"])
    assert store.search("E17", [doc["id"]])["semantic_available"]


def persistent_worker(directory, queue):
    from eil import knowledge

    knowledge.embed = vector
    knowledge.INDEXES = IndexCache(persistent=True)
    store = KnowledgeStore(directory)
    timings = []
    with capture_timings(timings.append):
        result = store.search("Generated E17 sensor", store.snapshot())
    queue.put((result, [t for t in timings if t["stage"] in {"index_lookup", "index_build"}]))
    # Process exit closes its read-only connections; do not delete the shared cache.


def test_persistent_snapshot_reused_by_a_separate_supervised_style_process(tmp_path, monkeypatch):
    store = KnowledgeStore(tmp_path)
    doc = add(store, "Generated E17 sensor blocked")
    monkeypatch.setattr("eil.knowledge.embed", vector)
    store.index(doc["id"])
    first_cache = IndexCache(max_entries=0, persistent=True)
    monkeypatch.setattr("eil.knowledge.INDEXES", first_cache)
    first = store.search("Generated E17 sensor", [doc["id"]])
    ctx = multiprocessing.get_context("spawn")
    queue = ctx.Queue()
    worker = ctx.Process(target=persistent_worker, args=(str(tmp_path), queue))
    try:
        worker.start()
        result, timings = queue.get(timeout=30)
        worker.join(timeout=10)
        assert worker.exitcode == 0
        assert first == result
        assert not [t for t in timings if t["stage"] == "index_build"]
        assert next(t["cache_hit"] for t in timings if t["stage"] == "index_lookup") is True
    finally:
        if worker.is_alive():
            worker.terminate()
            worker.join(timeout=5)
        worker.close()
        queue.close()
    first_cache.invalidate()


def test_persistent_files_are_read_only_and_never_store_query_text(tmp_path, monkeypatch):
    store = KnowledgeStore(tmp_path)
    doc = add(store, "Generated E17 sensor blocked")
    cache = IndexCache(persistent=True)
    monkeypatch.setattr("eil.knowledge.INDEXES", cache)
    query = "E17 generated_private_problem_identifier_928371"
    before = store.search(query, [doc["id"]])
    assert before["hits"]
    for entry in cache._entries.values():
        with pytest.raises(sqlite3.OperationalError, match="readonly|read.only"):
            entry.connection.execute("DELETE FROM terms")
    files = SnapshotFiles(store._scope())._files()
    assert len(files) == 1
    assert query.encode() not in files[0].read_bytes()
    assert b"generated_private_problem_identifier_928371" not in files[0].read_bytes()
    # A different process/cache instance sees the same evidence and no model call.
    cache.invalidate()  # Also proves explicit clear closes the file before removal.
    assert not SnapshotFiles(store._scope())._files()


def test_corrupt_and_interrupted_files_rebuild_from_authorized_sources(tmp_path, monkeypatch):
    store = KnowledgeStore(tmp_path)
    doc = add(store, "Generated E17 sensor blocked")
    first = IndexCache(max_entries=0, persistent=True)
    monkeypatch.setattr("eil.knowledge.INDEXES", first)
    expected = store.search("E17 sensor", [doc["id"]])
    files = SnapshotFiles(store._scope())
    path = files._files()[0]
    path.write_bytes(b"Generated corrupt interrupted SQLite bytes")
    partial = files.root / ("building-" + "a" * 32 + ".sqlite3")
    partial.write_bytes(b"Generated interrupted build")
    replacement = IndexCache(max_entries=0, persistent=True)
    monkeypatch.setattr("eil.knowledge.INDEXES", replacement)
    assert store.search("E17 sensor", [doc["id"]]) == expected
    assert not partial.exists()
    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA quick_check").fetchone()[0] == "ok"
    connection.close()
    replacement.invalidate()


def test_persistent_limits_expiry_and_unavailable_cache_fall_back(tmp_path, monkeypatch):
    import eil.retrieval_cache as module

    (tmp_path / "data").mkdir()
    scope = (str(tmp_path / "data/evidence.sqlite3"), None, None)
    cache = IndexCache(max_entries=0, persistent=True)
    monkeypatch.setattr(module, "FILE_LIMIT", 2)
    for i in range(3):
        with cache.acquire(scope, str(i), rows()) as index:
            assert index.execute("SELECT count(*) FROM terms").fetchone()[0] == 1
    files = SnapshotFiles(scope)
    assert len(files._files()) == 2
    for path in files._files():
        os.utime(path, (1, 1))
    with cache.acquire(scope, "after-expiry", rows()):
        assert len(files._files()) == 1
    monkeypatch.setattr(module, "BYTE_LIMIT", 1)
    with cache.acquire(scope, "too-large", rows()) as temporary:
        assert temporary.execute("SELECT count(*) FROM terms").fetchone()[0] == 1
    assert files._files() == []
    with pytest.raises(ValueError, match="fixed evidence"):
        SnapshotFiles(("relative/untrusted.sqlite3", None, None))
    with cache.acquire(("relative/untrusted.sqlite3", None, None), "memory-only", rows()) as index:
        assert index.execute("SELECT count(*) FROM terms").fetchone()[0] == 1


def test_source_mutations_clear_derived_files_and_backups_exclude_them(tmp_path, monkeypatch):
    from eil.auth import AuthStore
    from eil.storage import StorageManager
    from tests.auth_helpers import PASSWORD

    store = KnowledgeStore(tmp_path)
    doc = add(store, "Generated E17 sensor blocked")
    cache = IndexCache(persistent=True)
    monkeypatch.setattr("eil.knowledge.INDEXES", cache)
    expected = store.search("E17 sensor", [doc["id"]])
    files = SnapshotFiles(store._scope())
    assert files._files()
    auth = AuthStore(tmp_path)
    actor = auth.enroll(auth.bootstrap(), "generated-admin", PASSWORD)
    backup = StorageManager(tmp_path).create_backup(actor)
    with zipfile.ZipFile(StorageManager(tmp_path).backup_path(backup["id"])) as archive:
        assert not any(name.startswith("retrieval-cache/") for name in archive.namelist())
    store.set_active(doc["id"], False)
    assert files._files() == []
    assert store.search("E17 sensor", [doc["id"]]) == expected
    add(store, "Generated E18 drive stopped")
    assert files._files() == []
    monkeypatch.setattr("eil.knowledge.embed", vector)
    store.search("E17 sensor", [doc["id"]])
    store.index(doc["id"])
    assert files._files() == []
    assert store.resolve(expected["hits"][0]["citation_id"], [doc["id"]])
    cache.invalidate()
