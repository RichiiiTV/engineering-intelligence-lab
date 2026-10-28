from fastapi.testclient import TestClient

from eil.api import app

client = TestClient(app)


def test_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_summary_and_stations():
    response = client.get("/api/metrics/summary")
    assert response.status_code == 200
    assert response.json()["ranked_stations"][0]["station_id"] == "S03"
    s = client.get("/api/metrics/stations/S01")
    assert s.status_code == 200
    assert s.json()["baseline"]["period"] == "baseline"


def test_unknown_station_is_404():
    assert client.get("/api/metrics/stations/../../secrets").status_code in (404, 400)
    assert client.get("/api/metrics/stations/UNKNOWN").status_code == 404


def test_agent_input_validation_without_calling_model():
    response = client.post("/api/investigations", json={"question": ""})
    assert response.status_code == 422


def test_blank_and_oversized_questions_are_422(monkeypatch):
    def forbidden(question):
        raise AssertionError("Invalid input must not reach the model")

    monkeypatch.setattr("eil.agent.run_agent", forbidden)
    for question in (" \t\n", "x" * 4001):
        assert client.post("/api/investigations", json={"question": question}).status_code == 422


def test_model_connectivity_failure_is_actionable_503(monkeypatch):
    from eil.agent import ModelUnavailableError

    def unavailable(question):
        raise ModelUnavailableError("Cannot validate Ollama model. Start Ollama.")

    monkeypatch.setattr("eil.agent.run_agent", unavailable)
    response = client.post("/api/investigations", json={"question": "Compare the stations"})
    assert response.status_code == 503
    assert "Start Ollama" in response.json()["detail"]


def test_agent_success_is_returned(monkeypatch):
    monkeypatch.setattr("eil.agent.run_agent", lambda question: {"answer": "Offline answer"})
    response = client.post("/api/investigations", json={"question": "Compare the stations"})
    assert response.status_code == 200
    assert response.json()["answer"] == "Offline answer"
