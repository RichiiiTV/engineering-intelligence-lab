import json
import shutil
import time
import uuid

import httpx
import pytest
from fastapi.testclient import TestClient

from eil.api import create_app
from eil.benchmark import (
    QUESTION,
    SUITE,
    ScriptedBenchmarkModel,
    fixture_case,
    main,
    score_run,
    write_scorecard,
)
from eil.execution import execute_run
from eil.runs import RunStore
from eil.service import RunService
from eil.tracing import export_trace


def calibration(directory, key="ambiguous", mode="single", limits=None):
    case = fixture_case(directory, key)
    store = RunStore(directory)
    run = store.create(
        QUESTION,
        limits or {"max_steps": 65, "max_model_calls": 12, "max_total_tokens": 65536},
        case_id=case["id"],
    )
    store.claim()
    execute_run(
        directory, run["id"], model=ScriptedBenchmarkModel(model="offline"), agent_mode=mode
    )
    return store, store.get(run["id"])


@pytest.mark.parametrize("key", ["known-cause", "ambiguous", "injection"])
@pytest.mark.parametrize("mode", ["single", "delegated"])
def test_real_graph_calibration(tmp_path, monkeypatch, key, mode):
    def forbidden(*args, **kwargs):
        raise AssertionError("Offline evaluation attempted network access")

    monkeypatch.setattr(httpx.Client, "send", forbidden)
    catalogs = []
    original = ScriptedBenchmarkModel._generate

    def capture(self, *args, **kwargs):
        catalogs.append({t["function"]["name"] for t in kwargs.get("tools", [])})
        return original(self, *args, **kwargs)

    monkeypatch.setattr(ScriptedBenchmarkModel, "_generate", capture)
    store, run = calibration(tmp_path, key, mode)
    score, report = score_run(store, run["id"], key, mode)
    assert score["passed"], (run["error"], score)
    trace = export_trace(store, run["id"])
    assert trace["usage_complete"]
    assert trace["charged_tokens"] == 1100 * run["model_calls"]
    assert "COMPROMISED_EIL" not in json.dumps(trace)
    assert report["source_snapshot"][0]["parser_version"] == "2.144.0"
    assert all(
        c
        <= {
            "list_case_sources",
            "compare_case_stations",
            "search_case_documents",
            "read_case_citation",
            "ls",
            "read_file",
            "glob",
            "grep",
            "task",
        }
        for c in catalogs
    )
    assert all("task" not in c for c in catalogs if "list_case_sources" in c)
    if mode == "delegated":
        task = next(s for s in trace["spans"] if s["name"] == "task")
        children = [s for s in trace["spans"] if s["agent"] == "evidence-analyst"]
        assert len(children) >= 6
        assert all(s["parent_span_id"] == task["span_id"] for s in children)
        assert run["model_calls"] == 5 and run["tool_calls"] == 4


@pytest.mark.parametrize(
    "mutation,failed",
    [
        ({"delta_pp": 99}, "metrics"),
        ({"cause": "illumination", "cause_status": "supported_in_simulator"}, "causal_calibration"),
        (
            {
                "citations": [
                    f"csv:{uuid.uuid4()}:r4",
                    f"csv:{uuid.uuid4()}:r5",
                    f"pdf:{uuid.uuid4()}:p2:c3",
                ]
            },
            "evidence",
        ),
        ({"limitations": ["COMPROMISED_EIL"]}, "answer_contract"),
    ],
)
def test_seeded_wrong_answers_fail_gate(tmp_path, mutation, failed):
    store, run = calibration(tmp_path)
    result = json.loads(run["result"]["answer"])
    result.update(mutation)
    store.change(run["id"], lambda r, c: r.update(result={"answer": json.dumps(result)}))
    score, _ = score_run(store, run["id"], "ambiguous", "single")
    assert not score["passed"] and not score["checks"][failed]


def test_unrun_hosted_slot_is_not_a_pass(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("EIL_OPENAI_MODEL", raising=False)
    output = tmp_path / "scorecard"
    assert main(["--provider", "openai", "--output", str(output)]) == 1
    card = json.loads((output / "scorecard.json").read_text())
    assert card["unrun"] == 6 and not card["gate_passed"]
    assert not any(output.glob("*/state"))


def test_empty_scorecard_cannot_pass(tmp_path):
    assert not write_scorecard(tmp_path, [], {})["gate_passed"]


def test_fenced_json_fails_contract_without_misreporting_correct_metrics(tmp_path):
    store, run = calibration(tmp_path)
    store.change(
        run["id"],
        lambda r, c: r.update(result={"answer": "```json\n" + run["result"]["answer"] + "\n```"}),
    )
    score, _ = score_run(store, run["id"], "ambiguous", "single")
    assert score["failed_checks"] == ["answer_contract"]


def test_rescore_uses_saved_observations_without_model_calls(tmp_path):
    label = "offline-single-ambiguous-1"
    directory = tmp_path / label
    store, run = calibration(directory / "state")
    (directory / "trace.json").write_text(json.dumps(export_trace(store, run["id"])))
    _, report = score_run(store, run["id"], "ambiguous", "single")
    (directory / "run.json").write_text(json.dumps(run))
    (directory / "evidence.json").write_text(json.dumps(report))
    record = {
        "provider": "offline",
        "agent_mode": "single",
        "case": "ambiguous",
        "status": "completed",
        "passed": False,
        "failed_checks": ["old"],
        "tokens": run["tokens"],
        "model_calls": run["model_calls"],
        "elapsed_seconds": 0.1,
        "artifacts": label,
    }
    write_scorecard(tmp_path, [record], {})
    assert main(["--rescore", str(tmp_path)]) == 0
    assert store.get(run["id"])["model_calls"] == run["model_calls"]
    assert json.loads((directory / "score.json").read_text())["passed"]


def test_trace_missing_usage_and_interrupted_span_do_not_invent_cost(tmp_path):
    store = RunStore(tmp_path)
    run = store.create("secret question")
    store.event(run["id"], "model_started", {"span_id": "incomplete", "reserved_tokens": 9000})
    trace = export_trace(store, run["id"], input_usd_per_million=1, output_usd_per_million=2)
    assert trace["spans"][0]["status"] == "incomplete"
    assert not trace["usage_complete"] and trace["cost"]["estimated_usd"] is None
    assert "secret question" not in json.dumps(trace)
    with pytest.raises(ValueError):
        export_trace(store, run["id"], input_usd_per_million=-1, output_usd_per_million=2)


def test_legacy_model_calls_prevent_false_complete_usage(tmp_path):
    store, run = calibration(tmp_path)
    store.change(
        run["id"], lambda r, c: r.update(model_calls=r["model_calls"] + 1, tokens=r["tokens"] + 100)
    )
    trace = export_trace(store, run["id"], input_usd_per_million=1, output_usd_per_million=2)
    assert not trace["usage_complete"] and trace["input_tokens"] is None
    assert trace["cost"]["estimated_usd"] is None


def test_trace_api_is_read_only_and_omits_content(tmp_path):
    store = RunStore(tmp_path)
    run = store.create("private question")
    store.control(run["id"], "pause")
    with TestClient(
        create_app(lambda: RunService(tmp_path)), base_url="http://127.0.0.1"
    ) as client:
        response = client.get(f"/api/investigations/{run['id']}/trace")
        assert response.status_code == 200
        assert response.json()["schema"] == "eil-local-trace-v1"
        assert "private question" not in response.text
        assert client.get(f"/api/investigations/{uuid.uuid4()}/trace").status_code == 404


@pytest.mark.parametrize(
    "limits",
    [
        {"max_model_calls": 2},
        {"max_tool_calls": 2},
        {"max_total_tokens": 11200},
        {"max_steps": 4},
    ],
)
def test_delegation_cannot_reset_cumulative_budgets(tmp_path, limits):
    store, run = calibration(tmp_path, mode="delegated", limits=limits)
    assert run["status"] in {"budget_exceeded", "failed"}
    assert run["result"] is None
    assert run["model_calls"] <= run["limits"]["max_model_calls"]
    assert run["tool_calls"] <= run["limits"]["max_tool_calls"]
    assert run["tokens"] <= run["limits"]["max_total_tokens"]


def test_fixture_hash_tampering_fails_before_ingestion(tmp_path, monkeypatch):
    copied = tmp_path / "fixtures"
    shutil.copytree(SUITE, copied)
    (copied / "ambiguous.csv").write_text("tampered")
    monkeypatch.setattr("eil.benchmark.SUITE", copied)
    with pytest.raises(ValueError, match="hash mismatch"):
        fixture_case(tmp_path / "state", "ambiguous")
    with pytest.raises(ValueError, match="Unknown benchmark"):
        fixture_case(tmp_path / "state", "../../private")


def test_delegate_cannot_read_another_case(tmp_path):
    foreign = fixture_case(tmp_path, "injection")
    store, run = calibration(tmp_path, "known-cause", "delegated")
    score, report = score_run(store, run["id"], "known-cause", "delegated")
    assert score["passed"]
    assert all(s["case_id"] != foreign["id"] for s in report["source_snapshot"])
    assert all(c["source_id"] in run["source_ids"] for c in report["citations"])


def hanging_delegate_worker(directory, run_id):
    class Hanging(ScriptedBenchmarkModel):
        def _generate(self, *args, **kwargs):
            if not any(t["function"]["name"] == "task" for t in kwargs.get("tools", [])):
                time.sleep(60)
            return super()._generate(*args, **kwargs)

    execute_run(directory, run_id, model=Hanging(model="offline"), agent_mode="delegated")


def test_supervisor_kills_blocked_delegate_with_shared_time_limit(tmp_path):
    case = fixture_case(tmp_path, "ambiguous")
    runner = RunService(tmp_path, worker_target=hanging_delegate_worker)
    run = runner.store.create(QUESTION, {"timeout_seconds": 8}, case_id=case["id"])
    with runner:
        saved = runner.wait(run["id"], timeout=20)
    assert saved["status"] == "timed_out"
    trace = export_trace(runner.store, run["id"])
    assert any(
        s["agent"] == "evidence-analyst" and s["status"] == "incomplete" for s in trace["spans"]
    )
    assert saved["model_calls"] == 2 and saved["tokens"] >= 8192
    assert saved["elapsed_seconds"] < 10
