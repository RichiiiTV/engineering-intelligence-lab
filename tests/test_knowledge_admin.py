import json
import sqlite3
import struct
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import StructuredTool
from langchain_ollama import ChatOllama

from eil.api import create_app
from eil.audit import AuditStore, verify
from eil.auth import COOKIE, AuthenticationError, AuthStore
from eil.embeddings import EmbeddingUnavailable
from eil.evidence import EvidenceConflict, EvidenceNotFound
from eil.execution import execute_run
from eil.exports import export_investigation
from eil.knowledge import KnowledgeStore, library_tool
from eil.runs import RunStore
from eil.service import RunService
from eil.storage import StorageManager, restore_backup
from tests.auth_helpers import PASSWORD, sign_in
from tests.fakes import controlled_worker


def add(library, text="Illumination is measured in lux.", **kwargs):
    return library.add(
        "guide.txt",
        text.encode(),
        title="Lighting guide",
        family="Demo camera",
        version="v1",
        license_note="CC0-1.0 generated fixture",
        data_policy="synthetic",
        actor="test",
        **kwargs,
    )


def vectors(texts):
    return "test-model@fixed-digest", [
        struct.pack(
            "<32f",
            *([1.0, 0.0] if ("Illumination" in text or "brightness" in text) else [0.0, 1.0]),
            *([0.0] * 30),
        )
        for text in texts
    ]


def test_hybrid_search_finds_semantic_synonym_and_filters_before_ranking(tmp_path, monkeypatch):
    library = KnowledgeStore(tmp_path)
    lighting = add(library)
    timing = add(library, "Watchdog timing is version-specific.")
    monkeypatch.setattr("eil.knowledge.embed", vectors)
    library.index(lighting["id"])
    library.index(timing["id"])
    result = library.search("brightness", [lighting["id"]])
    assert result["semantic_available"] and result["method"].startswith("hybrid")
    assert result["hits"][0]["id"] == lighting["id"]
    assert not library.search("brightness", [timing["id"]])["hits"]
    assert library.search('" OR *; DROP TABLE knowledge_documents; --', [])["hits"] == []
    with pytest.raises(EvidenceNotFound):
        library.resolve(result["hits"][0]["citation_id"], [timing["id"]])


def test_keyword_fallback_outage_model_drift_and_no_match(tmp_path, monkeypatch):
    library = KnowledgeStore(tmp_path)
    doc = add(library)
    ids = [doc["id"]]
    assert library.search("Illumination", ids)["hits"]
    assert not library.search("ZXQ_UNSUPPORTED_9283", ids)["hits"]
    monkeypatch.setattr("eil.knowledge.embed", vectors)
    library.index(doc["id"])

    def unavailable(texts):
        raise EmbeddingUnavailable("Controlled offline error")

    monkeypatch.setattr("eil.knowledge.embed", unavailable)
    result = library.search("lux", ids)
    assert result["hits"] and not result["semantic_available"]
    assert "unavailable" in result["notice"]
    monkeypatch.setattr("eil.knowledge.embed", lambda texts: ("changed-digest", vectors(texts)[1]))
    result = library.search("lux", ids)
    assert result["hits"] and "changed" in result["notice"]


def test_library_snapshot_survives_disable_and_later_uploads_with_cached_no_argument_tool(
    tmp_path, monkeypatch
):
    library = KnowledgeStore(tmp_path)
    library.seed()
    run = RunStore(tmp_path).create("watchdog", use_library=True)
    before = run["library_document_ids"]
    later = add(library)
    assert later["id"] not in before
    assert not StructuredTool.from_function(library_tool(tmp_path, run["id"])).args
    tool = library_tool(tmp_path, run["id"])
    result = json.loads(tool())
    assert result["hits"]
    for identity in before:
        library.set_active(identity, False)
    assert not set(before) & set(library.snapshot())
    assert library.resolve(result["hits"][0]["citation_id"], before)
    monkeypatch.setattr(KnowledgeStore, "search", lambda *a: pytest.fail("Repeated retrieval"))
    assert json.loads(library_tool(tmp_path, run["id"])()) == result
    with pytest.raises(TypeError):
        tool(query="injected")


@pytest.mark.parametrize(
    "filename,content",
    [
        ("../escape.txt", b"x"),
        ("script.html", b"x"),
        ("bad.pdf", b"not PDF"),
        ("bad.txt", b"\x00binary"),
        ("empty.txt", b""),
    ],
)
def test_library_rejects_bad_uploads(tmp_path, filename, content):
    with pytest.raises(ValueError):
        KnowledgeStore(tmp_path).add(
            filename,
            content,
            title="test",
            family="Demo",
            version="v1",
            license_note="CC0",
            data_policy="synthetic",
            actor="test",
        )


def test_duplicate_and_unlicensed_content_refused(tmp_path):
    library = KnowledgeStore(tmp_path)
    add(library)
    with pytest.raises(EvidenceConflict):
        add(library)
    with pytest.raises(ValueError):
        library.add(
            "guide.txt", b"new", title="x", license_note="none", data_policy="private", actor="test"
        )


class LibraryProbe(ChatOllama):
    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        available = {t["function"]["name"] for t in kwargs.get("tools", [])}
        assert "read_knowledge_library" in available
        assert "compare_stations" not in available and "execute" not in available
        result = next(
            (
                m
                for m in messages
                if isinstance(m, ToolMessage) and m.name == "read_knowledge_library"
            ),
            None,
        )
        if not any(isinstance(m, AIMessage) for m in messages):
            content, calls = "Premature answer", []
        elif result is None:
            content, calls = (
                "",
                [
                    {
                        "name": "read_knowledge_library",
                        "args": {},
                        "id": "library",
                        "type": "tool_call",
                    }
                ],
            )
        else:
            hits = json.loads(result.text)["hits"]
            content, calls = (
                f"A watchdog is a configured time limit; exact behaviour depends on firmware. [{hits[0]['citation_id']}]",
                [],
            )
        return ChatResult(
            generations=[
                ChatGeneration(
                    message=AIMessage(
                        content=content,
                        tool_calls=calls,
                        usage_metadata={
                            "input_tokens": 50,
                            "output_tokens": 50,
                            "total_tokens": 100,
                        },
                    )
                )
            ]
        )


def test_graph_requires_retrieval_charges_calls_and_exports_separate_resolvable_library_citations(
    tmp_path,
):
    runs = RunStore(tmp_path)
    run = runs.create("What is a watchdog?", use_library=True)
    runs.claim()
    execute_run(tmp_path, run["id"], model=LibraryProbe(model="controlled"))
    final = runs.get(run["id"])
    assert final["status"] == "completed", final["error"]
    assert final["model_calls"] == 3 and final["tool_calls"] == 1 and final["tokens"] == 300
    export = export_investigation(runs, run["id"])
    assert any(r["cited_in_answer"] for r in export["library_citations"])
    assert export["library_citation_checks"]["unresolved"] == []
    assert export["citation_checks"]["unresolved"] == []
    assert export["source_snapshot"] == []


def test_admin_permissions_user_revocation_library_snapshots_and_audit_privacy(tmp_path):
    app = create_app(lambda: RunService(tmp_path, worker_target=controlled_worker))
    with TestClient(app, base_url="http://127.0.0.1") as client:
        owner = sign_in(client)
        auth = AuthStore(tmp_path)
        assert len(client.get("/api/library/documents").json()["documents"]) == 3
        member = client.post(
            "/api/auth/users", json={"username": "member", "password": PASSWORD}
        ).json()["user"]
        token, _ = auth.login("member", PASSWORD)
        admin_cookie = client.cookies.get(COOKIE)
        client.cookies.clear()
        client.cookies.set(COOKIE, token)
        assert client.get("/api/admin/audit").status_code == 403
        assert client.get("/api/auth/users").status_code == 403
        assert (
            client.post(f"/api/auth/users/{owner.id}/update", json={"role": "member"}).status_code
            == 403
        )
        assert (
            client.post(
                "/api/library/documents",
                files={"file": ("x.txt", b"public text")},
                data={
                    "title": "x",
                    "family": "x",
                    "version": "v1",
                    "license_note": "CC0",
                    "data_policy": "synthetic",
                    "confirmed": "true",
                },
            ).status_code
            == 403
        )
        client.cookies.clear()
        client.cookies.set(COOKIE, admin_cookie)
        response = client.post(
            "/api/library/documents",
            files={"file": ("reference.txt", b"PRIVATE_SENTINEL is untrusted generated text.")},
            data={
                "title": "Reference",
                "family": "Demo",
                "version": "v1",
                "license_note": "CC0",
                "data_policy": "synthetic",
                "confirmed": "true",
            },
        )
        assert response.status_code == 201, response.text
        document = response.json()
        assert client.post(
            f"/api/auth/users/{owner.id}/update", json={"active": False}
        ).status_code in {401, 422}
        assert (
            client.post(
                f"/api/auth/users/{member['id']}/update", json={"active": False}
            ).status_code
            == 200
        )
        with pytest.raises(AuthenticationError):
            auth.authenticate(token)
        assert (
            client.post(
                f"/api/auth/users/{member['id']}/update", json={"active": True, "role": "admin"}
            ).status_code
            == 200
        )
        second, _ = auth.login("member", PASSWORD)
        assert client.post(f"/api/auth/users/{member['id']}/revoke-sessions").status_code == 200
        with pytest.raises(AuthenticationError):
            auth.authenticate(second)
        audit = client.get("/api/admin/audit?limit=2").json()
        assert audit["integrity"]["valid"] and audit["next_after"]
        exported = client.get("/api/admin/audit/export")
        assert exported.status_code == 200
        assert (
            PASSWORD not in exported.text
            and "PRIVATE_SENTINEL" not in exported.text
            and token not in exported.text
        )
        assert (
            client.post(
                f"/api/library/documents/{document['id']}/availability", json={"active": False}
            ).status_code
            == 200
        )


def test_audit_append_only_concurrent_chain_and_legacy_migration(tmp_path):
    auth = AuthStore(tmp_path)
    owner = auth.enroll(auth.bootstrap(), "owner", PASSWORD)

    def record(i):
        with auth.connection() as conn:
            auth.audit(conn, owner.id, "test_event", str(i))

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(record, range(12)))
    with AuditStore(tmp_path).connection() as conn:
        assert verify(conn)["valid"]
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("DELETE FROM auth_audit")
    # Verify legacy records can be migrated without inventing historical details.
    legacy = tmp_path / "legacy"
    legacy.mkdir()
    with sqlite3.connect(legacy / "auth.sqlite3") as conn:
        conn.execute(
            "CREATE TABLE auth_audit(id INTEGER PRIMARY KEY,at REAL,actor_id TEXT,kind TEXT,subject_id TEXT)"
        )
        conn.execute("INSERT INTO auth_audit VALUES (1,1,'operator','legacy_event',NULL)")
    migrated = AuthStore(legacy)
    with AuditStore(migrated.directory).connection() as conn:
        assert verify(conn)["valid"]
        assert conn.execute("SELECT kind FROM auth_audit").fetchone()[0] == "legacy_event"


def test_backup_preserves_library_vectors_and_audit_but_revokes_sessions(tmp_path, monkeypatch):
    original = tmp_path / "original"
    auth = AuthStore(original)
    owner = auth.enroll(auth.bootstrap(), "owner", PASSWORD)
    token, _ = auth.login("owner", PASSWORD)
    library = KnowledgeStore(original)
    doc = add(library)
    monkeypatch.setattr("eil.knowledge.embed", vectors)
    library.index(doc["id"])
    manager = StorageManager(original)
    backup = manager.create_backup(owner)
    target = tmp_path / "restored"
    restore_backup(manager.backup_path(backup["id"]), target)
    restored = KnowledgeStore(target)
    assert restored.list()[0]["indexed_passages"] == 1
    assert restored.search("brightness", [doc["id"]])["hits"]
    with AuditStore(target).connection() as conn:
        assert verify(conn)["valid"]
    with pytest.raises(AuthenticationError):
        AuthStore(target).authenticate(token)


def test_failed_reindex_is_atomic_and_tampering_is_detected(tmp_path, monkeypatch):
    library = KnowledgeStore(tmp_path)
    doc = add(library)
    monkeypatch.setattr("eil.knowledge.embed", vectors)
    library.index(doc["id"])
    before = library.list()[0]["indexed_passages"]

    def fail(texts):
        raise EmbeddingUnavailable("controlled failure")

    monkeypatch.setattr("eil.knowledge.embed", fail)
    with pytest.raises(EmbeddingUnavailable):
        library.index(doc["id"])
    assert library.list()[0]["indexed_passages"] == before
    auth = AuthStore(tmp_path)
    with auth.connection() as conn:
        auth.audit(conn, "operator", "test")
    with AuditStore(tmp_path).connection() as conn:
        conn.execute("DROP TRIGGER audit_no_update")
        conn.execute("UPDATE auth_audit SET details='{} tampered' WHERE id=1")
        assert not verify(conn)["valid"]


def test_library_stops_before_retrieval_when_model_budget_is_exhausted(tmp_path, monkeypatch):
    runs = RunStore(tmp_path)
    run = runs.create("What is a watchdog?", {"max_total_tokens": 1}, use_library=True)
    runs.claim()
    monkeypatch.setattr(KnowledgeStore, "search", lambda *a: pytest.fail("Unbudgeted retrieval"))
    execute_run(tmp_path, run["id"], model=LibraryProbe(model="controlled"))
    final = runs.get(run["id"])
    assert final["status"] == "budget_exceeded" and final["tool_calls"] == 0


@pytest.mark.parametrize(
    "endpoint",
    [
        "https://external.example",
        "http://localhost:11434/?secret=x",
        "http://user:password@127.0.0.1:11434",
    ],
)
def test_embeddings_reject_nonlocal_or_credentialled_endpoints(monkeypatch, endpoint):
    from eil import embeddings

    monkeypatch.setattr(embeddings, "OLLAMA_BASE_URL", endpoint)
    with pytest.raises(EmbeddingUnavailable):
        embeddings.embed(["public generated text"])


def test_capacity_summary_does_not_force_unavailable_library_tools(tmp_path, monkeypatch):
    class CapacityProbe(ChatOllama):
        def _generate(self, messages, stop=None, run_manager=None, **kwargs):
            assert not kwargs.get("tools", [])
            return ChatResult(
                generations=[
                    ChatGeneration(
                        message=AIMessage(
                            content="The library was not searched within this budget; no source facts were verified.",
                            usage_metadata={
                                "input_tokens": 50,
                                "output_tokens": 50,
                                "total_tokens": 100,
                            },
                        )
                    )
                ]
            )

    runs = RunStore(tmp_path)
    run = runs.create("What is a watchdog?", {"max_model_calls": 1}, use_library=True)
    runs.claim()
    monkeypatch.setattr(KnowledgeStore, "search", lambda *a: pytest.fail("Unbudgeted retrieval"))
    execute_run(tmp_path, run["id"], model=CapacityProbe(model="controlled"))
    final = runs.get(run["id"])
    assert final["status"] == "completed" and final["result"]["capacity_limited"]
    assert final["model_calls"] == 1 and final["tool_calls"] == 0
