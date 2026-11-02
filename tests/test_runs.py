import sqlite3
import time

import pytest
from langgraph.checkpoint.sqlite import SqliteSaver

from eil.agent import build_agent
from eil.runs import BudgetExceeded, QueueFull, RunConflict, RunStore
from eil.service import RunService
from tests.fakes import ControlledOllama, controlled_worker, crashing_worker, wait_for_event


def test_durable_real_graph_run_and_thread_isolation(tmp_path):
    with RunService(tmp_path, worker_target=controlled_worker) as service:
        first = service.submit("case:ALPHA")
        second = service.submit("case:BETA")
        a = service.wait(first["id"], timeout=20)
        b = service.wait(second["id"], timeout=20)
    assert a["status"] == b["status"] == "completed"
    assert a["thread_id"] != b["thread_id"]
    assert "ALPHA" in a["result"]["answer"] and "BETA" not in a["result"]["answer"]
    assert "BETA" in b["result"]["answer"] and "ALPHA" not in b["result"]["answer"]
    assert a["model_calls"] == b["model_calls"] == 2
    assert a["tokens"] == b["tokens"] == 260
    assert a["tool_calls"] == 1
    assert a["started_at"] and a["finished_at"]
    assert RunStore(tmp_path).get(a["id"]) == a
    with SqliteSaver.from_conn_string(str(tmp_path / "checkpoints.sqlite3")) as saver:
        for run in (a, b):
            graph = build_agent(
                model=ControlledOllama(
                    model=run["model"], directory=str(tmp_path), run_id=run["id"]
                ),
                checkpointer=saver,
            )
            snapshot = graph.get_state({"configurable": {"thread_id": run["id"]}})
            assert not snapshot.next
            assert snapshot.values["messages"][0].content == run["question"]
    events = RunStore(tmp_path).events(a["id"])
    assert all(e["run_id"] == a["id"] for e in events)
    assert [e["type"] for e in events].count("tool_finished") == 1


def test_pause_resume_across_service_restart_keeps_checkpoint_and_budgets(tmp_path):
    with RunService(tmp_path, worker_target=controlled_worker) as service:
        run = service.submit("resume:durable")
        wait_for_event(service.store, run["id"], "fake_blocked")
        service.store.control(run["id"], "pause")
        paused = service.wait(run["id"], timeout=5)
        assert paused["status"] == "paused"
        assert paused["tool_calls"] == 1
        assert paused["model_calls"] == 2  # the interrupted request is charged
    with RunService(tmp_path, worker_target=controlled_worker) as service:
        service.store.control(run["id"], "resume")
        result = service.wait(run["id"], timeout=20)
        events = service.store.events(run["id"])
    assert result["status"] == "completed"
    assert result["attempts"] == 2
    assert result["tool_calls"] == 1  # completed analytical tool is not repeated
    assert result["model_calls"] == 3
    assert result["tokens"] > paused["tokens"]
    assert result["elapsed_seconds"] > paused["elapsed_seconds"]
    assert [e["type"] for e in events].count("tool_finished") == 1


def test_shutdown_interrupts_and_recovery_resumes_pending_node(tmp_path):
    service = RunService(tmp_path, worker_target=controlled_worker).start()
    try:
        run = service.submit("resume:shutdown")
        wait_for_event(service.store, run["id"], "fake_blocked")
    finally:
        service.close()
    assert RunStore(tmp_path).get(run["id"])["status"] == "interrupted"
    with RunService(tmp_path, worker_target=controlled_worker) as restarted:
        restarted.store.control(run["id"], "resume")
        assert restarted.wait(run["id"], timeout=20)["status"] == "completed"


def test_cancel_terminates_a_blocked_model_call(tmp_path):
    with RunService(tmp_path, worker_target=controlled_worker) as service:
        run = service.submit("hang:cancel")
        wait_for_event(service.store, run["id"], "fake_blocked")
        started = time.monotonic()
        service.store.control(run["id"], "cancel")
        result = service.wait(run["id"], timeout=5)
        assert result["status"] == "cancelled"
        assert time.monotonic() - started < 3
        assert result["worker_pid"] is None
        with pytest.raises(RunConflict):
            service.store.control(run["id"], "resume")


def test_wall_clock_budget_kills_blocked_worker(tmp_path):
    with RunService(tmp_path, worker_target=controlled_worker) as service:
        run = service.submit("hang:timeout", {"timeout_seconds": 4})
        result = service.wait(run["id"], timeout=12)
    assert result["status"] == "timed_out"
    assert result["error"]["code"] == "time_budget"
    assert result["elapsed_seconds"] < 7


@pytest.mark.parametrize(
    "limits,counter",
    [
        ({"max_model_calls": 1}, "model_calls"),
        ({"max_tool_calls": 1}, "tool_calls"),
        ({"max_total_tokens": 9216}, "tokens"),
        ({"max_steps": 1}, "steps"),
    ],
)
def test_loop_is_stopped_by_each_budget(tmp_path, limits, counter):
    with RunService(tmp_path, worker_target=controlled_worker) as service:
        run = service.submit("loop:bounded", limits)
        result = service.wait(run["id"], timeout=20)
    assert result["status"] == "budget_exceeded", result
    maximum = result["limits"][
        {
            "model_calls": "max_model_calls",
            "tool_calls": "max_tool_calls",
            "tokens": "max_total_tokens",
            "steps": "max_steps",
        }[counter]
    ]
    assert result[counter] <= maximum


def test_unsupported_station_rejected_through_durable_agent(tmp_path):
    with RunService(tmp_path, worker_target=controlled_worker) as service:
        run = service.submit("bad_station:../../secrets")
        result = service.wait(run["id"], timeout=20)
        events = service.store.events(run["id"])
    assert result["status"] == "completed"
    observation = next(e for e in events if e["type"] == "tool_finished")["data"]["observation"]
    assert "Unknown station" in observation


def test_only_one_service_can_own_a_state_directory(tmp_path):
    with RunService(tmp_path, worker_target=controlled_worker):
        other = RunService(tmp_path, worker_target=controlled_worker)
        with pytest.raises(RunConflict, match="active service"):
            other.start()


def test_startup_marks_stale_running_jobs_interrupted(tmp_path):
    store = RunStore(tmp_path)
    run = store.create("case:crash")
    store.claim()
    with RunService(tmp_path, worker_target=controlled_worker) as service:
        recovered = service.store.get(run["id"])
        assert recovered["status"] == "interrupted"
        assert recovered["error"]["code"] == "service_restarted"
        service.store.control(run["id"], "resume")
        assert service.wait(run["id"], timeout=20)["status"] == "completed"


def test_queue_limit_and_queued_control_are_durable(tmp_path):
    store = RunStore(tmp_path)
    runs = [store.create(f"case:{number}") for number in range(20)]
    with pytest.raises(QueueFull):
        store.create("overflow")
    paused = store.control(runs[0]["id"], "pause")
    assert paused["status"] == "paused"
    cancelled = store.control(runs[1]["id"], "cancel")
    assert cancelled["status"] == "cancelled"
    assert RunStore(tmp_path).get(runs[0]["id"])["status"] == "paused"
    store.create("replacement")
    store.create("replacement-two")
    with pytest.raises(QueueFull):
        store.control(runs[0]["id"], "resume")


def test_failed_reservation_and_restart_cannot_reset_token_budget(tmp_path):
    store = RunStore(tmp_path)
    run = store.create("case:reservation", {"max_total_tokens": 9216})
    store.claim()
    store.charge(run["id"], "tokens", 9216)
    store.recover()
    store.control(run["id"], "resume")
    store.claim()
    with pytest.raises(BudgetExceeded):
        store.charge(run["id"], "tokens", 1)
    assert store.get(run["id"])["tokens"] == 9216


def test_truncated_model_output_is_not_a_success(tmp_path):
    with RunService(tmp_path, worker_target=controlled_worker) as service:
        run = service.submit("output_limit:truncated")
        result = service.wait(run["id"], timeout=20)
    assert result["status"] == "budget_exceeded"
    assert result["result"]["answer_mode"] == "budget_source_extract"
    assert result["result"]["answer_contract"]["outcome"] == "budget_limited"
    assert "Teilweise Belegprüfung" in result["result"]["answer"]
    assert "output limit" in result["error"]["message"]


def test_budget_is_not_reset_by_pausing_and_resuming(tmp_path):
    with RunService(tmp_path, worker_target=controlled_worker) as service:
        run = service.submit("resume:budget", {"max_model_calls": 2})
        wait_for_event(service.store, run["id"], "fake_blocked")
        service.store.control(run["id"], "pause")
        assert service.wait(run["id"], timeout=5)["status"] == "paused"
        service.store.control(run["id"], "resume")
        result = service.wait(run["id"], timeout=20)
    assert result["status"] == "budget_exceeded"
    assert result["model_calls"] == 2


def test_unexpected_worker_exit_is_inspectable_and_resumable(tmp_path):
    with RunService(tmp_path, worker_target=crashing_worker) as service:
        run = service.submit("case:crash")
        result = service.wait(run["id"], timeout=20)
    assert result["status"] == "interrupted"
    assert result["error"]["exit_code"] == 23
    with RunService(tmp_path, worker_target=controlled_worker) as service:
        service.store.control(run["id"], "resume")
        assert service.wait(run["id"], timeout=20)["status"] == "completed"


def test_database_contains_distinct_checkpoint_threads(tmp_path):
    # A SQL-level assertion independently checks the persistence boundary.
    with RunService(tmp_path, worker_target=controlled_worker) as service:
        runs = [service.submit(f"case:{label}") for label in ("one", "two")]
        for run in runs:
            assert service.wait(run["id"], timeout=20)["status"] == "completed"
    with sqlite3.connect(tmp_path / "checkpoints.sqlite3") as conn:
        ids = {r[0] for r in conn.execute("SELECT DISTINCT thread_id FROM checkpoints")}
    assert ids == {r["id"] for r in runs}
