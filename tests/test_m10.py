from eil.code_sources import inspect
from eil.knowledge_benchmark import evaluate


def test_generated_knowledge_suite_has_reviewed_hashes_and_separate_gates(tmp_path):
    result = evaluate(tmp_path)
    assert len(result["results"]) == 50
    assert result["passed"], result["results"]
    assert set(result["metrics"]) == {
        "retrieval",
        "unknown",
        "applicability",
        "contract",
        "static",
        "isolation",
        "snapshot",
    }


def test_knowledge_generator_preserves_reviewed_manifest_and_sources_on_every_os(tmp_path):
    import hashlib
    import json
    import shutil
    import subprocess
    import sys

    from eil.knowledge_benchmark import MANIFEST_SHA256, PACK

    generator = tmp_path / "generate.py"
    shutil.copyfile(PACK / "generate.py", generator)
    subprocess.run([sys.executable, str(generator)], check=True, capture_output=True)
    raw = (tmp_path / "manifest.json").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == MANIFEST_SHA256
    for document in json.loads(raw)["documents"]:
        source = (tmp_path / document["filename"]).read_bytes()
        assert hashlib.sha256(source).hexdigest() == document["sha256"]


def test_changed_knowledge_baseline_cannot_be_scored_as_original(tmp_path, monkeypatch):
    import shutil

    import pytest

    from eil import knowledge_benchmark

    pack = tmp_path / "pack"
    shutil.copytree(knowledge_benchmark.PACK, pack)
    monkeypatch.setattr(knowledge_benchmark, "PACK", pack)
    (pack / "manifest.json").write_bytes((pack / "manifest.json").read_bytes() + b" ")
    with pytest.raises(ValueError, match="manifest changed"):
        knowledge_benchmark.evaluate(tmp_path / "state")


def test_static_complexity_limits_are_explicit():
    assert "skipped" in inspect("a.py", "x" * 32001)["scope"]
    assert "complexity limit" in inspect("a.py", "(" * 100 + "1" + ")" * 100)["scope"]
    assert "complexity limit" in inspect("a.py", "x=1\n" * 1000)["scope"]


def test_private_graph_repairs_citations_once_inside_normal_budgets(tmp_path, monkeypatch):
    import json

    from langchain_core.messages import AIMessage, ToolMessage
    from langchain_core.outputs import ChatGeneration, ChatResult
    from langchain_ollama import ChatOllama

    from eil.execution import execute_run
    from eil.machines import MachineStore
    from eil.runs import RunStore
    from tests.test_m8 import source, vector

    monkeypatch.setattr("eil.knowledge.embed", vector)
    machines = MachineStore(tmp_path)
    m = machines.create("a", "A")
    source(machines.documents(m["id"], "a"))

    class Probe(ChatOllama):
        def _generate(self, messages, stop=None, run_manager=None, **kwargs):
            names = {t["function"]["name"] for t in kwargs.get("tools", [])}
            assert (
                "read_machine_knowledge" in names
                and not {"execute", "compare_stations", "read_siemens_reference"} & names
            )
            result = next(
                (
                    m
                    for m in messages
                    if isinstance(m, ToolMessage) and m.name == "read_machine_knowledge"
                ),
                None,
            )
            if result is None:
                content = ""
                calls = [
                    {
                        "name": "read_machine_knowledge",
                        "args": {},
                        "id": "lookup",
                        "type": "tool_call",
                    }
                ]
            else:
                hit = json.loads(result.text)["hits"][0]
                content = "The source contains a sensor condition." + (
                    " [" + hit["citation_id"] + "]"
                    if "exact IDs in square brackets" in messages[-1].text
                    else ""
                )
                calls = []
            return ChatResult(
                generations=[
                    ChatGeneration(
                        message=AIMessage(
                            content=content,
                            tool_calls=calls,
                            usage_metadata={
                                "input_tokens": 50,
                                "output_tokens": 50,
                                "total_tokens": 100,
                            },
                        )
                    )
                ]
            )

    runs = RunStore(tmp_path)
    run = runs.create("sensor", machine_id=m["id"], owner_id="a")
    runs.claim()
    execute_run(tmp_path, run["id"], model=Probe(model="controlled"))
    final = runs.get(run["id"])
    assert final["status"] == "completed" and final["model_calls"] == 3 and final["tokens"] == 300
    assert final["result"]["answer_contract"]["outcome"] == "references_checked"


def test_private_model_preflight_rejects_cloud_alias_without_sending_prompt(monkeypatch):
    import httpx
    import pytest

    from eil.agent import ModelUnavailableError, verify_private_model

    original = httpx.Client
    calls = []
    entry = {
        "name": "demo:local",
        "details": {"format": "gguf"},
        "size": 2000000,
        "digest": "a" * 64,
    }

    def handler(request):
        calls.append(request.url.path)
        assert request.method == "GET" and not request.content
        return httpx.Response(200, json={"models": [entry]})

    monkeypatch.setattr(
        "eil.agent.httpx.Client",
        lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs),
    )
    verify_private_model("http://localhost:11434", "demo:local")
    entry["remote_host"] = "https://ollama.com"
    with pytest.raises(ModelUnavailableError):
        verify_private_model("http://localhost:11434", "demo:local")
    with pytest.raises(ModelUnavailableError):
        verify_private_model("http://remote.invalid", "demo:local")
    assert calls == ["/api/tags", "/api/tags"]
