import uuid
from types import SimpleNamespace

import pytest

from eil.evidence import EvidenceConflict, EvidenceNotFound
from eil.machines import MachineStore, machine_tools
from eil.notebooks import NotebookStore
from eil.runs import RunStore
from tests.test_m8 import source, vector


def test_notebook_followup_has_frozen_sources_context_budget_and_idempotency(tmp_path, monkeypatch):
    monkeypatch.setattr("eil.knowledge.embed", vector)
    machines = MachineStore(tmp_path)
    m = machines.create("a", "A")
    docs = machines.documents(m["id"], "a")
    first = source(docs)
    notebooks = NotebookStore(tmp_path)
    n = notebooks.create(m["id"], "a", "Stops")
    runs = RunStore(tmp_path)
    service = SimpleNamespace(submit=runs.create)
    request = str(uuid.uuid4())
    r = notebooks.submit(n["id"], "a", "Why does the sensor stop the motor?", request, service)
    assert notebooks.submit(n["id"], "a", r["question"], request, service)["id"] == r["id"]
    with pytest.raises(EvidenceConflict):
        notebooks.submit(n["id"], "a", "Changed", request, service)
    with pytest.raises(EvidenceConflict):
        notebooks.submit(n["id"], "a", "Next?", str(uuid.uuid4()), service)
    with pytest.raises(EvidenceConflict):
        notebooks.select(n["id"], "a", [], [])
    runs.change(
        r["id"],
        lambda row, c: row.update(
            status="completed",
            result={"answer": "The sensor condition stops the motor."},
            tokens=200,
        ),
    )
    later = source(docs, b"New sensor logic version; diagnose drive alarms.")
    follow = notebooks.submit(n["id"], "a", "Where is that condition?", str(uuid.uuid4()), service)
    assert (
        follow["machine_document_ids"] == [first["id"]]
        and later["id"] not in follow["machine_document_ids"]
    )
    assert (
        follow["thread_id"] != r["thread_id"]
        and follow["tokens"] == 0
        and runs.get(r["id"])["tokens"] == 200
    )
    assert follow["notebook_context"]["history"][0]["run_id"] == r["id"]
    assert not follow["siemens"]
    import json

    assert json.loads(machine_tools(tmp_path, follow["id"])[0]())["hits"]
    runs.change(follow["id"], lambda row, c: row.update(status="cancelled"))
    notebooks.select(n["id"], "a", [later["id"]], [])
    assert runs.get(r["id"])["machine_document_ids"] == [first["id"]]
    assert notebooks.get(n["id"], "a")["revision"] == 2
    with pytest.raises(EvidenceNotFound):
        notebooks.get(n["id"], "b")
    other = machines.create("a", "Other")
    with pytest.raises(EvidenceNotFound):
        notebooks.get(n["id"], "a", other["id"])
    with pytest.raises(EvidenceNotFound):
        notebooks.select(n["id"], "a", [str(uuid.uuid4())], [])


def test_notebook_history_is_bounded_and_public_query_is_independent(tmp_path):
    m = MachineStore(tmp_path).create("a", "Private machine")
    notebooks = NotebookStore(tmp_path)
    n = notebooks.create(m["id"], "a", "Notebook")
    runs = RunStore(tmp_path)
    service = SimpleNamespace(submit=runs.create)
    for _ in range(7):
        r = notebooks.submit(n["id"], "a", "Private subject " * 70, str(uuid.uuid4()), service)
        runs.change(
            r["id"],
            lambda row, c: row.update(
                status="completed", result={"answer": "Untrusted private answer " * 500}
            ),
        )
    public = {
        "question": "Which public manual covers S7-1200?",
        "family": "",
        "cpu": "",
        "firmware": "",
        "tia_version": "",
    }
    next_run = notebooks.submit(
        n["id"], "a", "Private follow-up", str(uuid.uuid4()), service, siemens=public
    )
    assert len(next_run["notebook_context"]["history"]) == 4
    assert next_run["notebook_context"]["omitted_turns"] == 3
    assert next_run["siemens"] == public and next_run["siemens"]["question"] != next_run["question"]
    assert (
        sum(len(h["question"]) + len(h["answer"]) for h in next_run["notebook_context"]["history"])
        <= 12800
    )
