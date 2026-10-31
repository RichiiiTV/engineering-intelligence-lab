import hashlib
import json
from pathlib import Path

from fastapi.testclient import TestClient

from eil.api import create_app
from eil.auth import COOKIE, AuthStore
from eil.ingestion import IngestionService, JobStore
from eil.service import RunService
from tests.auth_helpers import PASSWORD, sign_in
from tests.fakes import controlled_worker

PACK = Path(__file__).resolve().parents[1] / "data/public-machine-packs/voron-2.4-v1"


def test_voron_source_snapshots_and_full_license_match_the_manifest():
    manifest = json.loads((PACK / "manifest.json").read_text(encoding="utf-8"))
    uploaded = (PACK / manifest["upload"]["filename"]).read_bytes()
    assert hashlib.sha256(uploaded).hexdigest() == manifest["upload"]["sha256"]
    assert len(uploaded) == manifest["upload"]["bytes"] < 256 * 1024
    assert manifest["upload"]["data_policy"] == "licensed-public"
    assert manifest["license"] == "GPL-3.0" and len(manifest["sources"]) == 5
    for item in manifest["sources"]:
        raw = (PACK / item["filename"]).read_bytes()
        assert len(raw) == item["bytes"] and hashlib.sha256(raw).hexdigest() == item["sha256"]
        assert hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest() == item["git_blob_sha"]
        assert item["repository"] in {"VoronDesign/Voron-2", "VoronDesign/Voron-Documentation"}
        assert len(item["commit"]) == 40 and item["commit"] in item["source_url"]
        assert item["url"].startswith("https://raw.githubusercontent.com/VoronDesign/")
        assert raw in uploaded, "The publication must retain original bodies and the full license"
    assert b"GNU GENERAL PUBLIC LICENSE" in uploaded and b"Version 3, 29 June 2007" in uploaded
    assert b"Machine/product family: Voron 2.4" in uploaded


def test_public_machine_upload_keeps_attribution_and_rejects_member_or_oversized_notes(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(IngestionService, "start", lambda self: self)
    app = create_app(lambda: RunService(tmp_path, worker_target=controlled_worker))
    with TestClient(app, base_url="http://127.0.0.1") as client:
        admin = sign_in(client)
        note = "GPL-3.0; Voron Design; pinned source URLs and full license included."
        response = client.post(
            "/api/admin/machine-knowledge/uploads",
            data={"authorized": "true", "data_policy": "licensed-public", "license_note": note},
            files={"file": ("manual.md", b"# Licensed public test material")},
        )
        assert response.status_code == 202, response.text
        job = JobStore(tmp_path).get(response.json()["id"])
        assert job["metadata"]["data_policy"] == "licensed-public"
        assert job["metadata"]["license_note"] == note
        bad = client.post(
            "/api/admin/machine-knowledge/uploads",
            data={
                "authorized": "true",
                "data_policy": "licensed-public",
                "license_note": "x" * 1001,
            },
            files={"file": ("manual.md", b"bounded test material")},
        )
        assert bad.status_code == 422
        auth = AuthStore(tmp_path)
        auth.add_user(admin, "member", PASSWORD)
        token, _ = auth.login("member", PASSWORD)
        client.cookies.clear()
        client.cookies.set(COOKIE, token)
        forbidden = client.post(
            "/api/admin/machine-knowledge/uploads",
            data={"authorized": "true", "data_policy": "licensed-public", "license_note": note},
            files={"file": ("manual.md", b"bounded test material")},
        )
        assert forbidden.status_code == 403
