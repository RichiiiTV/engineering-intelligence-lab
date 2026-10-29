import asyncio
import hashlib

import pytest
from fastapi.testclient import TestClient

from eil.api import create_app
from eil.pdf_ingest import MAX_PDF_BYTES, PDFUnavailable
from eil.service import RunService
from eil.uploads import UploadBodyLimit
from tests.evidence_fixtures import CSV_BYTES, PDF_BYTES, fixture_pdf_parser
from tests.fakes import controlled_worker


@pytest.fixture
def client(tmp_path):
    app = create_app(lambda: RunService(tmp_path, worker_target=controlled_worker))
    app.state.pdf_parser = fixture_pdf_parser
    with TestClient(app, base_url="http://127.0.0.1") as client:
        yield client


def new_case(client, title="Synthetic case"):
    response = client.post("/api/cases", json={"title": title})
    assert response.status_code == 201
    return response.json()["id"]


def upload(client, case_id, name, content):
    return client.post(
        f"/api/cases/{case_id}/sources",
        data={"data_policy": "synthetic"},
        files={"file": (name, content, "application/octet-stream")},
    )


def test_upload_search_compare_investigate_export_and_download(client):
    case = new_case(client)
    pdf = upload(client, case, "note.pdf", PDF_BYTES)
    csv = upload(client, case, "measurements.csv", CSV_BYTES)
    assert pdf.status_code == csv.status_code == 201
    assert csv.json()["row_count"] == 336
    hits = client.get(f"/api/cases/{case}/search", params={"q": "S03 exposure setpoint"}).json()[
        "hits"
    ]
    assert hits[0]["page"] == 2
    comparison = client.get(f"/api/cases/{case}/sources/{csv.json()['id']}/comparison").json()
    assert comparison["ranking"][0]["delta_percentage_points"] == 12.5021
    source = client.get(f"/api/cases/{case}/sources/{pdf.json()['id']}/file")
    assert source.content == PDF_BYTES
    assert "attachment" in source.headers["content-disposition"]
    assert hashlib.sha256(source.content).hexdigest() == pdf.json()["sha256"]
    resolved = client.get(f"/api/cases/{case}/citations/{hits[0]['citation_id']}")
    assert resolved.status_code == 200
    response = client.post(
        "/api/investigations", json={"question": "Investigate this case", "case_id": case}
    )
    assert response.status_code == 202
    run = client.app.state.runs.wait(response.json()["id"], timeout=25)
    assert run["status"] == "completed", run
    report = client.get(f"/api/investigations/{run['id']}/export")
    assert report.status_code == 200
    assert report.json()["source_snapshot"][0]["case_id"] == case
    assert report.json()["citation_checks"]["unresolved"] == []
    assert len(client.get(f"/api/cases/{case}").json()["sources"]) == 2


def test_case_ids_cannot_address_other_cases_sources_or_files(client):
    a, b = new_case(client, "A"), new_case(client, "B")
    source = upload(client, a, "data.csv", CSV_BYTES).json()["id"]
    for suffix in ("file", "comparison"):
        assert client.get(f"/api/cases/{b}/sources/{source}/{suffix}").status_code == 404
    assert client.get(f"/api/cases/{b}/citations/csv:{source}:r0").status_code == 404
    assert client.get(f"/api/cases/{b}/search", params={"q": "S03"}).json()["hits"] == []
    assert client.get("/api/cases/not-a-path").status_code == 404
    assert (
        client.post(
            "/api/investigations", json={"question": "Empty case", "case_id": b}
        ).status_code
        == 409
    )


def test_policy_signature_path_schema_and_duplicate_errors_are_controlled(client):
    case = new_case(client)
    response = client.post(f"/api/cases/{case}/sources", files={"file": ("a.csv", CSV_BYTES)})
    assert response.status_code == 422  # explicit demo-data policy is required
    assert upload(client, case, "../secret.csv", CSV_BYTES).status_code == 422
    assert upload(client, case, "a.pdf", b"Not a PDF").status_code == 422
    assert upload(client, case, "a.csv", b"wrong,headers\na,b").status_code == 422
    assert upload(client, case, "a.exe", b"binary").status_code == 422
    assert upload(client, case, "a.csv", CSV_BYTES).status_code == 201
    assert upload(client, case, "renamed.csv", CSV_BYTES).status_code == 409
    assert len(client.get(f"/api/cases/{case}").json()["sources"]) == 1
    assert client.post("/api/cases", json={"title": "   "}).status_code == 422
    assert client.post("/api/cases", json={"title": "A", "path": "../../host"}).status_code == 422


def test_pdf_unavailable_and_oversized_body_fail_before_persistence(client):
    case = new_case(client)

    def missing(content):
        raise PDFUnavailable("Prefetch Docling models")

    client.app.state.pdf_parser = missing
    response = upload(client, case, "a.pdf", PDF_BYTES)
    assert response.status_code == 503
    assert "Prefetch" in response.json()["detail"]
    huge = b"x" * (MAX_PDF_BYTES + 65537)
    assert upload(client, case, "large.pdf", huge).status_code == 413
    assert client.get(f"/api/cases/{case}").json()["sources"] == []


def test_chunked_upload_limit_does_not_trust_content_length():
    statuses, app_called = [], []

    async def inner(scope, receive, send):
        app_called.append(True)

    chunk = b"a" * (1024 * 1024)
    packets = [{"type": "http.request", "body": chunk, "more_body": True}] * 12

    async def receive():
        return packets.pop(0)

    async def send(message):
        if message["type"] == "http.response.start":
            statuses.append(message["status"])

    scope = {"type": "http", "method": "POST", "path": "/api/cases/known/sources", "headers": []}
    asyncio.run(UploadBodyLimit(inner)(scope, receive, send))
    assert statuses == [413]
    assert app_called == []
