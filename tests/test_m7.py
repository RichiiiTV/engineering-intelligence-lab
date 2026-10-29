from eil.answer_contract import assess
from eil.knowledge import KnowledgeStore


def test_pdf_ranges_and_item_provenance_survive_library(tmp_path):
    library = KnowledgeStore(tmp_path)
    doc = library.add(
        "table.pdf",
        b"%PDF-fixture",
        title="Table",
        family="Demo",
        version="V20",
        license_note="CC0 fixture",
        data_policy="synthetic",
        actor="test",
        pdf_parser=lambda _: {
            "chunks": [
                {
                    "page": 1,
                    "pages": [1, 2],
                    "text": "A measurement table spanning two pages.",
                    "item_ref": "#/tables/0",
                    "bboxes": [{"page": 1}, {"page": 2}],
                    "offset": 0,
                }
            ]
        },
    )
    hit = library.search("table", [doc["id"]])["hits"][0]
    assert hit["pages"] == [1, 2] and hit["item_ref"] == "#/tables/0" and len(hit["bboxes"]) == 2


def test_explicit_version_excludes_incompatible_document_before_ranking(tmp_path):
    library = KnowledgeStore(tmp_path)
    docs = [
        library.add(
            v + ".txt",
            f"The minimum delay is {n} milliseconds.".encode(),
            title="Timing",
            family="Demo",
            version=v,
            license_note="CC0",
            data_policy="synthetic",
            actor="test",
        )
        for v, n in [("V19", 10), ("V20", 20)]
    ]
    result = library.search("For V20, what is the minimum delay?", [d["id"] for d in docs])
    assert {r["version"] for r in result["hits"]} == {"V20"}
    assert result["excluded_document_ids"] == [docs[0]["id"]]


def test_unobserved_citations_and_mismatched_quotes_need_review():
    run = {
        "use_library": True,
        "library_lookup": {
            "hits": [
                {
                    "citation_id": "kb:observed:p1:c0",
                    "text": "The timing limit depends on the controller firmware.",
                }
            ]
        },
    }
    assert assess(run, "Unsupported requirement [kb:unseen:p1:c0]")["outcome"] == "needs_review"
    assert (
        assess(run, "> The timing limit is always seven milliseconds.\n[kb:observed:p1:c0]")[
            "outcome"
        ]
        == "needs_review"
    )
    assert (
        assess(run, "> The timing limit depends on the controller firmware.\n[kb:observed:p1:c0]")[
            "outcome"
        ]
        == "references_checked"
    )
    assert (
        assess(
            {"use_library": True, "library_lookup": {"hits": []}}, "No supporting source was found."
        )["outcome"]
        == "no_support"
    )
