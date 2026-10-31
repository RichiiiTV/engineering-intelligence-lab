import hashlib
import json
import uuid
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from eil.api import create_app
from eil.catalog_tools import route
from eil.chat import ChatStore
from eil.evidence import EvidenceConflict
from eil.runs import RunStore
from eil.service import RunService
from eil.siemens_routing import automatic_public_query
from tests.auth_helpers import sign_in
from tests.test_chat_backbone import controlled_worker, publish


def test_language_is_frozen_per_answer_and_is_part_of_idempotency(tmp_path):
    runs = RunStore(tmp_path)
    chats = ChatStore(tmp_path)
    service = SimpleNamespace(submit=runs.create)
    request = str(uuid.uuid4())
    question = "S7-1500 error 16#80A1"
    run = chats.submit("a", question, request, service, language="en")
    assert run["language"] == "en" and "Answer in English" in run["siemens"]["question"]
    assert chats.submit("a", question, request, service, language="en")["id"] == run["id"]
    with pytest.raises(EvidenceConflict):
        chats.submit("a", question, request, service, language="de")
    runs.change(run["id"], lambda row, _: row.update(status="paused", tokens=123))
    resumed = runs.control(run["id"], "resume")
    assert resumed["language"] == "en" and resumed["tokens"] == 123
    with pytest.raises(ValueError):
        chats.submit("a", question, str(uuid.uuid4()), service, language="fr")


def test_receipts_from_before_language_preferences_remain_retryable(tmp_path):
    runs = RunStore(tmp_path)
    chats = ChatStore(tmp_path)
    request = str(uuid.uuid4())
    question = "XR7 Fehler E17"
    run = chats.submit("a", question, request, SimpleNamespace(submit=runs.create))
    with chats.evidence.connection() as conn:
        old = json.loads(conn.execute("SELECT document FROM chat_receipts").fetchone()[0])
        old.pop("language")
        old["fingerprint"] = hashlib.sha256(
            json.dumps(
                {"question": question, "conversation_id": None, "files": []}, sort_keys=True
            ).encode()
        ).hexdigest()
        conn.execute("UPDATE chat_receipts SET document=?", (json.dumps(old),))
    repeated = chats.submit("a", question, request, SimpleNamespace(submit=runs.create))
    assert repeated["id"] == run["id"]


def test_english_machine_clarification_preserves_machine_names(tmp_path, monkeypatch):
    publish(tmp_path, "admin", "a.md", "XR7", monkeypatch)
    publish(tmp_path, "admin", "b.md", "AB9", monkeypatch)
    run = RunStore(tmp_path).create(
        "The machine stops", owner_id="a", chat_mode=True, automatic_catalog=True, language="en"
    )
    result = route(tmp_path, run)
    assert result["status"] == "needs_clarification"
    assert result["question"].startswith("Which machine is affected")
    assert "XR7" in result["question"] and "AB9" in result["question"]


def test_api_validates_language_and_passes_it_to_normal_and_advanced_runs(tmp_path):
    app = create_app(lambda: RunService(tmp_path, worker_target=controlled_worker))
    with TestClient(app, base_url="http://127.0.0.1") as client:
        sign_in(client)
        response = client.post(
            "/api/chat/questions",
            data={"question": "A problem", "request_id": str(uuid.uuid4()), "language": "fr"},
        )
        assert response.status_code == 422
        assert client.get("/api/investigations").json()["investigations"] == []
        response = client.post(
            "/api/chat/questions",
            data={"question": "A problem", "request_id": str(uuid.uuid4()), "language": "en"},
        )
        assert response.status_code == 202 and response.json()["language"] == "en"
        app.state.runs.wait(response.json()["id"], timeout=10)
        advanced = client.post(
            "/api/investigations",
            headers={"X-EIL-Language": "en"},
            json={"question": "Explain PLC diagnostics", "chat_mode": True},
        )
        assert advanced.status_code == 202 and advanced.json()["language"] == "en"
        app.state.runs.wait(advanced.json()["id"], timeout=10)
        invalid = client.post(
            "/api/investigations",
            headers={"X-EIL-Language": "fr"},
            json={"question": "A problem", "chat_mode": True},
        )
        assert invalid.status_code == 422


def test_english_siemens_template_remains_canonical_and_bounded():
    query = automatic_public_query("Private line XY: S7-1500 error 16#80A1", language="en")
    assert query and "Answer in English" in query["question"]
    assert "XY" not in json.dumps(query) and "Private" not in json.dumps(query)
    with pytest.raises(ValueError):
        automatic_public_query("S7-1500 error 16#80A1", language="fr")
