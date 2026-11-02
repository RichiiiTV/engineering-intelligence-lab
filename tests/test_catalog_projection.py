"""Generated catalog observations stay concise without losing evidence or warnings."""

import copy
import json

import pytest

from eil.catalog_tools import catalog_tools
from eil.exports import export_investigation
from eil.runs import RunStore


def generated_lookup():
    document_id = "00000000-0000-4000-8000-000000000001"
    hit = {
        "id": document_id,
        "citation_id": f"kb:{document_id}:p4:c0",
        "title": "Generated conveyor manual",
        "filename": "generated-conveyor.pdf",
        "family": "Generated XR7",
        "version": "V2.1",
        "profile": {"model": "XR7", "firmware": "F3", "software_version": "V2.1"},
        "data_policy": "synthetic",
        "kind": "table",
        "page": 4,
        "pages": [4, 5],
        "multi_page_item": True,
        "item_ref": "#/tables/0",
        "bboxes": [{"page": 4, "l": 1, "t": 2, "r": 3, "b": 4}],
        "section": "Generated diagnostics",
        "line_start": 12,
        "line_end": 13,
        "offset": 1600,
        "text": "Störung E17: Sensor bleibt belegt.\nThis does not prove a defective sensor.",
        "compatibility_notice": "The firmware of the actual machine is unverified.",
        "license_note": "CC0 generated fixture. " * 8,
        "sha256": "a" * 64,
        "size": 12345,
        "created_at": "2026-01-01T00:00:00Z",
        "created_by": "generated-admin",
        "machine_id": "generated-machine",
        "ingestion_job_id": "generated-job",
        "classification": {"identity_evidence": "Generated machine XR7 " * 8},
        "assignment_basis": "generated-fixture",
    }
    return {
        "status": "identified",
        "machine": {
            "id": "generated-machine",
            "name": "XR7",
            "identity_kind": "product_family",
            "basis": "semantic-inference",
        },
        "hits": [copy.deepcopy(hit) for _ in range(3)],
        "query": "Generated current question and untrusted prior problem context.",
        "document_ids": [document_id],
        "embedding_model": "generated-embedding@" + "b" * 64,
        "method": "hybrid-bm25-sqlite-vec-rrf-v1",
        "semantic_available": False,
        "notice": "Semantic search unavailable; keyword search was used.",
        "matching_notice": "Machine matching is an inference; ask for missing versions.",
        "uncertainty": "Retrieval relevance does not establish compatibility.",
        "excluded_document_ids": ["generated-incompatible-source"],
        "product_context": {"family": "Generated XR7", "software_version": "V2.1"},
        "compatibility_notice": "Generated model family, not verified installed equipment.",
    }


def test_fresh_and_cached_catalog_projection_preserves_evidence_and_raw_export(
    tmp_path, monkeypatch
):
    runs = RunStore(tmp_path)
    run = runs.create(
        "What does generated XR7 error E17 mean?",
        owner_id="generated-member",
        chat_mode=True,
        automatic_catalog=True,
    )
    original = generated_lookup()
    frozen = copy.deepcopy(original)
    calls = []

    def lookup(directory, row, hint):
        calls.append((row["id"], hint))
        return original

    monkeypatch.setattr("eil.catalog_tools.route", lookup)
    read = catalog_tools(tmp_path, run["id"])[0]
    wire = read()
    observed = json.loads(wire)
    assert len(wire) < len(json.dumps(original)) * 0.7
    assert original == frozen
    assert "query" not in observed and "embedding_model" not in observed
    assert "document_ids" not in observed
    for key in (
        "status",
        "machine",
        "notice",
        "matching_notice",
        "uncertainty",
        "excluded_document_ids",
        "product_context",
        "compatibility_notice",
    ):
        assert observed[key] == original[key]
    for hit in observed["hits"]:
        assert "created_by" not in hit and "classification" not in hit
        for key in (
            "id",
            "citation_id",
            "text",
            "title",
            "filename",
            "family",
            "version",
            "profile",
            "data_policy",
            "kind",
            "page",
            "pages",
            "multi_page_item",
            "item_ref",
            "bboxes",
            "section",
            "line_start",
            "line_end",
            "compatibility_notice",
        ):
            assert hit[key] == original["hits"][0][key]
        assert "offset" not in hit  # Byte offsets are not source line numbers.
    saved = runs.get(run["id"])
    assert saved["catalog_lookup"] == frozen
    report = export_investigation(runs, run["id"])
    assert report["catalog_routing"] == {k: v for k, v in frozen.items() if k != "hits"}
    assert read("ignored cached hint") == wire
    assert len(calls) == 1
    assert runs.get(run["id"])["catalog_lookup"] == frozen
    assert export_investigation(runs, run["id"]) == report
    for key in ("limits", "tokens", "model_calls", "tool_calls", "steps", "catalog_snapshot"):
        assert runs.get(run["id"])[key] == run[key]


@pytest.mark.parametrize("cached", [False, True])
def test_catalog_projection_keeps_clarification_instead_of_guessing(tmp_path, monkeypatch, cached):
    runs = RunStore(tmp_path)
    run = runs.create("Generated machine error", chat_mode=True, automatic_catalog=True)
    raw = {
        "status": "needs_clarification",
        "question": "Welche Maschine ist betroffen — XR7 oder AB9?",
        "candidates": [{"id": "generated-xr7", "name": "XR7"}],
        "hits": [],
        "semantic_available": False,
        "notice": "No machine selected. Do not diagnose against one candidate.",
    }
    if cached:
        runs.change(run["id"], lambda row, conn: row.update(catalog_lookup=raw))

    def lookup(*args):
        assert not cached, "Cached clarification must not reroute or spend model tokens"
        return raw

    monkeypatch.setattr("eil.catalog_tools.route", lookup)
    read = catalog_tools(tmp_path, run["id"])[0]
    assert json.loads(read()) == raw
    assert runs.get(run["id"])["catalog_lookup"] == raw
    with pytest.raises(ValueError, match="short machine/model hint"):
        read("x" * 121)
    assert runs.get(run["id"])["catalog_lookup"] == raw
