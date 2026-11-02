import copy
import json

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from eil.agent import CHAT_SYSTEM_PROMPT, SYSTEM_PROMPT, build_agent
from eil.answer_contract import assess
from eil.quality_followup import PACK_HASH, main, pack_content, score
from tests.test_agent import make_model


def generated_run(answer):
    cid = "kb:00000000-0000-4000-8000-000000000001:p1:c0"
    hit = {"citation_id": cid, "text": "Example MCU STM32F446, bootloader32KiB."}
    return {
        "status": "completed",
        "question": "Which MCU and bootloader for Voron 2.4?",
        "automatic_catalog": True,
        "catalog_lookup": {"status": "identified", "hits": [hit]},
        "result": {
            "answer": answer + " [" + cid + "]",
            "answer_contract": {"outcome": "references_checked"},
        },
    }


def test_new_public_quality_fixture_preserves_original_pack_and_old_results(monkeypatch, capsys):
    import hashlib

    import httpx

    monkeypatch.setattr(httpx.Client, "send", lambda *a, **k: pytest.fail("Plan attempted network"))
    assert main([]) == 0
    assert json.loads(capsys.readouterr().out)["mode"] == "plan-only"
    assert hashlib.sha256(pack_content()).hexdigest() == PACK_HASH


def test_controller_quality_rejects_the_original_wrong_subject_and_vendor_failure():
    assert score("controller", generated_run("STM32F446 and 32 KiB"))["passed"]
    bad = generated_run("Poor gantry squaring causes first-layer issues; suggests Siemens.")
    frozen = copy.deepcopy(bad)
    result = score("controller", bad)
    assert not result["passed"] and not result["checks"]["documented_controller"]
    assert bad == frozen
    assert result["claim_entailment"] == "not_verified"
    assert not score("controller", generated_run("MCU is not STM32F446; bootloader is not 32 KiB"))[
        "passed"
    ]


@pytest.mark.parametrize(
    "answer",
    [
        "The source does not suggest Siemens.",
        "There is no Siemens PLC information in these sources.",
        "Es ist keine Siemens SPS dokumentiert.",
    ],
)
def test_vendor_denial_does_not_trigger_unnecessary_repair(answer):
    assert not any(
        "Vendor identification" in issue for issue in assess(generated_run(""), answer)["issues"]
    )


def test_opaque_ids_do_not_establish_vendor_but_human_context_can():
    run = generated_run("")
    cid = run["catalog_lookup"]["hits"][0]["citation_id"]
    assert any(
        "Vendor identification" in issue for issue in assess(run, f"Siemens PLC [{cid}]")["issues"]
    )
    run["question"] = "My Siemens PLC: which version?"
    assert not any(
        "Vendor identification" in issue for issue in assess(run, f"Siemens PLC [{cid}]")["issues"]
    )
    assert assess(run, f"Siemens PLC [{cid}]")["claim_entailment"] == "not_verified"


def test_chat_has_neutral_framing_without_changing_inspection_benchmark():
    assert "demo inspection" in SYSTEM_PROMPT and "demo inspection" not in CHAT_SYSTEM_PROMPT
    model = make_model(AIMessage(content="Please provide the manual."))
    graph = build_agent(model=model, chat_mode=True, case_evidence=False, evidence_tools=[])
    result = graph.invoke(
        {"messages": [HumanMessage(content="Generated machine fault")]},
        config={"configurable": {"thread_id": "quality-framing"}},
    )
    assert result["messages"][-1].text == "Please provide the manual."


def test_cited_passage_must_contain_literal_technical_values_and_repair_is_bounded(tmp_path):
    from eil.execution import RunMiddleware
    from eil.runs import RunStore

    runs = RunStore(tmp_path)
    run = runs.create("Which MCU?", chat_mode=True, automatic_catalog=True)
    cid = "kb:00000000-0000-4000-8000-000000000001:p1:c0"
    good = cid.replace("c0", "c10")
    lookup = {
        "status": "identified",
        "hits": [
            {"citation_id": cid, "text": "Public product overview."},
            {"citation_id": good, "text": "Compile for STM32F446 with a32KiB bootloader."},
        ],
    }
    runs.change(run["id"], lambda row, conn: row.update(catalog_lookup=lookup))
    wrong = AIMessage(content=f"STM32F446, 32 KiB [{cid}]")
    state = {"messages": [wrong]}
    assert assess(runs.get(run["id"]), wrong.text)["outcome"] == "needs_review"
    repair = RunMiddleware(runs, run["id"]).after_model(state, None)
    assert repair["jump_to"] == "model"
    assert "passage you cite" in repair["messages"][0].text
    assert RunMiddleware(runs, run["id"]).after_model(state, None) is None
    final = assess(runs.get(run["id"]), f"STM32F446, 32 KiB [{good}]")
    assert final["outcome"] == "references_checked" and final["claim_entailment"] == "not_verified"
