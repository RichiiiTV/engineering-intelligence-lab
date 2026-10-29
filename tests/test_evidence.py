import hashlib

import pytest
from langchain_core.messages import AIMessage, ToolMessage

from eil.agent import build_agent
from eil.case_tools import case_tools
from eil.evidence import EvidenceConflict, EvidenceNotFound, EvidenceStore, inspection_rows
from eil.exports import answer_citations, export_investigation
from eil.pdf_ingest import PDFBusy, PDFUnavailable, _slot, parse_pdf
from eil.runs import RunStore
from eil.service import RunService
from tests.evidence_fixtures import CSV_BYTES, PDF_BYTES, fixture_pdf_parser, golden_case
from tests.fakes import controlled_worker, wait_for_event
from tests.test_agent import OfflineOllama, call


def test_golden_document_page_table_and_csv_finding(tmp_path):
    store = EvidenceStore(tmp_path)
    case, pdf, csv = golden_case(store)
    assert pdf["page_count"] == 2 and pdf["table_count"] == 1
    assert pdf["sha256"] == hashlib.sha256(PDF_BYTES).hexdigest()
    search = store.search(case["id"], "S03 illumination exposure setpoint", limit=5)
    assert search["hits"][0]["page"] == 2
    table = next(h for h in search["hits"] if h["kind"] == "table")
    assert table["pages"] == [2]
    assert table["bboxes"] and "2400" in table["text"] and "800" in table["text"]
    finding = store.compare(case["id"], csv["id"])
    top = finding["ranking"][0]
    assert top["station_id"] == "S03"
    assert top["delta_percentage_points"] == 12.5021
    cite = store.resolve(case["id"], top["example_citations"][0])
    assert cite["row"]["row_id"] == "ROW-00003"
    assert cite["row"]["csv_line"] == 4
    assert finding["query_provenance"]["sha256"] == csv["sha256"]
    assert "not the complete aggregation" in finding["uncertainty"]


def test_other_cases_and_later_uploads_do_not_change_snapshot_ranking(tmp_path):
    store = EvidenceStore(tmp_path)
    a, pdf, csv = golden_case(store, "A")
    snapshot = store.snapshot(a["id"])
    before = store.search(a["id"], "S03 exposure", allowed=snapshot)
    b, other, _ = golden_case(store, "B")
    assert store.search(a["id"], "S03 exposure", allowed=snapshot) == before
    with pytest.raises(EvidenceNotFound):
        store.source(a["id"], other["id"])
    with pytest.raises(EvidenceNotFound):
        store.resolve(b["id"], before["hits"][0]["citation_id"])
    changed = CSV_BYTES.replace(b"ROW-00001", b"ROW-00001-NEW", 1)
    new = store.ingest(a["id"], "second.csv", changed)
    with pytest.raises(EvidenceNotFound):
        store.compare(a["id"], new["id"], snapshot)
    assert store.search(a["id"], "S03 exposure", allowed=snapshot) == before
    assert len(store.sources(a["id"])) == 3
    assert len(store.sources(a["id"], snapshot)) == 2


def test_multiple_csvs_have_distinct_row_citations_and_are_not_silently_combined(tmp_path):
    store = EvidenceStore(tmp_path)
    case, _, csv = golden_case(store)
    second = store.ingest(
        case["id"], "second.csv", CSV_BYTES.replace(b"ROW-00001", b"ANOTHER-ROW", 1)
    )
    a, b = (store.compare(case["id"], source) for source in (csv["id"], second["id"]))
    assert a["ranking"][0]["delta_percentage_points"] == b["ranking"][0]["delta_percentage_points"]
    assert a["ranking"][0]["example_citations"] != b["ranking"][0]["example_citations"]
    assert a["query_provenance"]["rows_used"] == 336


@pytest.mark.parametrize(
    "name", ["../outside.csv", "C:\\secrets.csv", "https://x/file.pdf", "a\x00.csv", "a.html"]
)
def test_filenames_never_become_host_paths(tmp_path, name):
    store = EvidenceStore(tmp_path)
    case = store.create_case("Invalid input")
    with pytest.raises(ValueError):
        store.ingest(case["id"], name, CSV_BYTES)
    assert store.sources(case["id"]) == []


@pytest.mark.parametrize(
    "content",
    [
        b"",
        b"\xff",
        b"wrong,columns\na,b\n",
        CSV_BYTES.replace(b"S01", b"../../secrets", 1),
        CSV_BYTES.replace(b"baseline", b"future", 1),
        CSV_BYTES.replace(b"2026-10-", b"NOT-A-DATE-", 1),
        b"\n".join(
            [CSV_BYTES.splitlines()[0], CSV_BYTES.splitlines()[1], CSV_BYTES.splitlines()[1]]
        ),
        b"x" * (2 * 1024 * 1024 + 1),
    ],
)
def test_invalid_csv_is_rejected_atomically(tmp_path, content):
    store = EvidenceStore(tmp_path)
    case = store.create_case("Bad CSV")
    with pytest.raises(ValueError):
        store.ingest(case["id"], "bad.csv", content)
    assert store.sources(case["id"]) == []


def test_rejection_count_validation_and_incomplete_periods(tmp_path):
    header = CSV_BYTES.splitlines()[0]
    invalid = header + b"\nX,2026-10-01,S01,baseline,10,8,4,600,2400\n"
    with pytest.raises(ValueError, match="counts"):
        inspection_rows(invalid)
    store = EvidenceStore(tmp_path)
    case = store.create_case("Incomplete")
    value = header + b"\nX,2026-10-01,S01,baseline,10,1,1,600,2400\n"
    source = store.ingest(case["id"], "partial.csv", value)
    with pytest.raises(ValueError, match="both baseline and incident"):
        store.compare(case["id"], source["id"])


def test_partial_station_coverage_is_not_reported_as_used_rows(tmp_path):
    store = EvidenceStore(tmp_path)
    case = store.create_case("Mixed coverage")
    content = CSV_BYTES.splitlines()[0] + (
        b"\nA,2026-10-01,S01,baseline,100,1,0,600,2400"
        b"\nB,2026-10-01,S03,baseline,100,1,0,600,2400"
        b"\nC,2026-10-11,S03,incident,100,15,0,340,800\n"
    )
    source = store.ingest(case["id"], "mixed.csv", content)
    result = store.compare(case["id"], source["id"])
    assert result["incomplete_stations"] == ["S01"]
    assert result["query_provenance"]["rows_scanned"] == 3
    assert result["query_provenance"]["rows_used"] == 2
    assert result["query_provenance"]["excluded_rows"] == 1


def test_duplicate_pdf_does_not_reconvert_and_source_limit_is_atomic(tmp_path):
    store = EvidenceStore(tmp_path)
    case = store.create_case("Quotas")
    calls = []

    def parser(content):
        calls.append(1)
        return fixture_pdf_parser(content)

    store.ingest(case["id"], "a.pdf", PDF_BYTES, pdf_parser=parser)
    with pytest.raises(EvidenceConflict):
        store.ingest(case["id"], "renamed.pdf", PDF_BYTES, pdf_parser=parser)
    assert len(calls) == 1
    for i in range(9):
        store.ingest(
            case["id"], f"data-{i}.csv", CSV_BYTES.replace(b"ROW-00001", f"CHANGED-{i}".encode(), 1)
        )
    with pytest.raises(EvidenceConflict, match="ten sources"):
        store.ingest(case["id"], "overflow.csv", CSV_BYTES)
    assert len(store.sources(case["id"])) == 10


def test_literal_search_handles_sql_and_fts_operators_as_data(tmp_path):
    store = EvidenceStore(tmp_path)
    case, _, _ = golden_case(store)
    result = store.search(case["id"], 'S03 "); DROP TABLE sources; -- OR NEAR(x)')
    assert all(h["case_id"] == case["id"] for h in result["hits"])
    assert len(store.sources(case["id"])) == 2
    assert store.search(case["id"], "unfindablecapybara")["hits"] == []


def test_case_tools_do_not_offer_default_fixture_or_execution_access(tmp_path):
    store = EvidenceStore(tmp_path)
    case, _, _ = golden_case(store)
    tools = case_tools(tmp_path, case["id"], store.snapshot(case["id"]))
    model = OfflineOllama(
        model="offline",
        responses=[call("compare_station_performance"), AIMessage(content="Unavailable")],
    )
    graph = build_agent(model=model, evidence_tools=tools)
    result = graph.invoke(
        {"messages": [{"role": "user", "content": "Compare sources"}]},
        config={"configurable": {"thread_id": "isolated"}},
    )
    expected = {
        "list_case_sources",
        "search_case_documents",
        "compare_case_stations",
        "read_case_citation",
        "ls",
        "read_file",
        "glob",
        "grep",
    }
    assert all(names == expected for names in model.bound_names)
    assert next(m for m in result["messages"] if isinstance(m, ToolMessage)).status == "error"


def test_real_graph_golden_case_and_export(tmp_path):
    case, _, _ = golden_case(EvidenceStore(tmp_path))
    with RunService(tmp_path, worker_target=controlled_worker) as runner:
        run = runner.submit("Investigate this case", case_id=case["id"])
        final = runner.wait(run["id"], timeout=25)
        report = export_investigation(runner.store, run["id"])
    assert final["status"] == "completed", final
    assert "S03" in final["result"]["answer"]
    assert report["citation_checks"]["unresolved"] == []
    assert report["citation_checks"]["not_returned_by_tools"] == []
    assert any(c.get("page") == 2 and c["cited_in_answer"] for c in report["citations"])
    assert any(
        c.get("row", {}).get("station_id") == "S03" and c["cited_in_answer"]
        for c in report["citations"]
    )
    assert {q["phase"] for q in report["query_provenance"]} == {"requested", "observed"}
    assert report["uncertainty"]["causation"] == "not_established"


def test_case_snapshot_survives_pause_upload_and_resume(tmp_path):
    store = EvidenceStore(tmp_path)
    case, _, _ = golden_case(store)
    with RunService(tmp_path, worker_target=controlled_worker) as runner:
        run = runner.submit("resume_case:keep sources frozen", case_id=case["id"])
        wait_for_event(runner.store, run["id"], "fake_blocked", timeout=25)
        runner.store.control(run["id"], "pause")
        assert runner.wait(run["id"], timeout=5)["status"] == "paused"
        extra = store.ingest(
            case["id"], "later.csv", CSV_BYTES.replace(b"ROW-00001", b"LATER-ROW", 1)
        )
        runner.store.control(run["id"], "resume")
        assert runner.wait(run["id"], timeout=25)["status"] == "completed"
        exported = export_investigation(runner.store, run["id"])
    assert extra["id"] not in {s["id"] for s in exported["source_snapshot"]}


def test_export_flags_unresolved_and_unobserved_citations(tmp_path):
    evidence = EvidenceStore(tmp_path)
    case, _, csv = golden_case(evidence)
    foreign, pdf, _ = golden_case(evidence, "Other case")
    store = RunStore(tmp_path)
    run = store.create("Unsupported citation", case_id=case["id"])
    store.claim()
    bad = f"pdf:{pdf['id']}:p2:c0"
    valid_but_unseen = f"csv:{csv['id']}:r0"
    store.finish(run["id"], "completed", result={"answer": f"Claim [{bad}] [{valid_but_unseen}]"})
    report = export_investigation(store, run["id"])
    assert report["citation_checks"]["unresolved"] == [bad]
    assert set(report["citation_checks"]["not_returned_by_tools"]) == {bad, valid_but_unseen}
    assert all(c["case_id"] != foreign["id"] for c in report["citations"])
    with pytest.raises(EvidenceNotFound):
        evidence.resolve(case["id"], valid_but_unseen + ":fake")


def test_grouped_citations_are_resolved_and_malformed_ones_are_explicit():
    source = "12345678-1234-1234-1234-123456789012"
    answer = f"Facts [csv:{source}:r2, r170] [pdf:{source}:p2:c13, c14, p3:c20]"
    cited, malformed = answer_citations(answer)
    assert cited == {
        f"csv:{source}:r2",
        f"csv:{source}:r170",
        f"pdf:{source}:p2:c13",
        f"pdf:{source}:p2:c14",
        f"pdf:{source}:p3:c20",
    }
    assert malformed == []
    assert answer_citations("No references") == (set(), [])
    assert answer_citations("[pdf:../../host]")[1] == ["pdf:../../host"]
    assert answer_citations(f"[csv:{source}:r2, r3-r500]")[1]


def test_pdf_conversion_has_admission_and_time_limits(monkeypatch):
    _slot.acquire()
    try:
        with pytest.raises(PDFBusy):
            parse_pdf(PDF_BYTES)
    finally:
        _slot.release()

    def isolated_timeout(content, *, timeout):
        assert timeout == 0.001
        raise RuntimeError("Isolated PDF conversion timed out")

    monkeypatch.setattr("eil.isolated_pdf.convert", isolated_timeout)
    with pytest.raises(PDFUnavailable, match="timed out"):
        parse_pdf(PDF_BYTES, timeout=0.001)
