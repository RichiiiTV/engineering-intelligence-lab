import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from eil.api import create_app
from eil.auth import IDLE_SECONDS, SESSION_SECONDS, AuthenticationError, AuthStore
from eil.benchmark import fixture_case
from eil.claims import Claims, evidence_ledger, verify
from eil.evidence import EvidenceStore
from eil.service import RunService
from eil.siemens_reference import enrich, query_context, references
from tests.auth_helpers import sign_in


def test_metrics_quotes_and_conflicts_are_checked_against_scoped_data(tmp_path):
    case = fixture_case(tmp_path, "known-cause")
    store = EvidenceStore(tmp_path)
    sources = store.sources(case["id"])
    csv = next(s for s in sources if s["kind"] == "csv")
    hits = store.search(case["id"], "controlled illumination", limit=5)["hits"]
    hit = next(h for h in hits if "CONTROLLED-REPLAY" in h["text"])
    base = {
        "source_id": csv["id"],
        "station_id": "S03",
        "baseline_rate": 0.01,
        "incident_rate": 0.14,
        "delta_pp": 13,
    }
    claims = Claims.model_validate(
        {
            "metrics": [base, {**base, "delta_pp": 99}, {**base, "station_id": "S02"}],
            "quotations": [
                {
                    "citation_id": hit["citation_id"],
                    "quotation": "S03 lighting was the sole manipulated variable",
                },
                {
                    "citation_id": hit["citation_id"],
                    "quotation": "The physical PLC cause is proven.",
                },
            ],
        }
    )
    snapshot = store.snapshot(case["id"])
    result = verify(store, case["id"], snapshot, claims)
    assert [m["verified"] for m in result["metrics"]] == [True, False, False]
    assert [q["verified"] for q in result["quotations"]] == [True, False]
    assert result["prose_entailment"] == "not_verified" and result["causation"] == "not_established"
    changed = (
        Path("data/benchmarks/eil-v1/known-cause.csv")
        .read_bytes()
        .replace(b"10000,1400", b"10000,1800")
    )
    other = store.ingest(case["id"], "conflicting.csv", changed)
    assert not verify(
        store,
        case["id"],
        snapshot,
        Claims.model_validate({"metrics": [{**base, "source_id": other["id"]}]}),
    )["metrics"][0]["verified"]
    ledger = evidence_ledger(store, case["id"], store.snapshot(case["id"]))
    assert ledger["conflicting_csv_measurements"][0]["station_id"] == "S03"
    assert len(ledger["comparisons"]) == 2


def test_retrieval_returns_adjacent_conclusion_with_own_citation(tmp_path):
    case = fixture_case(tmp_path, "known-cause")
    store = EvidenceStore(tmp_path)
    result = store.search(case["id"], "CONTROLLED-REPLAY", limit=1)
    hit = result["hits"][0]
    assert any("supports illumination as the cause" in n["text"] for n in hit["context"])
    assert all(
        n["page"] == hit["page"] and n["source_id"] == hit["source_id"] for n in hit["context"]
    )


@pytest.mark.parametrize("field,seconds", [("last_used", IDLE_SECONDS + 1), ("expires", -1)])
def test_session_expiry_is_enforced(tmp_path, field, seconds):
    import time

    auth = AuthStore(tmp_path)
    auth.enroll(auth.bootstrap(), "owner", "A synthetic password 123!")
    token, _ = auth.login("owner", "A synthetic password 123!")
    with auth.connection() as conn:
        value = time.time() - seconds if field == "last_used" else time.time() - 1
        conn.execute(f"UPDATE sessions SET {field}=?", (value,))
    with pytest.raises(AuthenticationError):
        auth.authenticate(token)
    assert SESSION_SECONDS == 8 * 3600


@pytest.mark.parametrize(
    "question,family,tia,expected",
    [
        ("Where is OB1 cycle time documented?", "S7-1500", "V20", "1500-cycle-v20"),
        ("S7-1500 V20 cycle-time manual", "", "", "1500-cycle-v20"),
        ("Wo ist die Zykluszeit beschrieben?", "S7-1500", "V20", "1500-cycle-v20"),
        ("CPU firmware programming manual", "S7-1200", "V20", "1200-cpu-v20"),
        ("UMAC access security configuration", "S7-1200", "V20", "1200-configuration-v20"),
        ("G2 programming manual", "S7-1200 G2", "V20", "1200-g2-v20"),
        ("OB1 cycle time", "S7-1500", "V19", None),
        ("S7-1500 V19 OB1 cycle time", "", "", None),
        ("unrelated motor torque", "S7-1500", "V20", None),
    ],
)
def test_sps_manual_coverage_golden_questions(question, family, tia, expected):
    outbound, context = query_context(question, family=family, tia_version=tia)
    result = enrich({"sources": []}, question, outbound, context)
    ids = {r["id"] for r in result["curated_references"]}
    assert (expected in ids) if expected else not ids
    assert not result["technical_answer_verified"]
    assert all(not r["firmware_compatibility_verified"] for r in result["curated_references"])


def test_product_context_is_bounded_and_has_no_case_payload():
    question, context = query_context(
        "OB1 cycle time", family="S7-1500", cpu="CPU 1511-1 PN", firmware="V3.1", tia_version="V20"
    )
    assert "firmware=V3.1" in question and "tia_version=V20" in question
    assert "case" not in question and context["cpu"] == "CPU 1511-1 PN"
    for values in (
        {"cpu": "$(shell)"},
        {"firmware": "https://evil.invalid"},
        {"family": "S7-9999"},
        {"tia_version": "latest"},
    ):
        with pytest.raises(ValueError):
            query_context("Public question", **values)
    with pytest.raises(ValueError):
        query_context("q" * 500, cpu="1511")
    assert not references("S7-1200 G2 manual", {"tia_version": "V19"})


def test_reviewed_manual_host_is_allowed_without_opening_cloud_subdomains():
    from eil.siemens_mcp import approved_url
    from eil.siemens_reference import BASE, REFERENCES

    assert all(approved_url(BASE + r["path"]) for r in REFERENCES)
    assert not approved_url("https://evil.siemens.cloud/manual")
    assert not approved_url("https://docs.tia.siemens.cloud.evil.invalid/manual")


def test_container_flags_pin_resources_endpoint_and_mount(monkeypatch, tmp_path):
    from eil import isolated_pdf as worker

    assets = tmp_path / ".eil/docling-models"
    assets.mkdir(parents=True)
    monkeypatch.setattr(worker, "ROOT", tmp_path)
    monkeypatch.setattr(worker, "DOCLING_ARTIFACTS", assets)
    monkeypatch.setattr(
        worker, "docker", lambda: ["C:/fixed/docker.exe", "--host", "fixed-local-engine"]
    )
    captured = []

    def inspect(args, **kwargs):
        captured.append(args)
        return subprocess.CompletedProcess(args, 0, ("sha256:" + "a" * 64).encode(), b"")

    monkeypatch.setattr(worker.subprocess, "run", inspect)
    command = worker.command("eil-pdf-fixed", self_test=True)
    assert captured[0][:3] == ["C:/fixed/docker.exe", "--host", "fixed-local-engine"]
    for option, value in (
        ("--network", "none"),
        ("--user", "65532:65532"),
        ("--cap-drop", "ALL"),
        ("--memory", "2g"),
        ("--memory-swap", "2g"),
        ("--cpus", "2"),
        ("--pids-limit", "128"),
    ):
        assert command[command.index(option) + 1] == value
    assert "--read-only" in command and "--privileged" not in command
    assert command[-2] == "sha256:" + "a" * 64
    assert sum("type=bind" in c for c in command) == 1
    assert "target=/models,readonly" in command[command.index("--mount") + 1]
    monkeypatch.setattr(worker, "DOCLING_ARTIFACTS", tmp_path.parent)
    with pytest.raises(RuntimeError, match="approved"):
        worker.command("eil-pdf-fixed")


def test_storage_api_requires_owner_and_admin(tmp_path):
    with TestClient(
        create_app(lambda: RunService(tmp_path)), base_url="http://127.0.0.1"
    ) as client:
        sign_in(client)
        case = client.post("/api/cases", json={"title": "Recoverable case"}).json()
        assert client.post(f"/api/cases/{case['id']}/trash").status_code == 200
        assert client.get(f"/api/cases/{case['id']}").status_code == 404
        assert client.get("/api/cases?deleted=true").json()["cases"][0]["id"] == case["id"]
        assert client.post(f"/api/cases/{case['id']}/restore").status_code == 200
        assert client.post("/api/admin/backups").status_code == 201
        assert (
            client.post(
                "/api/auth/users",
                json={
                    "username": "member",
                    "password": "Synthetic member password!",
                    "role": "member",
                },
            ).status_code
            == 201
        )
        client.post("/api/auth/logout")
        client.post(
            "/api/auth/login", json={"username": "member", "password": "Synthetic member password!"}
        )
        assert client.get("/api/admin/storage").status_code == 403
        assert client.post("/api/admin/backups").status_code == 403
        assert client.post(f"/api/cases/{case['id']}/trash").status_code == 404
        assert client.get("/api/cases?deleted=true").json()["cases"] == []


@pytest.mark.parametrize(
    "key", ["other-station", "no-increase", "conflicting-records", "missing-document"]
)
def test_extended_negative_graph_calibration(tmp_path, key):
    from eil.benchmark_extended import QUESTION, ScriptedV2Model, fixture, score
    from eil.execution import execute_run
    from eil.runs import RunStore

    case = fixture(tmp_path, key)
    store = RunStore(tmp_path)
    run = store.create(QUESTION, {"max_steps": 65, "max_total_tokens": 65536}, case_id=case["id"])
    store.change(
        run["id"],
        lambda r, c: r.update(experiment={"suite": "eil-benchmark-v2", "structured_output": True}),
    )
    store.claim()
    execute_run(tmp_path, run["id"], model=ScriptedV2Model(model="offline"))
    result, _ = score(store, run["id"], key)
    assert result["passed"], result
    from eil.claims import check_closed_finding

    finding = result["finding"]
    assert not check_closed_finding(store, run["id"], finding)
    assert check_closed_finding(store, run["id"], {**finding, "delta_pp": 99})
    if key != "missing-document":
        assert check_closed_finding(
            store,
            run["id"],
            {**finding, "citations": [c for c in finding["citations"] if c.startswith("csv:")]},
        )
