import json
import uuid
from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from eil.answer_contract import assess
from eil.catalog_tools import route
from eil.chat import ChatStore
from eil.execution import execute_run
from eil.problem_sources import parse
from eil.runs import RunStore
from eil.siemens_chat import reference_tool
from eil.siemens_routing import automatic_public_query
from eil.vision import visual_only_question
from tests.test_siemens_chat import ChatProbe, public_response


@pytest.mark.parametrize(
    "question,identifier",
    [
        ("Meine Maschine XY mit Siemens S7-1500 zeigt Fehler 16#80A1", "16#80A1"),
        ("Meine S7 1200 hat Statuscode 80b1, interne Linie geheim", "16#80B1"),
        ("S7-1200 G2 meldet 0x80A1", "16#80A1"),
        ("Meine S7-1500 meldet OB82", "OB82"),
    ],
)
def test_canonical_diagnostics_only(question, identifier):
    query = automatic_public_query(question)
    assert query and identifier in query["question"]
    assert "Deutsch" in query["question"]
    assert not any(value in json.dumps(query) for value in ["Maschine XY", "geheim", "Linie"])


@pytest.mark.parametrize(
    "question",
    [
        "Meine Maschine XY zeigt E17",
        "Siemens PLC error 80A1",
        "S7-1500 Fehler E17",
        "S7-1500 16#80A1 nur lokal",
        "S7-1500 16#80A1 keine externe Suche",
        "S7-1500 oder S7-1200 16#80A1",
        "S7-1500 16#80A100DEADBEEF",
        "S7-1500 zeigt Statuscode 1234",
        "S7-1500 16#80A1 do not search online",
        "S7-1500 16#80A1 nicht an Siemens senden",
        "S7-1500 16#80A1 don't send to Siemens",
        "S7-1500 Passwort=16#80A1, Fehler unbekannt",
        "S7-1500 16#80A1",
    ],
)
def test_ambiguous_private_or_opted_out_questions_stay_local(question):
    assert automatic_public_query(question) is None


def test_ordinary_german_chat_uses_fixed_mcp_query_once_with_no_private_context(
    tmp_path, monkeypatch
):
    sent = []

    async def search(question):
        sent.append(question)
        return public_response(question)

    monkeypatch.setattr("eil.siemens_mcp.search", search)
    runs = RunStore(tmp_path)
    chats = ChatStore(tmp_path)
    run = chats.submit(
        "member",
        "Meine geheime Maschine XY zeigt an der S7-1500 den Fehler 16#80A1",
        str(uuid.uuid4()),
        SimpleNamespace(submit=runs.create),
        [parse("internal.log", b"PRIVATE 16#DEAD password: confidential")],
    )
    assert run["siemens"]
    assert run["chat_context"]["siemens_routing"] == "canonical-human-diagnostic"
    read = reference_tool(tmp_path, run["id"])
    first, second = json.loads(read()), json.loads(read())
    assert first == second and len(sent) == 1 and "16#80A1" in sent[0]
    assert not any(
        t in sent[0] for t in ["geheim", "XY", "PRIVATE", "DEAD", "password", "confidential"]
    )
    # New natural-language follow-up never inherits an external query or uses old log codes.
    runs.change(run["id"], lambda row, _: row.update(status="completed"))
    follow = chats.submit(
        "member",
        "Was könnte intern falsch sein?",
        str(uuid.uuid4()),
        SimpleNamespace(submit=runs.create),
        conversation_id=run["chat_context"]["id"],
    )
    assert follow["siemens"] is None


def test_private_log_alone_cannot_enable_siemens(tmp_path):
    runs = RunStore(tmp_path)
    run = ChatStore(tmp_path).submit(
        "a",
        "Meine Maschine XY zeigt diesen Fehler",
        str(uuid.uuid4()),
        SimpleNamespace(submit=runs.create),
        [parse("error.log", b"S7-1500 16#80A1")],
    )
    assert run["siemens"] is None


def test_hex_looking_secrets_are_excluded_from_an_otherwise_public_diagnostic():
    query = automatic_public_query("S7-1500 Fehler 16#80A1. Passwort=16#DEAD")
    assert query and "80A1" in query["question"] and "DEAD" not in query["question"]


def test_german_safety_and_image_reading_are_not_bypasses():
    run = {"automatic_catalog": True, "catalog_lookup": {"status": "identified", "hits": []}}
    assert (
        assess(run, "Das ist eine Sicherheitsfunktion mit Not-Halt.")["outcome"] == "needs_review"
    )
    assert visual_only_question("Was steht auf diesem Bild?")
    assert not visual_only_question("Was bedeutet der Code im Bild?")


def test_graph_requires_automatic_siemens_lookup_with_german_system_instruction(
    tmp_path, monkeypatch
):
    from eil import execution

    sent = []
    prompts = []

    async def search(question):
        sent.append(question)
        return public_response(question)

    monkeypatch.setattr("eil.siemens_mcp.search", search)
    original = execution.build_agent

    def build(**kwargs):
        prompts.append(kwargs.get("extra_prompt", ""))
        return original(**kwargs)

    monkeypatch.setattr(execution, "build_agent", build)
    runs = RunStore(tmp_path)
    run = ChatStore(tmp_path).submit(
        "a", "S7-1500 Fehler 16#80A1", str(uuid.uuid4()), SimpleNamespace(submit=runs.create)
    )
    runs.claim()

    class Probe(ChatProbe):
        def _generate(self, messages, **kwargs):
            if not any(
                isinstance(m, ToolMessage) and m.name == "read_workspace_knowledge"
                for m in messages
            ):
                return ChatResult(
                    generations=[
                        ChatGeneration(
                            message=AIMessage(
                                content="",
                                tool_calls=[
                                    {
                                        "name": "read_workspace_knowledge",
                                        "args": {},
                                        "id": "catalog",
                                        "type": "tool_call",
                                    }
                                ],
                                usage_metadata={
                                    "input_tokens": 20,
                                    "output_tokens": 20,
                                    "total_tokens": 40,
                                },
                            )
                        )
                    ]
                )
            return super()._generate(messages, **kwargs)

    execute_run(tmp_path, run["id"], model=Probe(model="controlled", skip_first_lookup=True))
    final = runs.get(run["id"])
    assert final["status"] == "completed" and len(sent) == 1
    assert final["siemens_lookup"]["observation"]["remote_search_status"] == "completed"
    assert any("Antworte vollständig auf Deutsch" in p for p in prompts)
    assert final["tokens"] > 0 and final["tool_calls"] > 0
    assert route(tmp_path, final)["status"] in {"general_reference", "public_reference"}
