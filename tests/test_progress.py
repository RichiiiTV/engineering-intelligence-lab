import asyncio
import json
from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from eil.api import create_app
from eil.auth import COOKIE, AuthStore
from eil.progress import MAX_CURSOR, REPLAY_LIMIT, project, recent_events, stream_progress
from eil.runs import RunStore
from tests.auth_helpers import PASSWORD, sign_in


@pytest.fixture
def client(tmp_path):
    @contextmanager
    def service():
        yield SimpleNamespace(store=RunStore(tmp_path))

    with TestClient(create_app(service), base_url="http://127.0.0.1") as client:
        owner = sign_in(client)
        client.owner = owner
        yield client


def run(client, *, completed=True):
    store = client.app.state.runs.store
    row = store.create("Generated private question sentinel", owner_id=client.owner.id)
    store.claim()
    store.event(row["id"], "model_started", {"prompt": "Generated secret prompt sentinel"})
    store.event(row["id"], "tool_started", {"arguments": {"text": "Generated private log"}})
    store.event(row["id"], "tool_finished", {"observation": "Generated private excerpt"})
    store.event(row["id"], "unknown", {"stage": "invented-stage"})
    if completed:
        store.finish(row["id"], "completed", result={"answer": "Generated private answer"})
    return row


def values(response):
    return [
        json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")
    ]


def test_progress_projects_only_known_enums_and_terminal_status(client):
    row = run(client)
    store = client.app.state.runs.store
    before = store.get(row["id"])
    response = client.get(f"/api/investigations/{row['id']}/progress")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["cache-control"] == "no-store"
    messages = values(response)
    assert [m["stage"] for m in messages] == [
        "queued",
        "preparing",
        "generating",
        "retrieving",
        "completed",
    ]
    assert messages[-1]["status"] == "completed"
    assert all(set(m) <= {"id", "stage", "status"} for m in messages)
    assert "private" not in response.text and "sentinel" not in response.text
    assert "arguments" not in response.text and "observation" not in response.text
    assert store.get(row["id"]) == before
    assert project(1, "unknown") is None


def test_progress_reconnect_uses_max_cursor_and_validates_bounds(client):
    row = run(client)
    path = f"/api/investigations/{row['id']}/progress"
    messages = values(client.get(path))
    cursor = messages[-2]["id"]
    reconnect = values(client.get(path + "?after=1", headers={"Last-Event-ID": str(cursor)}))
    assert reconnect == [messages[-1]]
    assert client.get(path + "?after=-1").status_code == 422
    assert client.get(path, headers={"Last-Event-ID": str(MAX_CURSOR + 1)}).status_code == 422


def test_progress_replay_is_bounded_without_dropping_current_terminal_state(client):
    row = run(client, completed=False)
    store = client.app.state.runs.store
    for _ in range(REPLAY_LIMIT + 12):
        store.event(row["id"], "model_started", {"secret": "Generated private sentinel"})
    store.finish(row["id"], "failed", error={"message": "Generated private error sentinel"})
    assert len(recent_events(store, row["id"], 0)) == REPLAY_LIMIT
    response = client.get(f"/api/investigations/{row['id']}/progress")
    messages = values(response)
    assert len(messages) == REPLAY_LIMIT
    assert messages[-1]["status"] == "failed"
    assert "sentinel" not in response.text


def test_progress_denies_other_owner_and_revoked_session(client):
    row = run(client)
    auth = AuthStore(client.app.state.runs.store.directory)
    auth.add_user(client.owner, "generated-other", PASSWORD)
    token, _ = auth.login("generated-other", PASSWORD)
    client.cookies.set(COOKIE, token)
    path = f"/api/investigations/{row['id']}/progress"
    assert client.get(path).status_code == 404
    auth.logout(token)
    assert client.get(path).status_code == 401


def test_progress_stream_rechecks_revocation_without_emitting_error_details(client, monkeypatch):
    row = run(client, completed=False)
    store = client.app.state.runs.store
    token = client.cookies.get(COOKIE)
    request = SimpleNamespace(cookies={COOKIE: token})

    async def connected():
        return False

    request.is_disconnected = connected
    monkeypatch.setattr("eil.progress.AUTH_CHECK_SECONDS", 0)

    async def check():
        stream = stream_progress(store, row["id"], request, 0)
        for _ in range(4):
            await anext(stream)
        AuthStore(store.directory).logout(token)
        with pytest.raises(StopAsyncIteration):
            await anext(stream)

    asyncio.run(check())
