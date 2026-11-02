import json

import pytest
from fastapi.testclient import TestClient

from eil.api import create_app
from eil.auth import COOKIE, AuthenticationError, AuthenticationLimited, AuthStore
from eil.database import StorageFull
from eil.drafts import DraftStore
from eil.evidence import EvidenceStore
from eil.runs import BudgetExceeded, RunConflict, RunStopped, RunStore
from eil.service import RunService
from eil.storage import StorageManager, restore_backup
from eil.tracing import export_trace
from tests.auth_helpers import PASSWORD
from tests.fakes import controlled_worker


def test_setup_requires_operator_code_and_session_is_revocable(tmp_path):
    auth = AuthStore(tmp_path)
    with pytest.raises(AuthenticationError):
        auth.enroll("bad-code", "owner", PASSWORD)
    code = auth.bootstrap()
    user = auth.enroll(code, "owner", PASSWORD)
    with pytest.raises(AuthenticationError):
        auth.enroll(code, "attacker", PASSWORD)
    token, _ = auth.login("owner", PASSWORD)
    assert auth.authenticate(token) == user
    with auth.connection() as conn:
        serialized = json.dumps([tuple(r) for r in conn.execute("SELECT * FROM users")])
        assert PASSWORD not in serialized
        assert conn.execute("SELECT token_hash FROM sessions").fetchone()[0] != token
    auth.logout(token)
    with pytest.raises(AuthenticationError):
        auth.authenticate(token)


def test_password_change_revokes_all_sessions_and_attempts_are_limited(tmp_path):
    auth = AuthStore(tmp_path)
    user = auth.enroll(auth.bootstrap(), "owner", PASSWORD)
    first, _ = auth.login("owner", PASSWORD)
    second, _ = auth.login("owner", PASSWORD)
    auth.change_password(user, PASSWORD, "A-different-synthetic-password")
    for token in (first, second):
        with pytest.raises(AuthenticationError):
            auth.authenticate(token)
    for _ in range(5):
        with pytest.raises(AuthenticationError):
            auth.login("owner", "incorrect", "test-rate")
    with pytest.raises(AuthenticationLimited):
        auth.login("owner", "incorrect", "test-rate")


def test_http_auth_cookie_tenant_boundaries_and_reviewer_identity(tmp_path):
    app = create_app(lambda: RunService(tmp_path, worker_target=controlled_worker))
    with TestClient(app, base_url="http://127.0.0.1") as client:
        assert client.get("/api/cases").status_code == 401
        assert client.get("/api/knowledge/siemens/search").status_code == 401
        assert client.get("/api/auth/status").json() == {"configured": False}
        code = AuthStore(tmp_path).bootstrap()
        response = client.post(
            "/api/auth/enroll", json={"code": code, "username": "owner", "password": PASSWORD}
        )
        assert response.status_code == 201, response.text
        header = response.headers["set-cookie"].lower()
        assert "httponly" in header and "samesite=strict" in header and "domain=" not in header
        owner = response.json()["user"]
        case = client.post("/api/cases", json={"title": "Owner-only"}).json()
        evidence = EvidenceStore(tmp_path)
        source = evidence.ingest(
            case["id"],
            "metrics.csv",
            b"row_id,timestamp,station_id,period,inspected,false_ejects,true_rejects,illumination_lux,exposure_us\nx,2026-10-10,S03,baseline,100,1,0,600,2400\n",
        )
        runs = RunStore(tmp_path)
        run = runs.create("Synthetic case", case_id=case["id"], owner_id=owner["id"])
        runs.claim()
        runs.finish(run["id"], "completed", result={"answer": "Synthetic result"})
        proposal = DraftStore(runs).propose(run["id"], "Draft", "Synthetic evidence")
        admin_cookie = client.cookies.get(COOKIE)
        assert (
            client.post(
                "/api/auth/users", json={"username": "second", "password": PASSWORD}
            ).status_code
            == 201
        )
        client.post("/api/auth/login", json={"username": "second", "password": PASSWORD})
        assert client.get("/api/cases").json()["cases"] == []
        for path in (
            f"/api/cases/{case['id']}",
            f"/api/cases/{case['id']}/sources/{source['id']}/file",
            f"/api/investigations/{run['id']}",
            f"/api/investigations/{run['id']}/events",
            f"/api/investigations/{run['id']}/export",
            f"/api/approvals/{proposal['id']}",
        ):
            assert client.get(path).status_code == 404, path
        assert (
            client.post(
                "/api/investigations", json={"question": "steal", "case_id": case["id"]}
            ).status_code
            == 404
        )
        assert (
            client.post(
                "/api/auth/users", json={"username": "third", "password": PASSWORD}
            ).status_code
            == 403
        )
        assert (
            client.post(
                f"/api/approvals/{proposal['id']}/decision",
                json={"decision": "approve", "expected_sha256": proposal["sha256"]},
            ).status_code
            == 404
        )
        client.cookies.clear()
        client.cookies.set(COOKIE, admin_cookie)
        approved = client.post(
            f"/api/approvals/{proposal['id']}/decision",
            json={"decision": "approve", "expected_sha256": proposal["sha256"]},
        ).json()
        assert approved["reviewer"]["id"] == owner["id"]
        assert approved["reviewer_authentication"] == "authenticated-session"


def test_provider_overage_is_atomic_audited_and_cannot_resume(tmp_path):
    store = RunStore(tmp_path)
    run = store.create("Synthetic overage", {"max_total_tokens": 10000})
    store.claim()
    _, admission = store.reserve_model(run["id"], 8192)
    with pytest.raises(BudgetExceeded):
        store.settle_tokens(run["id"], admission["reserved"], 12000)
    saved = store.get(run["id"])
    assert saved["tokens"] == 12000 and saved["status"] == "budget_exceeded"
    assert saved["result"]["answer_contract"]["outcome"] == "budget_limited"
    assert any(e["type"] == "model_usage_overage" for e in store.events(run["id"]))
    with pytest.raises(RunStopped):
        store.reserve_model(run["id"], 8192)
    with pytest.raises(RunConflict):
        store.control(run["id"], "resume")
    with pytest.raises(RunConflict):
        store.continue_tokens(run["id"], 65536)
    assert export_trace(store, run["id"])["charged_tokens"] == 12000


def test_empty_member_retention_cannot_consume_backup_quota(tmp_path):
    from datetime import datetime, timedelta, timezone

    auth = AuthStore(tmp_path / "state")
    admin = auth.enroll(auth.bootstrap(), "owner", PASSWORD)
    member = auth.add_user(admin, "member", PASSWORD)
    manager = StorageManager(tmp_path / "state")
    for _ in range(5):
        plan = manager.retention_plan(member)
        assert plan["cases"] == []
        for _ in range(2):
            with pytest.raises(RunConflict, match="no trash to purge"):
                manager.apply_retention(
                    plan["id"], plan["sha256"], member, "PERMANENTLY PURGE REVIEWED TRASH"
                )
        assert manager.list_backups() == []

    # A real member purge still makes its required recovery backup, and an
    # administrator retains capacity for an explicit workspace backup.
    case = manager.evidence.create_case("Generated member case", owner_id=member.id)
    manager.trash(case["id"], member)
    with manager.evidence.connection() as conn:
        conn.execute(
            "UPDATE cases SET deleted_at=? WHERE id=?",
            ((datetime.now(timezone.utc) - timedelta(days=91)).isoformat(), case["id"]),
        )
    plan = manager.retention_plan(member)
    result = manager.apply_retention(
        plan["id"], plan["sha256"], member, "PERMANENTLY PURGE REVIEWED TRASH"
    )
    assert result["purged_cases"] == 1
    assert len(manager.list_backups()) == 1
    assert manager.create_backup(admin)["id"]
    assert len(manager.list_backups()) == 2


def test_trash_restore_backup_integrity_and_permanent_retention_approval(tmp_path):
    from datetime import datetime, timedelta, timezone

    auth = AuthStore(tmp_path / "state")
    actor = auth.enroll(auth.bootstrap(), "owner", PASSWORD)
    manager = StorageManager(tmp_path / "state")
    case = manager.evidence.create_case("Recoverable synthetic case", owner_id=actor.id)
    manager.trash(case["id"], actor)
    assert manager.evidence.cases(owner_id=actor.id) == []
    assert manager.evidence.cases(owner_id=actor.id, deleted=True)[0]["id"] == case["id"]
    manager.trash(case["id"], actor, restore=True)
    assert manager.evidence.case(case["id"])["id"] == case["id"]
    backup = manager.create_backup(actor)
    restored = tmp_path / "restored"
    restore_backup(manager.backup_path(backup["id"]), restored)
    assert EvidenceStore(restored).case(case["id"])["title"] == case["title"]
    with AuthStore(restored).connection() as conn:
        assert conn.execute("SELECT count(*) FROM sessions").fetchone()[0] == 0
    with pytest.raises(RunConflict):
        restore_backup(manager.backup_path(backup["id"]), restored)
    manager.trash(case["id"], actor)
    with manager.evidence.connection() as conn:
        conn.execute(
            "UPDATE cases SET deleted_at=? WHERE id=?",
            ((datetime.now(timezone.utc) - timedelta(days=91)).isoformat(), case["id"]),
        )
    plan = manager.retention_plan(actor)
    assert len(plan["cases"]) == 1
    with pytest.raises(RunConflict):
        manager.apply_retention(plan["id"], "0" * 64, actor, "PERMANENTLY PURGE REVIEWED TRASH")
    with pytest.raises(RunConflict):
        manager.apply_retention(plan["id"], plan["sha256"], actor, "no")
    result = manager.apply_retention(
        plan["id"], plan["sha256"], actor, "PERMANENTLY PURGE REVIEWED TRASH"
    )
    assert result["purged_cases"] == 1 and result["backup_id"]
    assert manager.evidence.cases(owner_id=actor.id, deleted=True) == []
    assert (
        manager.apply_retention(
            plan["id"], plan["sha256"], actor, "PERMANENTLY PURGE REVIEWED TRASH"
        )["status"]
        == "completed"
    )


def test_stale_retention_and_corrupt_backup_are_rejected(tmp_path):
    import zipfile
    from datetime import datetime, timedelta, timezone

    auth = AuthStore(tmp_path / "state")
    actor = auth.enroll(auth.bootstrap(), "owner", PASSWORD)
    manager = StorageManager(tmp_path / "state")
    case = manager.evidence.create_case("Synthetic retention", owner_id=actor.id)
    manager.trash(case["id"], actor)
    with manager.evidence.connection() as conn:
        conn.execute(
            "UPDATE cases SET deleted_at=? WHERE id=?",
            ((datetime.now(timezone.utc) - timedelta(days=91)).isoformat(), case["id"]),
        )
    plan = manager.retention_plan(actor)
    manager.trash(case["id"], actor, restore=True)
    with pytest.raises(RunConflict):
        manager.apply_retention(
            plan["id"], plan["sha256"], actor, "PERMANENTLY PURGE REVIEWED TRASH"
        )
    attack = tmp_path / "attack.zip"
    with zipfile.ZipFile(attack, "w") as archive:
        archive.writestr("../outside", "untrusted")
        archive.writestr("manifest.json", "{}")
    with pytest.raises(RunConflict):
        restore_backup(attack, tmp_path / "unsafe")
    assert not (tmp_path / "unsafe").exists()


def test_global_case_quota_is_not_bypassed_by_new_owners(tmp_path, monkeypatch):
    monkeypatch.setattr("eil.evidence.MAX_CASES", 1)
    store = EvidenceStore(tmp_path)
    store.create_case("First", owner_id="first")
    with pytest.raises(StorageFull):
        store.create_case("Second", owner_id="second")


def test_case_pagination_and_owner_filtered_history(tmp_path):
    evidence = EvidenceStore(tmp_path)
    for n in range(61):
        evidence.create_case(f"Case {n}", owner_id="first")
    assert len(evidence.cases(owner_id="first", limit=50)) == 50
    assert len(evidence.cases(owner_id="first", limit=50, offset=50)) == 11
    assert evidence.cases(owner_id="second") == []
    runs = RunStore(tmp_path)
    for i in range(61):
        run = runs.create(f"Completed {i}", owner_id="first")
        runs.claim()
        runs.finish(run["id"], "completed", result={"answer": "synthetic"})
    assert len(runs.list(offset=50, owner_id="first")) == 11
    assert runs.list(owner_id="second") == []


def test_password_verification_admission_is_bounded(tmp_path):
    from eil.auth import _login_slot

    auth = AuthStore(tmp_path)
    auth.enroll(auth.bootstrap(), "owner", PASSWORD)
    _login_slot.acquire()
    _login_slot.acquire()
    try:
        with pytest.raises(AuthenticationLimited):
            auth.login("owner", PASSWORD)
    finally:
        _login_slot.release()
        _login_slot.release()
    token, _ = auth.login("owner", PASSWORD)
    assert auth.authenticate(token).username == "owner"


def test_backup_preserves_evidence_drafts_checkpoints_and_purge_recovers_after_interruption(
    tmp_path, monkeypatch
):
    import sqlite3
    from contextlib import closing, contextmanager
    from datetime import datetime, timedelta, timezone

    from eil.benchmark import QUESTION, ScriptedBenchmarkModel, fixture_case
    from eil.execution import execute_run

    state = tmp_path / "state"
    auth = AuthStore(state)
    actor = auth.enroll(auth.bootstrap(), "owner", PASSWORD)
    case = fixture_case(state, "ambiguous")
    manager = StorageManager(state)
    run = manager.runs.create(QUESTION, case_id=case["id"])
    manager.runs.claim()
    execute_run(state, run["id"], model=ScriptedBenchmarkModel(model="offline"))
    assert manager.runs.get(run["id"])["status"] == "completed"
    drafts = DraftStore(manager.runs)
    proposal = drafts.propose(run["id"], "Reviewed synthetic report", "Evidence remains local.")
    drafts.decide(proposal["id"], "approve", proposal["sha256"], actor=actor.public())
    original = manager.evidence.sources(case["id"])[0]
    raw = manager.evidence.source(case["id"], original["id"])["raw"]
    backup = manager.create_backup(actor)
    restored = tmp_path / "restored"
    restore_backup(manager.backup_path(backup["id"]), restored)
    assert EvidenceStore(restored).source(case["id"], original["id"])["raw"] == raw
    assert RunStore(restored).get(run["id"])["tokens"] == manager.runs.get(run["id"])["tokens"]
    assert DraftStore(RunStore(restored)).drafts(case["id"])[0]["body"] == "Evidence remains local."
    with closing(sqlite3.connect(restored / "checkpoints.sqlite3")) as conn:
        assert (
            conn.execute(
                "SELECT count(*) FROM checkpoints WHERE thread_id=?", (run["id"],)
            ).fetchone()[0]
            > 0
        )
    manager.trash(case["id"], actor)
    with manager.evidence.connection() as conn:
        conn.execute(
            "UPDATE cases SET deleted_at=? WHERE id=?",
            ((datetime.now(timezone.utc) - timedelta(days=91)).isoformat(), case["id"]),
        )
    plan = manager.retention_plan(actor)
    original_connection = manager.evidence.connection

    class Interrupted:
        def __init__(self, conn):
            self.conn = conn

        def execute(self, sql, *args):
            if sql.startswith("DELETE FROM chunks"):
                raise RuntimeError("Synthetic interrupted purge")
            return self.conn.execute(sql, *args)

    @contextmanager
    def interrupt():
        with original_connection() as conn:
            yield Interrupted(conn)

    monkeypatch.setattr(manager.evidence, "connection", interrupt)
    with pytest.raises(RuntimeError, match="interrupted purge"):
        manager.apply_retention(
            plan["id"], plan["sha256"], actor, "PERMANENTLY PURGE REVIEWED TRASH"
        )
    monkeypatch.setattr(manager.evidence, "connection", original_connection)
    assert (
        manager.apply_retention(
            plan["id"], plan["sha256"], actor, "PERMANENTLY PURGE REVIEWED TRASH"
        )["status"]
        == "completed"
    )
    with closing(sqlite3.connect(state / "checkpoints.sqlite3")) as conn:
        assert (
            conn.execute(
                "SELECT count(*) FROM checkpoints WHERE thread_id=?", (run["id"],)
            ).fetchone()[0]
            == 0
        )
        assert (
            conn.execute("SELECT count(*) FROM writes WHERE thread_id=?", (run["id"],)).fetchone()[
                0
            ]
            == 0
        )
