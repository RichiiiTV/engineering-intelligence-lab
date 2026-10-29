import asyncio
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, ToolMessage
from mcp.types import Tool, ToolAnnotations

from eil.agent import build_agent
from eil.api import create_app
from eil.case_tools import case_tools
from eil.drafts import DraftStore
from eil.mock_mcp import (
    APPROVED_SCHEMA,
    TOOL_NAME,
    approved_tool,
    call_mock_tool,
    read_mock_station_context,
)
from eil.runs import RunConflict, RunStore
from eil.service import RunService
from tests.evidence_fixtures import CSV_BYTES
from tests.fakes import controlled_worker
from tests.test_agent import call, make_model


def case_run(tmp_path):
    from eil.evidence import EvidenceStore

    evidence = EvidenceStore(tmp_path)
    case = evidence.create_case("M4 synthetic case")
    evidence.ingest(case["id"], "inspection.csv", CSV_BYTES)
    store = RunStore(tmp_path)
    run = store.create("Compare the stations", case_id=case["id"])
    store.claim()
    store.finish(run["id"], "completed", result={"answer": "S03 changed most; cause unknown."})
    return store, case, run


def test_real_mcp_sdk_memory_handshake_list_and_call():
    observation = asyncio.run(call_mock_tool(TOOL_NAME, {"station_id": "S03"}))
    assert observation["synthetic"] is True
    assert observation["station_id"] == "S03"
    assert "illumination" in observation["note"]
    assert "Not a case citation" in observation["uncertainty"]


@pytest.mark.parametrize(
    "name,args",
    [
        ("write_settings", {"station_id": "S03"}),
        (TOOL_NAME, {"station_id": "../../secret"}),
        (TOOL_NAME, {"station_id": "S03", "url": "http://company.example"}),
    ],
)
def test_mcp_rejects_unreviewed_tool_station_and_arguments(name, args):
    with pytest.raises(ValueError):
        asyncio.run(call_mock_tool(name, args))


def test_readonly_annotation_cannot_authorize_a_different_tool_or_schema():
    assert approved_tool(Tool(name=TOOL_NAME, inputSchema=APPROVED_SCHEMA))
    assert not approved_tool(
        Tool(
            name="execute",
            inputSchema=APPROVED_SCHEMA,
            annotations=ToolAnnotations(readOnlyHint=True),
        )
    )
    assert not approved_tool(
        Tool(
            name=TOOL_NAME,
            inputSchema={
                **APPROVED_SCHEMA,
                "additionalProperties": True,
            },
        )
    )


def test_mcp_executes_inside_real_deep_agent_without_write_tools(tmp_path):
    import json

    store, case, run = case_run(tmp_path)
    tools = [
        *case_tools(tmp_path, case["id"], store.get(run["id"])["source_ids"]),
        read_mock_station_context,
    ]
    model = make_model(
        call("read_mock_station_context", {"station_id": "S03"}),
        AIMessage(content="Synthetic mock context only; verify case evidence."),
    )
    result = build_agent(model=model, evidence_tools=tools).invoke(
        {"messages": [{"role": "user", "content": "Read optional mock context"}]},
        {"configurable": {"thread_id": "m4-mcp"}, "recursion_limit": 10},
    )
    observation = next(m for m in result["messages"] if isinstance(m, ToolMessage))
    assert json.loads(observation.content)["source"] == "eil-synthetic-maintenance-v1"
    assert all("read_mock_station_context" in names for names in model.bound_names)
    assert not any(
        {"execute", "save_report_draft", "write_file"} & names for names in model.bound_names
    )


def test_draft_approval_is_content_bound_durable_idempotent_and_atomic(tmp_path):
    store, case, run = case_run(tmp_path)
    drafts = DraftStore(store)
    proposal = drafts.propose(run["id"], "Review draft", "Finding <script>untrusted text</script>")
    assert drafts.drafts(case["id"]) == []
    with pytest.raises(RunConflict, match="review it again"):
        drafts.decide(proposal["id"], "approve", "0" * 64)
    assert drafts.get(proposal["id"])["status"] == "pending"

    def approve(_):
        return DraftStore(RunStore(tmp_path)).decide(proposal["id"], "approve", proposal["sha256"])

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(approve, range(2)))
    assert results[0]["draft_id"] == results[1]["draft_id"]
    saved = DraftStore(RunStore(tmp_path)).drafts(case["id"])
    assert len(saved) == 1 and saved[0]["body"] == proposal["body"]
    assert len([e for e in store.events(run["id"]) if e["type"] == "approval_decided"]) == 1
    with pytest.raises(RunConflict, match="already been decided"):
        drafts.decide(proposal["id"], "reject", proposal["sha256"])


def test_reject_never_saves_and_proposals_require_completed_case(tmp_path):
    store, case, run = case_run(tmp_path)
    drafts = DraftStore(store)
    p = drafts.propose(run["id"], "Draft", "Hypothesis; not a proven cause.")
    assert drafts.decide(p["id"], "reject", p["sha256"])["status"] == "rejected"
    assert drafts.drafts(case["id"]) == []
    queued = store.create("Question", case_id=case["id"])
    with pytest.raises(RunConflict):
        drafts.propose(queued["id"], "Draft", "Body")
    with pytest.raises(ValueError):
        drafts.propose(run["id"], "   ", "Body")


def test_m4_api_approval_filter_origin_and_sample_boundaries(tmp_path):
    store, case, run = case_run(tmp_path)
    app = create_app(lambda: RunService(tmp_path, worker_target=controlled_worker))
    with TestClient(app) as client:
        assert client.get("/api/integrations/mock-mcp").json()["enabled_by_default"] is False
        assert (
            client.get("/api/investigations", params={"case_id": case["id"]}).json()[
                "investigations"
            ][0]["id"]
            == run["id"]
        )
        other = client.post("/api/cases", json={"title": "Other"}).json()["id"]
        assert (
            client.get("/api/investigations", params={"case_id": other}).json()["investigations"]
            == []
        )
        assert (
            client.post(
                "/api/cases", json={"title": "Attack"}, headers={"Origin": "https://evil.example"}
            ).status_code
            == 403
        )
        p = client.post(
            f"/api/investigations/{run['id']}/draft-proposals",
            json={"title": "Draft", "body": "Review findings."},
        )
        assert p.status_code == 201
        proposal = p.json()
        assert client.get(f"/api/cases/{case['id']}/drafts").json()["drafts"] == []
        assert client.get(f"/api/cases/{other}/drafts").json()["proposals"] == []
        assert (
            client.post(
                f"/api/approvals/{proposal['id']}/decision",
                json={"decision": "approve", "expected_sha256": "0" * 64},
            ).status_code
            == 409
        )
        assert (
            client.post(
                f"/api/approvals/{proposal['id']}/decision",
                json={"decision": "approve", "expected_sha256": proposal["sha256"]},
            ).status_code
            == 200
        )
        assert len(client.get(f"/api/cases/{case['id']}/drafts").json()["drafts"]) == 1
        assert client.get("/api/examples/inspection.csv").content == CSV_BYTES
        assert client.get("/api/examples/not-allowed").status_code == 422
        assert client.get("/api/no-such-endpoint").status_code == 404


def test_mcp_option_is_frozen_in_run_record(tmp_path):
    store, case, _ = case_run(tmp_path)
    run = store.create("Compare", case_id=case["id"], use_mock_mcp=True)
    assert RunStore(tmp_path).get(run["id"])["use_mock_mcp"] is True
    with pytest.raises(ValueError, match="case-backed"):
        store.create("No case", use_mock_mcp=True)


def test_changed_mcp_catalog_fails_closed_without_dispatch(monkeypatch):
    import json

    from mcp.server.fastmcp import FastMCP

    server = FastMCP("tampered-test-only")
    calls = []

    @server.tool(annotations=ToolAnnotations(readOnlyHint=True))
    def write_settings(station_id: str) -> dict:
        calls.append(station_id)
        return {"unreviewed": True}

    monkeypatch.setattr("eil.mock_mcp.mock_server", lambda: server)
    response = json.loads(read_mock_station_context("S03"))
    assert "unavailable" in response["error"]
    assert calls == []


def test_frontend_serving_preserves_api_errors_and_csp_scope(tmp_path, monkeypatch):
    monkeypatch.setattr("eil.api.ROOT", tmp_path)
    build = tmp_path / "frontend" / "dist"
    (build / "assets").mkdir(parents=True)
    (build / "index.html").write_text("<!doctype html><title>EIL test</title>")
    (build / "assets" / "test.js").write_text("console.log('local build')")
    app = create_app(lambda: RunService(tmp_path / "state", worker_target=controlled_worker))
    with TestClient(app) as client:
        assert client.get("/").status_code == 200
        assert "script-src 'self'" in client.get("/").headers["content-security-policy"]
        assert client.get("/assets/test.js").status_code == 200
        assert "content-security-policy" not in client.get("/docs").headers
        assert client.get("/api/does-not-exist").status_code == 404
        assert client.get("/backend/src/eil/settings.py").status_code == 404
        (build / "index.html").unlink()
        assert client.get("/").status_code == 503
