import hashlib
import json

from eil.answer_contract import assess, normalize_citations
from eil.knowledge import KnowledgeStore
from eil.text_sources import line_hits, plain_chunks


def document(store, text):
    meta = store.add(
        "generated.md",
        text.encode(),
        title="Generated manual",
        family="Fixture",
        version="v1",
        license_note="CC0 generated",
        data_policy="synthetic",
        actor="fixture",
    )
    return store.document(meta["id"])


def test_legacy_plain_source_read_returns_actual_later_passage_without_mutation(tmp_path):
    store = KnowledgeStore(tmp_path)
    text = "\n".join(f"Generated reference line {i:04d}: bounded fixture text." for i in range(500))
    doc = document(store, text)
    with store.evidence.connection() as conn:
        conn.execute(
            "UPDATE knowledge_passages SET metadata=? WHERE document_id=?",
            (json.dumps({"page": 1}), doc["id"]),
        )
    hits = line_hits(store, doc, 340, 345)
    assert hits and all(int(h["citation_id"].rsplit(":c", 1)[1]) > 8 for h in hits)
    assert all(340 <= h["line_start"] <= h["line_end"] <= 345 for h in hits)
    assert all(h["text"] in text for h in hits)
    with store.evidence.connection() as conn:
        assert all(
            json.loads(row[0]) == {"page": 1}
            for row in conn.execute(
                "SELECT metadata FROM knowledge_passages WHERE document_id=?", (doc["id"],)
            )
        )
    assert store.document(doc["id"])["sha256"] == hashlib.sha256(text.encode()).hexdigest()


def test_long_line_does_not_attach_another_chunks_specification(tmp_path):
    store = KnowledgeStore(tmp_path)
    text = "x" * 2500 + " MCU STM32F446 with32KiB bootloader. " + "y" * 500
    doc = document(store, text)
    hits = line_hits(store, doc, 1, 1)
    first = next(h for h in hits if h["citation_id"].endswith(":c0"))
    assert "STM32F446" not in first["text"]
    assert any("STM32F446" in h["text"] for h in hits)
    assert len(first["text"]) <= 1200


def test_plain_locations_preserve_exact_old_chunk_text_and_page_ordinal():
    text = "a\r\n" * 500 + "\f" + "b\n" * 700
    old = [
        {"page": n + 1, "text": page[start : start + 1200]}
        for n, page in enumerate(text.split("\f"))
        for start in range(0, len(page), 1000)
        if page[start : start + 1200].strip()
    ]
    new = plain_chunks(text)
    assert [{"page": c["page"], "text": c["text"]} for c in new] == old
    assert all(c["line_start"] <= c["line_end"] for c in new)


def test_only_observed_markdown_citations_are_normalized():
    cid = "kb:00000000-0000-4000-8000-000000000001:p1:c0"
    run = {
        "automatic_catalog": True,
        "catalog_lookup": {"hits": [{"citation_id": cid, "text": "Generated source"}]},
    }
    assert normalize_citations(run, f"[Manual]({cid})") == f"Manual [{cid}]"
    assert (
        normalize_citations(run, "[Link](https://external.invalid)")
        == "[Link](https://external.invalid)"
    )
    assert normalize_citations(run, "[Unknown](kb:unknown)") == "[Unknown](kb:unknown)"
    code = f"```md\n[Manual]({cid})\n```"
    assert normalize_citations(run, code) == code
    assert assess(run, f"[Manual]({cid})")["observed_citation_count"] == 1


def test_technical_abstentions_do_not_consume_a_repair():
    cid = "kb:00000000-0000-4000-8000-000000000001:p1:c0"
    run = {
        "automatic_catalog": True,
        "catalog_lookup": {"hits": [{"citation_id": cid, "text": "Generic overview"}]},
    }
    for sentence in (
        "The supplied manual does not establish whether STM32F446 is supported.",
        "The source cannot determine the required32 KiB bootloader.",
        "Die Quellen enthalten keine Angaben zur STM32F446.",
    ):
        assert not any(
            "technical identifiers" in s for s in assess(run, sentence + f" [{cid}]")["issues"]
        )
