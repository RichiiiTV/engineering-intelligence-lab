import sqlite3
import threading

import pytest
from fastapi.testclient import TestClient

from eil import auth as module
from eil.api import create_app
from eil.audit import AuditStore, flush, status
from eil.auth import AuthenticationError, AuthStore
from eil.service import RunService
from eil.storage import StorageManager, restore_backup
from tests.auth_helpers import PASSWORD
from tests.fakes import controlled_worker


@pytest.mark.parametrize("change", ["password", "revoke", "disable"])
def test_inflight_login_is_rejected_after_security_change(tmp_path, monkeypatch, change):
    store = AuthStore(tmp_path)
    user = store.enroll(store.bootstrap(), "owner", PASSWORD)
    member = store.add_user(user, "member", PASSWORD)
    checked, release = threading.Event(), threading.Event()
    original = module._passwords

    class Passwords:
        def hash(self, value):
            return original.hash(value)

        def verify(self, value, hashed):
            valid = original.verify(value, hashed)
            if threading.current_thread().name == "pending-login":
                checked.set()
                assert release.wait(10)
            return valid

    monkeypatch.setattr(module, "_passwords", Passwords())
    outcome = []

    def login():
        try:
            store.login("member", PASSWORD)
        except AuthenticationError:
            outcome.append("rejected")

    thread = threading.Thread(target=login, name="pending-login")
    thread.start()
    try:
        assert checked.wait(10)
        if change == "password":
            store.change_password(member, PASSWORD, "Changed-synthetic-password")
        else:
            store.manage_user(
                user,
                member.id,
                revoke=change == "revoke",
                active=False if change == "disable" else None,
            )
    finally:
        release.set()
        thread.join(10)
    assert outcome == ["rejected"]


def test_anonymous_flood_is_aggregated_and_archive_keeps_chain_and_backup(tmp_path):
    auth = AuthStore(tmp_path)
    owner = auth.enroll(auth.bootstrap(), "owner", PASSWORD)
    with TestClient(
        create_app(lambda: RunService(tmp_path, worker_target=controlled_worker)),
        base_url="http://127.0.0.1",
    ) as client:
        for _ in range(450):
            assert client.get("/api/cases").status_code == 401
        assert (
            client.post(
                "/api/auth/login", json={"username": "owner", "password": PASSWORD}
            ).status_code
            == 200
        )
    history = AuditStore(tmp_path)
    before = history.integrity()
    assert before["checked"] < 12 and before["valid"]
    archive = history.archive()
    assert archive["archived"]
    with auth.connection() as conn:
        auth.audit(conn, owner.id, "after_archive")
    assert history.integrity()["valid"]
    assert history.integrity()["checked"] == before["checked"] + 1
    assert len(history.events()) == before["checked"] + 1
    manager = StorageManager(tmp_path)
    backup = manager.create_backup(owner)
    destination = tmp_path / "restored"
    restore_backup(manager.backup_path(backup["id"]), destination)
    assert AuditStore(destination).integrity()["valid"]


def test_audit_destination_failure_does_not_break_sign_in(tmp_path, monkeypatch):
    auth = AuthStore(tmp_path)
    auth.enroll(auth.bootstrap(), "owner", PASSWORD)
    original = AuditStore.connection

    def unavailable(self):
        raise sqlite3.OperationalError("Controlled audit destination outage")

    monkeypatch.setattr(AuditStore, "connection", unavailable)
    token, _ = auth.login("owner", PASSWORD)
    assert auth.authenticate(token).username == "owner"
    assert status(tmp_path)["pending"] > 0
    monkeypatch.setattr(AuditStore, "connection", original)
    flush(tmp_path)
    assert status(tmp_path)["pending"] == 0
    assert AuditStore(tmp_path).integrity()["valid"]
