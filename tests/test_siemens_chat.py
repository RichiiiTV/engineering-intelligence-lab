import json
from typing import ClassVar

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import StructuredTool
from langchain_ollama import ChatOllama

from eil.api import create_app
from eil.benchmark import fixture_case
from eil.execution import execute_run
from eil.exports import export_investigation
from eil.runs import RunStore
from eil.service import RunService
from eil.siemens_chat import reference_tool
from tests.auth_helpers import sign_in

PUBLIC = "S7-1500 OB1 cycle time documentation"
REQUEST = "11111111-1111-4111-8111-111111111111"


def public_response(question):
    return {
        "request_id": REQUEST,
        "question": question,
        "summary": "Find cycle timing in the public manual.",
        "summary_verified": False,
        "connection_verified": True,
        "retrieved_at": "2026-10-29T10:00:00Z",
        "server_version": "test",
        "sources": [
            {
                "title": "Cycle manual",
                "url": "https://support.industry.siemens.com/cs/ww/en/view/59193558",
                "description": "Public cycle timing reference.",
                "kind": "content",
            }
        ],
    }


class ChatProbe(ChatOllama):
    catalogs: ClassVar[list] = []
    skip_first_lookup: bool = False
    omit_first_reference: bool = False

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.catalogs.append({t["function"]["name"] for t in kwargs.get("tools", [])})
        observation = next(
            (
                m
                for m in messages
                if isinstance(m, ToolMessage) and m.name == "read_siemens_reference"
            ),
            None,
        )
        calls = []
        if self.skip_first_lookup and not any(isinstance(m, AIMessage) for m in messages):
            content = "An answer before checking documentation."
        elif observation is None:
            calls = [
                {"name": "read_siemens_reference", "args": {}, "id": "lookup", "type": "tool_call"}
            ]
            content = ""
        else:
            data = json.loads(observation.text)
            refs = data.get("references", [])
            content = "A public reference to review. " + (
                f"[{refs[0]['citation_id']}]"
                if refs
                else "Siemens is unavailable; technical claims could not be verified."
            )
            if self.omit_first_reference and not any(
                "Source references:" in getattr(m, "text", "") for m in messages
            ):
                content = "A public reference to review, without its citation yet."
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


@pytest.mark.parametrize("with_case", [False, True])
def test_normal_graph_lookup_is_bound_budgeted_exported_and_case_scoped(
    tmp_path, monkeypatch, with_case
):
    sent = []

    async def search(question):
        sent.append(question)
        return public_response(question)

    monkeypatch.setattr("eil.siemens_mcp.search", search)
    case = fixture_case(tmp_path, "injection") if with_case else None
    store = RunStore(tmp_path)
    run = store.create(
        "PRIVATE case details must never become the query",
        case_id=case["id"] if case else None,
        siemens={"question": PUBLIC, "tia_version": "V20"},
    )
    store.claim()
    ChatProbe.catalogs = []
    execute_run(tmp_path, run["id"], model=ChatProbe(model="offline", skip_first_lookup=True))
    saved = store.get(run["id"])
    assert saved["status"] == "completed", saved["error"]
    assert sent == [PUBLIC + " Product context: tia_version=V20"]
    assert "PRIVATE" not in sent[0] and "COMPROMISED_EIL" not in sent[0]
    assert saved["tool_calls"] == 1 and saved["model_calls"] == 3 and saved["tokens"] == 300
    assert all("read_siemens_reference" in c for c in ChatProbe.catalogs)
    assert not any(
        c & {"execute", "read_file", "ls", "compare_station_performance", "inspect_station"}
        for c in ChatProbe.catalogs
    )
    report = export_investigation(store, run["id"])
    assert report["integrations"]["siemens"]["connection_verified"]
    assert report["external_references"][0]["cited_in_answer"]
    assert report["external_reference_checks"]["unresolved"] == []
    assert report["integrations"]["siemens"]["summary_verified"] is False
    if not case:
        assert report["source_snapshot"] == [] and report["verified_evidence"]["comparisons"] == []
        assert saved["chat_mode"] is True
    # The snapshot is outside the case evidence store and no subsequent request
    # can change its query or resend it after checkpoint recovery.
    first = json.loads(reference_tool(tmp_path, run["id"])())
    second = json.loads(reference_tool(tmp_path, run["id"])())
    assert first == second and len(sent) == 1
    assert all("url" not in r for r in first["references"])
    assert not first["manual_content_fetched"] and not first["technical_claims_verified"]
    assert "summary" not in first
    assert all(r["kind"] == "curated_manual" for r in first["references"])


def test_citation_correction_is_metered_and_does_not_repeat_external_search(tmp_path, monkeypatch):
    sent = []

    async def search(question):
        sent.append(question)
        return public_response(question)

    monkeypatch.setattr("eil.siemens_mcp.search", search)
    store = RunStore(tmp_path)
    run = store.create(PUBLIC, siemens={"question": PUBLIC})
    store.claim()
    execute_run(tmp_path, run["id"], model=ChatProbe(model="offline", omit_first_reference=True))
    result = store.get(run["id"])
    assert result["status"] == "completed" and len(sent) == 1
    assert result["model_calls"] == 3 and result["tool_calls"] == 1 and result["tokens"] == 300
    assert export_investigation(store, run["id"])["external_references"][0]["cited_in_answer"]


def test_tool_has_no_query_arguments_and_interrupted_lookup_is_not_resent(tmp_path, monkeypatch):
    store = RunStore(tmp_path)
    run = store.create("Public question", siemens={"question": PUBLIC})
    function = reference_tool(tmp_path, run["id"])
    tool = StructuredTool.from_function(function)
    assert tool.args == {}
    with pytest.raises(TypeError):
        function(query="PRIVATE DATA")

    async def forbidden(*args, **kwargs):
        raise AssertionError("Interrupted query was resent")

    monkeypatch.setattr("eil.siemens_mcp.search", forbidden)
    store.change(run["id"], lambda r, c: r.update(siemens_lookup={"status": "started"}))
    result = json.loads(function())
    assert "nicht automatisch erneut gesendet" in result["error"] and result["references"] == []


def test_budget_prevents_network_and_outage_is_saved_once(tmp_path, monkeypatch):
    from eil.siemens_mcp import SiemensUnavailable

    sent = []

    async def unavailable(question):
        sent.append(question)
        raise SiemensUnavailable("Private upstream detail must not leak")

    monkeypatch.setattr("eil.siemens_mcp.search", unavailable)
    store = RunStore(tmp_path)
    run = store.create(PUBLIC, {"max_tool_calls": 1}, siemens={"question": PUBLIC})
    store.claim()
    store.charge(run["id"], "tool_calls")
    execute_run(tmp_path, run["id"], model=ChatProbe(model="offline"))
    assert store.get(run["id"])["status"] == "budget_exceeded" and not sent
    second = store.create(PUBLIC, siemens={"question": PUBLIC})
    store.claim()
    execute_run(tmp_path, second["id"], model=ChatProbe(model="offline"))
    report = export_investigation(store, second["id"])
    assert store.get(second["id"])["status"] == "completed"
    assert (
        len(sent) == 1
        and report["integrations"]["siemens"]["remote_search_status"] == "unavailable"
    )
    assert report["external_references"][0]["kind"] == "curated_manual"
    assert "Private upstream detail" not in json.dumps(report)
    reference_tool(tmp_path, second["id"])()
    assert len(sent) == 1


def finish_without_model(directory, run_id):
    RunStore(directory).finish(run_id, "completed", result={"answer": "A test answer."})


def test_chat_api_validates_public_payload_and_keeps_owner_access(tmp_path):
    with TestClient(
        create_app(lambda: RunService(tmp_path, worker_target=finish_without_model)),
        base_url="http://127.0.0.1",
    ) as client:
        sign_in(client)
        for siemens in (
            {"question": PUBLIC, "endpoint": "https://evil.invalid"},
            {"question": "x" * 500, "cpu": "CPU 1511"},
            {"question": PUBLIC, "case_history": "PRIVATE"},
        ):
            assert (
                client.post(
                    "/api/investigations",
                    json={"question": PUBLIC, "chat_mode": True, "siemens": siemens},
                ).status_code
                == 422
            )
        created = client.post(
            "/api/investigations",
            json={"question": PUBLIC, "chat_mode": True, "siemens": {"question": PUBLIC}},
        )
        assert created.status_code == 202
        run = created.json()
        assert run["chat_mode"] and run["case_id"] is None and run["source_ids"] == []
        assert client.get("/api/investigations").json()["investigations"][0]["id"] == run["id"]
        client.post(
            "/api/auth/users",
            json={"username": "member", "password": "Synthetic member password!", "role": "member"},
        )
        client.post("/api/auth/logout")
        client.post(
            "/api/auth/login", json={"username": "member", "password": "Synthetic member password!"}
        )
        assert client.get(f"/api/investigations/{run['id']}/export").status_code == 404
        assert client.get("/api/investigations").json()["investigations"] == []
