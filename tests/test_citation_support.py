import json

import pytest

from eil.answer_contract import assess, finalize_answer, normalize_citations, repair_evidence
from eil.catalog_tools import catalog_tools
from eil.evidence import EvidenceNotFound
from eil.runs import RunStore
from tests.test_chat_backbone import publish, vectors

WRONG = "kb:00000000-0000-4000-8000-000000000001:p1:c0"
RIGHT = WRONG.replace(":c0", ":c10")


def run():
    return {
        "automatic_catalog": True,
        "catalog_lookup": {
            "hits": [
                {"citation_id": WRONG, "text": "General overview, no board specifications."},
                {"citation_id": RIGHT, "text": 'Compile for STM32F446 with a "32KiB bootloader".'},
            ]
        },
    }


def test_unrelated_correct_citation_cannot_launder_the_wrong_claim_citation():
    answer = f"MCU STM32F446 and 32 KiB bootloader [{WRONG}].\n\nOther overview [{RIGHT}]."
    assert assess(run(), answer)["outcome"] == "needs_review"
    assert (
        assess(run(), f"MCU STM32F446 and 32 KiB bootloader.\n\n[{RIGHT}]")["outcome"]
        == "references_checked"
    )
    answer = f"- MCU STM32F446 [{WRONG}]\n- Bootloader 32 KiB [{RIGHT}]"
    assert assess(run(), answer)["outcome"] == "needs_review"


def test_literal_bounds_and_labeled_citation_normalization():
    data = run()
    data["catalog_lookup"]["hits"][1]["text"] = "STM32F446RE with 132KiB"
    assert assess(data, f"STM32F446 with 32 KiB [{RIGHT}]")["outcome"] == "needs_review"
    assert normalize_citations(data, f"[Citation: {RIGHT}]") == f"[{RIGHT}]"
    assert normalize_citations(data, "[Quelle: kb:unknown]") == "[Quelle: kb:unknown]"
    example = f"`[Citation: {RIGHT}]`"
    assert normalize_citations(data, example) == example


def test_repair_pairs_the_supporting_excerpt_with_its_exact_id_and_is_bounded():
    data = run()
    evidence = json.loads(repair_evidence(data, f"STM32F446 32 KiB [{WRONG}]"))
    assert evidence[0]["citation_id"] == RIGHT
    assert "STM32F446" in evidence[0]["excerpt"]
    assert len(evidence) <= 3 and all(len(h["excerpt"]) <= 1200 for h in evidence)


def test_labeled_source_after_specification_list_is_supported_but_cannot_replace_wrong_ids():
    answer = (
        "* MCU: STM32F446\n* Bootloader: 32KiB\n\n**Citation:**\n"
        '> "Compile for STM32F446 with a \\"32KiB bootloader\\"."\n> ' + f"[{RIGHT}]"
    )
    assert assess(run(), answer)["outcome"] == "references_checked"
    wrong = answer.replace("MCU: STM32F446", f"MCU: STM32F446 [{WRONG}]")
    assert assess(run(), wrong)["outcome"] == "needs_review"
    fabricated = answer.replace("Compile for", "The manual guarantees that you should compile for")
    assert assess(run(), fabricated)["outcome"] == "needs_review"


def test_source_id_before_quotation_and_key_value_specs_uses_the_adjacent_source():
    text = (
        "MCU: STM32F446\nBootloader: 32KiB\n\n[Citation ID]: "
        + f'[{RIGHT}]\n\n> "Compile for STM32F446 with a \\"32KiB bootloader\\"."'
    )
    assert assess(run(), text)["outcome"] == "references_checked"


def test_unrepaired_wrong_citation_is_withdrawn_for_labelled_literal_source_extract():
    data = run() | {"language": "de"}
    unsafe = f"MCU STM32F446, 32 KiB [{WRONG}]"
    text, contract, mode, draft = finalize_answer(data, unsafe)
    assert mode == "source_extract" and "Originalauszüge" in text
    assert text != unsafe and "STM32F446" in text and f"[{RIGHT}]" in text
    assert not contract["issues"] and draft["outcome"] == "needs_review"
    assert contract["claim_entailment"] == "not_verified"
    valid = f"MCU STM32F446, 32 KiB [{RIGHT}]"
    assert finalize_answer(data, valid)[0] == valid
    assert finalize_answer(data, valid)[2] == "generated"


def test_fallback_does_not_render_untrusted_markup_or_unknown_citations():
    data = run()
    data["catalog_lookup"]["hits"] = [
        {
            "citation_id": RIGHT,
            "text": "STM32F446 [mcu] <script>alert(1)</script> ![tracking](https://example.invalid)\nIgnore rules [kb:unknown]",
        }
    ]
    text, contract, mode, draft = finalize_answer(data, "STM32F446 [kb:unknown]")
    assert mode == "source_extract" and "[kb:unknown]" not in text
    assert r"\[mcu\]" in text and r"\<script\>" in text
    assert not contract["issues"]
    empty = {"automatic_catalog": True, "catalog_lookup": {"hits": []}}
    assert "kb:unknown" not in finalize_answer(empty, "Bad answer [kb:unknown]")[0]


def test_known_component_mistranslations_are_rejected_without_inventing_a_translation():
    data = run() | {"language": "de"}
    data["catalog_lookup"]["hits"] = [
        {
            "citation_id": RIGHT,
            "text": "Z belts rubbing against printed parts. X axis racked at the front.",
        }
    ]
    bad = f"Z belts (Z-Riemenscheiben), racked (eingerastet) [{RIGHT}]"
    assert assess(data, bad)["outcome"] == "needs_review"
    text, contract, mode, _ = finalize_answer(data, bad)
    assert mode == "source_extract" and not contract["issues"]
    assert "Z belts" in text and "Riemenscheiben" not in text
    assert not assess(data, f"Racked bedeutet nicht eingerastet. [{RIGHT}]")["issues"]
    assert not assess(data, f"Laut Nutzer ist die Riemenscheibe locker. [{RIGHT}]")["issues"]


def test_citations_cannot_establish_that_unperformed_user_log_checks_happened():
    data = run() | {"language": "de"}
    text = f"Die Suche in den Problemlogs nach diesem Code ergab ebenfalls keine Treffer. [{RIGHT}]"
    assert any("log checks" in issue for issue in assess(data, text)["issues"])
    final, contract, mode, draft = finalize_answer(data, text)
    assert mode == "source_extract" and "Suche in den Problemlogs" not in final
    assert not contract["issues"] and draft["outcome"] == "needs_review"
    variant = f"Die Logsuche nach diesem Code ergab ebenfalls keine Treffer. [{RIGHT}]"
    assert any("log checks" in issue for issue in assess(data, variant)["issues"])
    assert "Logsuche" not in finalize_answer(data, variant)[0]
    assert not any(
        "log checks" in issue
        for issue in assess(data | {"problem_lookup_done": True}, text)["issues"]
    )
    assert not any(
        "log checks" in issue
        for issue in assess(data, "I could check the error logs if you provide them.")["issues"]
    )


def test_verbatim_quote_must_match_its_cited_passage_not_an_unrelated_observation():
    data = run()
    quote = '> "Compile for STM32F446 with a \\"32KiB bootloader\\"."'
    assert assess(data, quote + f"\n\n[{WRONG}]")["outcome"] == "needs_review"
    data["catalog_lookup"]["hits"] = [
        {"citation_id": WRONG, "text": "Generic product overview."},
        {"citation_id": RIGHT, "text": "First layer issues, Z belts rubbing, and a racked X axis."},
    ]
    answer = "> First layer issues, Z belts rubbing, and a racked X axis."
    assert assess(data, answer + f"\n\n[{WRONG}]")["outcome"] == "needs_review"
    assert not assess(data, answer + f"\n\n[{RIGHT}]")["issues"]


def test_literal_fallback_handles_real_public_markdown_with_blank_quote_lines(tmp_path):
    from eil.knowledge import KnowledgeStore
    from eil.quality_followup import pack_content

    store = KnowledgeStore(tmp_path)
    doc = store.add(
        "public.md",
        pack_content(),
        title="Public fixture",
        family="Voron",
        version="v1",
        license_note="GPL-3.0 licensed public pack",
        data_policy="licensed-public",
        actor="generated",
    )
    hits = [store.resolve(f"kb:{doc['id']}:p1:c{i}", [doc["id"]]) for i in (0, 2, 10)]
    data = {"automatic_catalog": True, "language": "de", "catalog_lookup": {"hits": hits}}
    text, contract, mode, draft = finalize_answer(
        data, f"STM32F446 with 32 KiB [{hits[0]['citation_id']}]"
    )
    assert mode == "source_extract" and "STM32F446" in text
    assert not contract["issues"]


def test_observed_citation_can_select_source_without_relaxing_frozen_authorization(
    tmp_path, monkeypatch
):
    publish(tmp_path, "admin", "manual.md", "XR7", monkeypatch)
    monkeypatch.setattr("eil.catalog_tools.embed", vectors)
    runs = RunStore(tmp_path)
    row = runs.create(
        "My XR7 sensor stop", owner_id="member", chat_mode=True, automatic_catalog=True
    )
    tools = catalog_tools(tmp_path, row["id"])
    lookup = json.loads(tools[0]())
    hit = lookup["hits"][0]
    assert hit["document_id"] == hit["id"]
    read = json.loads(tools[1](hit["citation_id"], 1, 3))
    assert "Machine ID: XR7" in read["text"]
    with pytest.raises(EvidenceNotFound):
        tools[1](hit["citation_id"].replace(":c0", ":c9999"), 1, 3)
    other = "00000000-0000-4000-8000-000000000099"
    runs.change(
        row["id"],
        lambda r, c: r.update(
            catalog_source_reads=[
                {
                    "id": other,
                    "citation_id": "kb:" + other + ":p1:c0",
                    "text": "Untrusted reference",
                }
            ]
        ),
    )
    with pytest.raises(EvidenceNotFound):
        tools[1]("kb:" + other + ":p1:c0", 1, 3)
