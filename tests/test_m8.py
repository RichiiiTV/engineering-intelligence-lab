import json
import struct

import pytest
from fastapi.testclient import TestClient

from eil.api import create_app
from eil.embeddings import EmbeddingUnavailable
from eil.evidence import EvidenceConflict, EvidenceNotFound
from eil.exports import export_investigation
from eil.ingestion import IngestionService, JobStore, parse_batches, process_job
from eil.knowledge import KnowledgeStore
from eil.machines import MachineStore, machine_tools
from eil.runs import RunStore
from eil.service import RunService
from tests.auth_helpers import sign_in
from tests.fakes import controlled_worker


def metadata():
    return dict(
        title="Generated source",
        family="Demo",
        version="V20",
        license_note="CC0 generated",
        data_policy="internal",
    )


def vector(texts):
    return "test@digest", [struct.pack("<32f", 1, *([0] * 31)) for _ in texts]


def source(documents, text=b"IF sensor THEN motor := FALSE; END_IF;"):
    return documents.add("control.st", text, actor="owner", **metadata())


def test_private_sources_cannot_escape_machine_or_owner(tmp_path, monkeypatch):
    monkeypatch.setattr("eil.knowledge.embed", vector)
    machines = MachineStore(tmp_path)
    first = machines.create("owner", "Machine A")
    second = machines.create("owner", "Machine B")
    docs = machines.documents(first["id"], "owner")
    doc = source(docs)
    with pytest.raises(EvidenceNotFound):
        machines.documents(first["id"], "other")
    with pytest.raises(EvidenceNotFound):
        machines.documents(second["id"], "owner").document(doc["id"])
    with pytest.raises(EvidenceNotFound):
        KnowledgeStore(tmp_path).document(doc["id"])
    with pytest.raises(ValueError):
        source(KnowledgeStore(tmp_path))
    runs = RunStore(tmp_path)
    run = runs.create("sensor", machine_id=first["id"], owner_id="owner")
    read, lines, inspect = machine_tools(tmp_path, run["id"])
    hit = json.loads(read())["hits"][0]
    assert hit["line_start"] == 1 and hit["citation_id"]
    assert json.loads(lines(doc["id"]))["execution"] == "never"
    assert "no uploaded code was executed" in json.loads(inspect(doc["id"]))["scope"]
    docs.set_active(doc["id"], False)
    assert json.loads(read())["hits"] == [hit]
    export = export_investigation(runs, run["id"])
    assert export["machine_snapshot"][0]["id"] == doc["id"]
    with pytest.raises(EvidenceNotFound):
        runs.create("x", owner_id="other", machine_id=first["id"])


def test_static_syntax_inspection_never_executes(tmp_path):
    from eil.code_sources import inspect

    sentinel = tmp_path / "must-not-exist"
    text = f"open({str(sentinel)!r}, 'w').write('bad')\nif True print('syntax')"
    assert inspect("source.py", text)["findings"][0]["line"] == 2
    assert not sentinel.exists()


def test_clusters_use_only_owner_and_compatible_vectors(tmp_path, monkeypatch):
    monkeypatch.setattr("eil.knowledge.embed", vector)
    machines = MachineStore(tmp_path)
    for owner, name in [("a", "A"), ("a", "B"), ("b", "Private")]:
        m = machines.create(owner, name)
        docs = machines.documents(m["id"], owner)
        d = source(docs)
        docs.index(d["id"])
    groups = machines.clusters("a")["groups"]
    assert len(groups) == 1 and len(groups[0]["machines"]) == 2
    assert all(m["owner_id"] == "a" for m in groups[0]["machines"])
    with machines.evidence.connection() as conn:
        conn.execute(
            "UPDATE knowledge_passages SET model='different' WHERE document_id=(SELECT id FROM knowledge_documents WHERE machine_id=(SELECT id FROM machines WHERE owner_id='a' LIMIT 1) LIMIT 1)"
        )
    assert len(machines.clusters("a")["groups"]) == 2


def test_ingestion_failure_retry_and_atomic_publication(tmp_path, monkeypatch):
    machines = MachineStore(tmp_path)
    m = machines.create("a", "A")
    jobs = JobStore(tmp_path)
    job = jobs.enqueue(
        m["id"], "a", "program.st", b"IF alarm THEN stop := TRUE; END_IF;", metadata()
    )

    def unavailable(_):
        raise EmbeddingUnavailable("controlled")

    monkeypatch.setattr("eil.knowledge.embed", unavailable)
    assert jobs.claim() == job["id"]
    process_job(tmp_path, job["id"])
    assert jobs.get(job["id"])["status"] == "failed"
    docs = machines.documents(m["id"], "a")
    assert docs.list() == [] and len(docs.list(all_documents=True)) == 1
    monkeypatch.setattr("eil.knowledge.embed", vector)
    jobs.control(job["id"], "a", "retry")
    jobs.claim()
    process_job(tmp_path, job["id"])
    assert jobs.get(job["id"])["status"] == "completed"
    assert len(docs.list()) == 1 and jobs.get(job["id"])["content"] == b""
    with pytest.raises(EvidenceConflict):
        jobs.control(job["id"], "a", "retry")


def test_cancel_claim_restart_and_queue_limits(tmp_path, monkeypatch):
    m = MachineStore(tmp_path).create("a", "A")
    jobs = JobStore(tmp_path)
    job = jobs.enqueue(m["id"], "a", "a.txt", b"demo", metadata())
    jobs.control(job["id"], "a", "cancel")
    assert jobs.claim() is None
    jobs.control(job["id"], "a", "retry")
    assert jobs.claim() == job["id"]
    with pytest.raises(EvidenceNotFound):
        jobs.control(job["id"], "b", "cancel")
    monkeypatch.setattr(IngestionService, "loop", lambda self: None)
    service = IngestionService(tmp_path).start()
    service.close()
    assert jobs.get(job["id"])["status"] == "interrupted"
    for n in range(4):
        jobs.enqueue(m["id"], "a", f"{n}.txt", b"demo", metadata())
    with pytest.raises(EvidenceConflict):
        jobs.control(job["id"], "a", "retry")


def test_batched_pdf_preserves_original_pages_and_rejects_oversize(tmp_path, monkeypatch):
    m = MachineStore(tmp_path).create("a", "A")
    jobs = JobStore(tmp_path)
    job = jobs.enqueue(m["id"], "a", "a.pdf", b"%PDF-fixture", metadata())
    calls = []

    def convert(content, *, page_range, container_name):
        calls.append(page_range)
        return {
            "total_page_count": 21,
            "chunks": [
                {"page": p, "text": f"Page {p}"}
                for p in range(page_range[0], min(21, page_range[1]) + 1)
            ],
        }

    monkeypatch.setattr("eil.isolated_pdf.convert", convert)
    result = parse_batches(b"%PDF-fixture", jobs, job["id"])
    assert calls == [(1, 20), (21, 21)] and result["chunks"][-1]["page"] == 21
    monkeypatch.setattr(
        "eil.isolated_pdf.convert", lambda *a, **kw: {"total_page_count": 201, "chunks": []}
    )
    with pytest.raises(ValueError):
        parse_batches(b"%PDF-fixture", jobs, job["id"])


def test_machine_api_owner_boundary_and_reviewed_purge(tmp_path):
    app = create_app(lambda: RunService(tmp_path, worker_target=controlled_worker))
    with TestClient(app, base_url="http://127.0.0.1") as client:
        owner = sign_in(client)
        m = client.post("/api/machines", json={"name": "Demo"}).json()
        doc = source(MachineStore(tmp_path).documents(m["id"], owner.id))
        assert client.get(f"/api/library/documents/{doc['id']}/file").status_code == 404
        endpoint = f"/api/machines/{m['id']}/sources/{doc['id']}"
        assert client.get(endpoint + "/preview").json()["static_review"]
        payload = {
            "sha256": doc["sha256"],
            "confirmation": "PERMANENTLY DELETE UNREFERENCED SOURCE",
        }
        assert client.post(endpoint + "/purge", json=payload).status_code == 409
        assert client.post(endpoint + "/availability", json={"active": False}).status_code == 200
        assert client.post(endpoint + "/purge", json=payload).status_code == 200
        assert client.get(endpoint + "/preview").status_code == 404
