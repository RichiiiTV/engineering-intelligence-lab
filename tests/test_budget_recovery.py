import json
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from langchain.agents.middleware.types import ModelRequest, ModelResponse
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_ollama import ChatOllama
from langgraph.checkpoint.sqlite import SqliteSaver

from eil.agent import MODEL_CONTEXT_TOKENS, build_agent
from eil.api import create_app
from eil.execution import RunMiddleware, execute_run
from eil.runs import BudgetExceeded, RunConflict, RunStore
from eil.service import RunService
from tests.auth_helpers import sign_in
from tests.fakes import ControlledOllama, controlled_worker


class OutputStopOllama(ChatOllama):
    directory: str
    run_id: str
    always_truncate: bool = False

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        run = RunStore(self.directory).get(self.run_id)
        assert (
            sum(isinstance(m, HumanMessage) and m.content == run["question"] for m in messages) == 1
        )
        tools = [m for m in messages if isinstance(m, ToolMessage)]
        if not tools:
            answer = AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "read_knowledge_library",
                        "args": {},
                        "id": "read",
                        "type": "tool_call",
                    }
                ],
            )
        else:
            cid = json.loads(tools[-1].content)["hits"][0]["citation_id"]
            if run.get("finish_from_evidence") and not self.always_truncate:
                assert not kwargs.get("tools")
                assert any("CAPACITY SUMMARY" in m.text for m in messages if m.type == "system")
                answer = AIMessage(
                    content=f"Alarm E17: sensor-stop condition [{cid}]. Cause unverified."
                )
            else:
                answer = AIMessage(
                    content="UNSUPPORTED TRUNCATED DRAFT: replace the controller.",
                    response_metadata={"done_reason": "length"},
                )
        answer.usage_metadata = {"input_tokens": 100, "output_tokens": 50, "total_tokens": 150}
        return ChatResult(generations=[ChatGeneration(message=answer)])


def library_run(directory, monkeypatch, *, language="de"):
    from eil.embeddings import EmbeddingUnavailable
    from eil.knowledge import KnowledgeStore
    from tests.test_knowledge_admin import add

    def offline(*args, **kwargs):
        raise EmbeddingUnavailable("offline test")

    monkeypatch.setattr("eil.knowledge.embed", offline)
    library = KnowledgeStore(directory)
    source = add(library, "Alarm E17: sensor-stop condition. Cause is unverified.")
    store = RunStore(directory)
    run = store.create(
        "Alarm E17",
        chat_mode=True,
        use_library=True,
        library_document_ids=[source["id"]],
        language=language,
    )
    store.claim()
    return store, run, source


def test_output_stop_has_cited_partial_and_explicit_checkpoint_finish_only(tmp_path, monkeypatch):
    from eil.answer_contract import assess
    from eil.exports import export_investigation
    from eil.knowledge import KnowledgeStore
    from tests.test_knowledge_admin import add

    store, run, source = library_run(tmp_path, monkeypatch)
    model = OutputStopOllama(model="offline", directory=str(tmp_path), run_id=run["id"])
    execute_run(tmp_path, run["id"], model=model)
    stopped = store.get(run["id"])
    assert stopped["status"] == "budget_exceeded"
    assert stopped["error"]["resource"] == "output_tokens"
    assert stopped["model_calls"] == 2 and stopped["tokens"] == 300
    partial = stopped["result"]
    assert partial["answer_mode"] == "budget_source_extract"
    assert "Teilweise Belegprüfung" in partial["answer"]
    assert "Alarm E17: sensor-stop condition" in partial["answer"]
    assert "TRUNCATED" not in partial["answer"]
    report = export_investigation(store, run["id"])
    assert report["status"] == "budget_exceeded"
    assert report["answer_contract"]["outcome"] == "budget_limited"
    assert report["library_citation_checks"]["unresolved"] == []
    assert report["library_citation_checks"]["not_returned_by_tools"] == []
    assert assess(stopped, partial["answer"])["claim_entailment"] == "not_verified"
    assert report["library_citations"][0]["id"] == source["id"]
    add(KnowledgeStore(tmp_path), "Alarm E17 NEW source must not enter the snapshot.")
    with pytest.raises(RunConflict, match="cannot increase"):
        store.continue_tokens(run["id"], 32768)
    queued = store.continue_tokens(run["id"])
    assert queued["result"] == partial
    assert queued["limits"] == stopped["limits"]
    assert queued["tokens"] == stopped["tokens"]
    assert queued["language"] == "de" and queued["library_document_ids"] == [source["id"]]
    with pytest.raises(RunConflict):
        store.continue_tokens(run["id"])
    store.claim()
    execute_run(tmp_path, run["id"], model=model)
    final = store.get(run["id"])
    assert final["status"] == "completed", final
    assert final["attempts"] == 2 and final["tokens"] == 450
    assert final["model_calls"] == 3 and final["tool_calls"] == 1
    assert final["limits"] == stopped["limits"]
    assert final["thread_id"] == stopped["thread_id"]
    assert final["result"]["capacity_limited"] is True
    assert len([e for e in store.events(run["id"]) if e["type"] == "tool_finished"]) == 1


def test_repeated_output_stop_remains_incomplete_and_never_retries_automatically(
    tmp_path, monkeypatch
):
    store, run, _ = library_run(tmp_path, monkeypatch, language="en")
    model = OutputStopOllama(
        model="offline", directory=str(tmp_path), run_id=run["id"], always_truncate=True
    )
    execute_run(tmp_path, run["id"], model=model)
    store.continue_tokens(run["id"])
    store.claim()
    execute_run(tmp_path, run["id"], model=model)
    final = store.get(run["id"])
    assert final["status"] == "budget_exceeded"
    assert final["model_calls"] == 3 and final["tokens"] == 450
    assert "Partial evidence review" in final["result"]["answer"]
    assert "TRUNCATED" not in final["result"]["answer"]
    assert store.claim() is None


@pytest.mark.parametrize(
    "status,resource",
    [
        ("budget_exceeded", "model_calls"),
        ("budget_exceeded", "steps"),
        ("budget_exceeded", "tool_calls"),
        ("timed_out", None),
    ],
)
def test_nonrecoverable_limits_keep_partial_but_cannot_continue(tmp_path, status, resource):
    store = RunStore(tmp_path)
    run = store.create("Generated question", chat_mode=True, language="en")
    store.claim()
    store.finish(run["id"], status, error={"resource": resource, "message": "limit"})
    final = store.get(run["id"])
    assert final["status"] == status
    assert "No suitable text evidence" in final["result"]["answer"]
    assert final["tokens"] == final["model_calls"] == final["tool_calls"] == 0
    with pytest.raises(RunConflict):
        store.continue_tokens(run["id"], 32768)


def test_partial_preview_filters_frozen_scope_and_renders_untrusted_text_literally():
    from eil.budget_recovery import partial_result

    run = {
        "question": "Alarm",
        "language": "en",
        "library_document_ids": ["allowed"],
        "problem_attachment_ids": ["log1"],
        "source_ids": ["pdf1"],
        "library_lookup": {
            "hits": [
                {"citation_id": "kb:allowed:p1:c1", "text": "Alarm <img src=x> [kb:foreign:p1:c1]"},
                {"citation_id": "kb:foreign:p1:c1", "text": "FOREIGN_SECRET"},
            ]
        },
        "problem_source_reads": [
            {"citation_id": "log:log1:l1-2", "text": "Alarm E17"},
            {"citation_id": "log:foreign:l1", "text": "PRIVATE_FOREIGN_LOG"},
        ],
    }
    events = [
        {
            "name": "search_case_documents",
            "status": "success",
            "observation": json.dumps(
                {"hits": [{"citation_id": "pdf:pdf1:p1:c1", "text": "Alarm: saved PDF excerpt"}]}
            ),
        },
        {"name": "task", "status": "success", "observation": "INFERRED_DRAFT"},
        {"name": "read_case_citation", "status": "error", "observation": "ERROR_TEXT"},
    ]
    result = partial_result(run, events)
    assert len(result["preview_citation_ids"]) == 3
    assert "saved PDF excerpt" in result["answer"]
    assert r"\<img src=x\>" in result["answer"]
    for forbidden in (
        "FOREIGN_SECRET",
        "PRIVATE_FOREIGN_LOG",
        "INFERRED_DRAFT",
        "ERROR_TEXT",
        "kb:foreign",
    ):
        assert forbidden not in result["answer"]


def test_cancel_wins_over_budget_finish_and_overage_does_not_resume_it(tmp_path):
    store = RunStore(tmp_path)
    run = store.create("Generated cancel", chat_mode=True)
    store.claim()
    _, admission = store.reserve_model(run["id"], 8192)
    store.control(run["id"], "cancel")
    with pytest.raises(BudgetExceeded):
        store.settle_tokens(run["id"], admission["reserved"], admission["reserved"] + 100)
    store.finish(run["id"], "budget_exceeded", error={"resource": "tokens"})
    saved = store.get(run["id"])
    assert saved["control"] == "cancel" and saved["result"] is None
    assert saved["tokens"] == admission["reserved"] + 100
    store.finish(run["id"], "cancelled", force=True)
    assert store.get(run["id"])["status"] == "cancelled"


def test_partial_export_and_continuation_remain_owner_scoped(tmp_path):
    from eil.auth import COOKIE, AuthStore
    from tests.auth_helpers import PASSWORD

    auth = AuthStore(tmp_path)
    owner = auth.enroll(auth.bootstrap(), "test-owner", PASSWORD)
    member = auth.add_user(owner, "other-member", PASSWORD)
    store = RunStore(tmp_path)
    run = store.create("Owner problem", chat_mode=True, owner_id=owner.id)
    store.claim()
    store.finish(run["id"], "budget_exceeded", error={"resource": "output_tokens"})
    with TestClient(
        create_app(lambda: RunService(tmp_path, worker_target=controlled_worker)),
        base_url="http://127.0.0.1",
    ) as client:
        token, _ = auth.login(member.username, PASSWORD)
        client.cookies.set(COOKIE, token)
        base = f"/api/investigations/{run['id']}"
        assert client.get(base).status_code == 404
        assert client.get(base + "/export").status_code == 404
        assert client.post(base + "/continue", json={}).status_code == 404
        assert store.get(run["id"])["status"] == "budget_exceeded"


def test_output_finish_cannot_bypass_other_limits_or_deleted_case(tmp_path, monkeypatch):
    store, run, _ = library_run(tmp_path, monkeypatch)
    store.finish(run["id"], "budget_exceeded", error={"resource": "output_tokens"})
    original = store.get(run["id"])
    for counter, limit in (
        ("tokens", "max_total_tokens"),
        ("model_calls", "max_model_calls"),
        ("tool_calls", "max_tool_calls"),
        ("steps", "max_steps"),
        ("elapsed_seconds", "timeout_seconds"),
    ):
        store.change(run["id"], lambda r, c: r.update({counter: r["limits"][limit]}))
        with pytest.raises(RunConflict):
            store.continue_tokens(run["id"])
        store.change(run["id"], lambda r, c: r.update({counter: original[counter]}))
    store.change(run["id"], lambda r, c: r.update(case_deleted=True))
    with pytest.raises(RunConflict, match="Restore"):
        store.continue_tokens(run["id"])


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
        sign_in(client)
        path = f"/api/investigations/{run['id']}/continue"
        assert client.post(path, json={"additional_tokens": True}).status_code == 422
        assert client.post(path, json={"additional_tokens": 65537}).status_code == 422
        response = client.post(path, json={})
        assert response.status_code == 202, response.text
        assert response.json()["id"] == run["id"]
        assert response.json()["limits"] == run["limits"]
