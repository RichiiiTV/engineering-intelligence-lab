import json

import pytest
from fastapi.testclient import TestClient

from eil.api import create_app
from eil.service import RunService
from tests.fakes import controlled_worker, wait_for_event


@pytest.fixture
def client(tmp_path):
    with TestClient(
        create_app(lambda: RunService(tmp_path, worker_target=controlled_worker)),
        base_url="http://127.0.0.1",
    ) as value:
        yield value


def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_summary_and_stations(client):
    response = client.get("/api/metrics/summary")
    assert response.status_code == 200
    assert response.json()["ranked_stations"][0]["station_id"] == "S03"
    station = client.get("/api/metrics/stations/S01")
    assert station.status_code == 200
    assert station.json()["baseline"]["period"] == "baseline"


def test_unknown_station_is_404(client):
    assert client.get("/api/metrics/stations/../../secrets").status_code in (404, 400)
    assert client.get("/api/metrics/stations/UNKNOWN").status_code == 404


@pytest.mark.parametrize("question", ["", " \t\n", "x" * 4001])
def test_input_rejected_before_starting_a_job(client, question):
    assert client.post("/api/investigations", json={"question": question}).status_code == 422
    assert client.get("/api/investigations").json()["investigations"] == []


def test_model_connectivity_failure_is_recorded_without_api_traceback(client):
    response = client.post("/api/investigations", json={"question": "model_down:offline"})
    assert response.status_code == 202
    run = client.app.state.runs.wait(response.json()["id"], timeout=20)
    status = client.get(f"/api/investigations/{run['id']}")
    assert status.status_code == 200
    assert run["status"] == "failed"
    assert run["error"]["code"] == "model_unavailable"
    assert "Start the service" in run["error"]["message"]
    assert "Traceback" not in status.text


def test_agent_is_queued_and_completed_result_is_inspectable(client):
    response = client.post("/api/investigations", json={"question": "case:api"})
    assert response.status_code == 202
    run = client.app.state.runs.wait(response.json()["id"], timeout=20)
    assert run["status"] == "completed"
    assert "S03" in run["result"]["answer"]
    assert client.get(f"/api/investigations/{run['id']}").json()["result"] == run["result"]
    assert len(client.get("/api/investigations").json()["investigations"]) == 1


def test_persisted_sse_events_and_reconnect_cursor(client):
    run = client.post("/api/investigations", json={"question": "case:events"}).json()
    client.app.state.runs.wait(run["id"], timeout=20)
    path = f"/api/investigations/{run['id']}/events"
    response = client.get(path)
    assert response.headers["content-type"].startswith("text/event-stream")
    events = [
        json.loads(line.removeprefix("data: "))
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]
    assert events[0]["type"] == "queued"
    assert events[-1]["type"] == "completed"
    assert any(e["type"] == "tool_finished" for e in events)
    resumed = client.get(path, headers={"Last-Event-ID": str(events[-2]["id"])})
    assert "event: completed" in resumed.text
    assert "event: queued" not in resumed.text
    assert client.get(path + "?after=-1").status_code == 422


def test_api_stays_responsive_and_can_pause_resume(client):
    run = client.post("/api/investigations", json={"question": "resume:api"}).json()
    runner = client.app.state.runs
    wait_for_event(runner.store, run["id"], "fake_blocked")
    assert client.get("/api/health").status_code == 200
    path = f"/api/investigations/{run['id']}"
    assert client.post(path + "/pause").status_code == 202
    assert runner.wait(run["id"], timeout=5)["status"] == "paused"
    assert client.post(path + "/resume").status_code == 202
    assert runner.wait(run["id"], timeout=20)["status"] == "completed"
    assert client.post(path + "/resume").status_code == 409


def test_invalid_ollama_configuration_is_actionable_503(client, monkeypatch):
    monkeypatch.setattr("eil.runs.OLLAMA_BASE_URL", "file:///secrets")
    response = client.post("/api/investigations", json={"question": "case:invalid"})
    assert response.status_code == 503
    assert "HTTP Ollama URL" in response.json()["detail"]


def test_unknown_runs_and_untrusted_execution_options(client):
    assert client.get("/api/investigations/not-a-path").status_code == 404
    assert client.post("/api/investigations/unknown/cancel").status_code == 404
    for extra in ({"thread_id": "other"}, {"model": "paid-provider"}, {"path": "../../secrets"}):
        response = client.post("/api/investigations", json={"question": "case:invalid", **extra})
        assert response.status_code == 422
    assert (
        client.post(
            "/api/investigations", json={"question": "case:invalid", "limits": {"max_steps": 0}}
        ).status_code
        == 422
    )
