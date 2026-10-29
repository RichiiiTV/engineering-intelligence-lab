from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from langchain.agents.middleware.types import ModelRequest, ModelResponse
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_ollama import ChatOllama
from langgraph.checkpoint.sqlite import SqliteSaver

from eil.agent import MODEL_CONTEXT_TOKENS, build_agent
from eil.api import create_app
from eil.execution import RunMiddleware, execute_run
from eil.runs import BudgetExceeded, RunConflict, RunStore
from eil.service import RunService
from tests.fakes import ControlledOllama, controlled_worker


def stopped_run(directory, *, tokens=23018, maximum=32768):
    store = RunStore(directory)
    run = store.create("case:preserved", {"max_total_tokens": maximum, "max_output_tokens": 2048})
    store.claim()
    store.change(
        run["id"], lambda r, c: r.update(tokens=tokens, model_calls=7, tool_calls=6, steps=13)
    )
    store.finish(
        run["id"],
        "budget_exceeded",
        error={
            "code": "budget_exceeded",
            "message": "tokens budget exhausted; create a new investigation",
        },
    )
    return store, store.get(run["id"])


def test_failed_admission_does_not_spend_a_model_call_or_reset_tokens(tmp_path):
    store = RunStore(tmp_path)
    run = store.create("case:small", {"max_total_tokens": 8192})
    store.claim()
    with pytest.raises(BudgetExceeded) as exc:
        store.reserve_model(run["id"], MODEL_CONTEXT_TOKENS)
    assert exc.value.resource == "tokens"
    saved = store.get(run["id"])
    assert saved["model_calls"] == saved["tokens"] == 0


def test_tail_request_fits_existing_budget_and_preserves_ollama_options(tmp_path):
    store, saved = stopped_run(tmp_path)
    continued = store.continue_tokens(saved["id"])
    assert continued["limits"] == saved["limits"]
    assert all(
        continued[k] == saved[k]
        for k in (
            "id",
            "thread_id",
            "question",
            "tokens",
            "model_calls",
            "tool_calls",
            "steps",
            "source_ids",
        )
    )
    store.claim()
    model = ChatOllama(model="offline", num_ctx=8192, num_predict=2048, temperature=0)
    request = ModelRequest(
        model=model,
        messages=[HumanMessage(content="question")],
        system_message=SystemMessage(content="Keep existing safety instructions."),
        tools=[],
    )

    def handler(actual):
        options = actual.model._chat_params(actual.messages, **actual.model_settings)
        assert options["options"]["num_predict"] == 1558
        assert options["options"]["num_ctx"] == 8192
        assert options["options"]["temperature"] == 0
        assert options["think"] is False
        assert actual.tools == []
        assert "Keep existing safety instructions." in actual.system_message.text
        assert "CAPACITY SUMMARY" in actual.system_message.text
        return ModelResponse(
            result=[
                AIMessage(
                    content="A bounded summary.",
                    usage_metadata={
                        "input_tokens": 4800,
                        "output_tokens": 200,
                        "total_tokens": 5000,
                    },
                )
            ]
        )

    RunMiddleware(store, saved["id"]).wrap_model_call(request, handler)
    after = store.get(saved["id"])
    assert after["tokens"] == 28018 < 32768
    assert after["model_calls"] == 8 and after["budget_summary"] is True
    assert model.num_predict == 2048  # The original adapter was not mutated.
    started = next(e for e in store.events(saved["id"]) if e["type"] == "model_started")
    assert started["data"]["reserved_tokens"] == 9750


def test_continuation_can_extend_once_without_resetting_counters_and_is_hard_capped(tmp_path):
    store, run = stopped_run(tmp_path, tokens=32768)
    with pytest.raises(RunConflict, match="additional"):
        store.continue_tokens(run["id"])
    extended = store.continue_tokens(run["id"], 32768)
    assert extended["tokens"] == run["tokens"]
    assert extended["model_calls"] == run["model_calls"]
    assert extended["limits"]["max_total_tokens"] == 65536
    assert extended["initial_limits"] == run["limits"]
    with pytest.raises(RunConflict):
        store.continue_tokens(run["id"], 32768)
    capped_store, capped = stopped_run(tmp_path / "capped", tokens=131072, maximum=131072)
    with pytest.raises(RunConflict, match="131,072"):
        capped_store.continue_tokens(capped["id"], 32768)
    assert capped_store.get(capped["id"])["limits"]["max_total_tokens"] == 131072


def test_concurrent_continuations_queue_once_and_cannot_bypass_other_limits(tmp_path):
    store, run = stopped_run(tmp_path)

    def attempt(_):
        try:
            return RunStore(tmp_path).continue_tokens(run["id"])["status"]
        except RunConflict:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(attempt, range(2))) == ["conflict", "queued"]
    assert len([e for e in store.events(run["id"]) if e["type"] == "investigation_continued"]) == 1
    other_store, other = stopped_run(tmp_path / "other")
    other_store.change(
        other["id"], lambda r, c: r.update(model_calls=r["limits"]["max_model_calls"])
    )
    with pytest.raises(RunConflict, match="Another run limit"):
        other_store.continue_tokens(other["id"], 32768)


def test_actual_checkpoint_continues_without_repeating_question_or_completed_tool(tmp_path):
    store = RunStore(tmp_path)
    run = store.create("case:checkpoint", {"max_output_tokens": 2048})
    store.claim()
    model = ControlledOllama(model="offline", directory=str(tmp_path), run_id=run["id"])
    config = {"configurable": {"thread_id": run["id"]}}
    with SqliteSaver.from_conn_string(str(tmp_path / "checkpoints.sqlite3")) as saver:
        graph = build_agent(
            model=model, checkpointer=saver, middleware=[RunMiddleware(store, run["id"])]
        )
        state = graph.invoke(
            {"messages": [HumanMessage(content=run["question"])]}, config, interrupt_after=["tools"]
        )
        assert any(isinstance(m, ToolMessage) for m in state["messages"])
    store.change(run["id"], lambda r, c: r.update(tokens=23018, model_calls=7))
    store.finish(
        run["id"],
        "budget_exceeded",
        error={
            "message": "tokens budget exhausted; create a new investigation",
            "code": "budget_exceeded",
        },
    )
    store.continue_tokens(run["id"])
    store.claim()
    execute_run(tmp_path, run["id"], model=model)
    final = store.get(run["id"])
    assert final["status"] == "completed", final
    assert final["thread_id"] == run["id"] and final["attempts"] == 2
    assert final["model_calls"] == 8 and final["tool_calls"] == 1
    assert final["result"]["capacity_limited"] is True
    assert "S03" in final["result"]["answer"]
    assert len([e for e in store.events(run["id"]) if e["type"] == "tool_finished"]) == 1


def test_continuation_keeps_case_snapshot_when_new_sources_arrive(tmp_path):
    from eil.evidence import EvidenceStore
    from tests.evidence_fixtures import CSV_BYTES

    evidence = EvidenceStore(tmp_path)
    case = evidence.create_case("case")
    original = evidence.ingest(case["id"], "first.csv", CSV_BYTES)
    store = RunStore(tmp_path)
    run = store.create("Compare", case_id=case["id"])
    store.claim()
    store.change(run["id"], lambda r, c: r.update(tokens=23018))
    store.finish(
        run["id"], "budget_exceeded", error={"message": "token stop", "resource": "tokens"}
    )
    evidence.ingest(case["id"], "second.csv", CSV_BYTES.replace(b"ROW-00001", b"ROW-NEW01"))
    assert store.continue_tokens(run["id"])["source_ids"] == [original["id"]]


def test_continuation_api_validates_and_handles_legacy_token_stop(tmp_path):
    store, run = stopped_run(tmp_path)
    with TestClient(
        create_app(lambda: RunService(tmp_path, worker_target=controlled_worker)),
        base_url="http://127.0.0.1",
    ) as client:
        path = f"/api/investigations/{run['id']}/continue"
        assert client.post(path, json={"additional_tokens": True}).status_code == 422
        assert client.post(path, json={"additional_tokens": 65537}).status_code == 422
        response = client.post(path, json={})
        assert response.status_code == 202, response.text
        assert response.json()["id"] == run["id"]
        assert response.json()["limits"] == run["limits"]
