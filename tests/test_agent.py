"""Exercise the real Deep Agents graph without a model server or network."""

import json
from unittest.mock import Mock

import httpx
import pytest
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_ollama import ChatOllama
from ollama import ResponseError
from pydantic import Field

from eil import agent


class OfflineOllama(ChatOllama):
    """Use ChatOllama's real tool binding, with scripted local responses."""

    responses: list[AIMessage] = Field(default_factory=list)
    bound_names: list[set[str]] = Field(default_factory=list)

    def bind_tools(self, tools, **kwargs):
        self.bound_names.append({tool.name for tool in tools})
        return super().bind_tools(tools, **kwargs)

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        assert self.responses, "Unexpected extra model call"
        return ChatResult(generations=[ChatGeneration(message=self.responses.pop(0))])


@pytest.fixture(autouse=True)
def forbid_network(monkeypatch):
    def fail(*args, **kwargs):
        pytest.fail("Offline agent tests must never send HTTP requests")

    monkeypatch.setattr(httpx.Client, "send", fail)
    monkeypatch.setattr(httpx.AsyncClient, "send", fail)


def make_model(*responses):
    return OfflineOllama(model=agent.OLLAMA_MODEL, responses=list(responses))


def call(name, args=None, call_id="call-1"):
    return AIMessage(
        content="",
        tool_calls=[{"name": name, "args": args or {}, "id": call_id, "type": "tool_call"}],
    )


def invoke(model):
    return agent.build_agent(model=model).invoke(
        {"messages": [{"role": "user", "content": "Compare the stations using evidence."}]},
        config={"configurable": {"thread_id": "offline-test"}, "recursion_limit": 12},
    )


def test_real_graph_executes_analytics_and_binds_only_reviewed_tools():
    model = make_model(
        call("compare_station_performance"),
        call("inspect_station", {"station_id": "S03", "period": "incident"}, "call-2"),
        AIMessage(content="S03 changed most; concurrent lighting changes are a hypothesis."),
    )
    result = invoke(model)
    observations = [json.loads(m.content) for m in result["messages"] if isinstance(m, ToolMessage)]
    assert observations[0][0]["station_id"] == "S03"
    assert observations[0][0]["delta_percentage_points"] > 8
    assert observations[1]["station_id"] == "S03"
    assert observations[1]["source_rows"]
    assert "hypothesis" in result["messages"][-1].content
    expected = {"compare_station_performance", "inspect_station", "ls", "read_file", "glob", "grep"}
    assert model.bound_names and all(names == expected for names in model.bound_names)
    assert not model.responses


@pytest.mark.parametrize("name", ["execute", "eval", "write_file", "edit_file", "delete", "task"])
def test_unregistered_execution_write_and_delegation_tools_are_rejected(name):
    model = make_model(call(name), AIMessage(content="Tool unavailable."))
    result = invoke(model)
    observation = next(m for m in result["messages"] if isinstance(m, ToolMessage))
    assert observation.status == "error"
    assert "not a valid tool" in observation.content


@pytest.mark.parametrize(
    "path, expected_error",
    [
        ("/data/ground_truth.json", "not found"),
        (str(agent.__file__), "windows absolute paths are not supported"),
        ("C:/Windows/win.ini", "windows absolute paths are not supported"),
    ],
)
def test_virtual_reads_cannot_open_host_or_ground_truth_files(path, expected_error):
    model = make_model(call("read_file", {"file_path": path}), AIMessage(content="No file."))
    result = invoke(model)
    observation = next(m for m in result["messages"] if isinstance(m, ToolMessage))
    assert observation.status == "error"
    assert expected_error in observation.content.lower()


def test_invalid_station_is_a_constrained_tool_observation():
    model = make_model(
        call("inspect_station", {"station_id": "../../secrets", "period": "baseline"}),
        AIMessage(content="Invalid station."),
    )
    result = invoke(model)
    observation = next(m for m in result["messages"] if isinstance(m, ToolMessage))
    assert "Unknown station" in json.loads(observation.content)["error"]


def test_ollama_adapter_validates_model_and_sets_http_timeouts(monkeypatch):
    constructor = Mock()
    monkeypatch.setattr("langchain_ollama.ChatOllama", constructor)
    agent._build_model()
    kwargs = constructor.call_args.kwargs
    assert kwargs["model"] == agent.OLLAMA_MODEL
    assert kwargs["base_url"] == agent.OLLAMA_BASE_URL
    assert kwargs["validate_model_on_init"] is True
    assert kwargs["client_kwargs"]["timeout"].connect == 5
    assert kwargs["client_kwargs"]["timeout"].read == 60
    assert kwargs["client_kwargs"]["trust_env"] is False


def test_real_ollama_constructor_validates_stubbed_model_listing(monkeypatch):
    monkeypatch.setattr(
        "ollama.Client.list", lambda self: {"models": [{"model": agent.OLLAMA_MODEL}]}
    )
    model = agent._build_model()
    assert isinstance(model, ChatOllama)
    assert model.model == agent.OLLAMA_MODEL
    assert model._client._client.timeout.connect == 5
    assert model._client._client.timeout.read == 60


def test_real_ollama_constructor_reports_missing_model(monkeypatch):
    monkeypatch.setattr("ollama.Client.list", lambda self: {"models": []})
    with pytest.raises(agent.ModelUnavailableError, match="install/select"):
        agent._build_model()


@pytest.mark.parametrize(
    "error",
    [
        ValueError("Model not found"),
        ConnectionError("Connection refused"),
        httpx.ConnectError("Connection failed"),
        httpx.ReadTimeout("Slow validation"),
        ResponseError("Server error", 500),
    ],
)
def test_model_initialization_errors_are_actionable(monkeypatch, error):
    monkeypatch.setattr("langchain_ollama.ChatOllama", Mock(side_effect=error))
    with pytest.raises(agent.ModelUnavailableError, match="Ollama"):
        agent._build_model()


@pytest.mark.parametrize(
    "error, message",
    [
        (httpx.ConnectError("offline"), "connection failed"),
        (ConnectionError("offline"), "connection failed"),
        (httpx.ReadTimeout("slow"), "inference timed out"),
        (ResponseError("Model missing", 404), "HTTP 404"),
        (ResponseError("Tools unsupported", 400), "supports tool calling"),
    ],
)
def test_inference_errors_are_normalized(monkeypatch, error, message):
    graph = Mock()
    graph.invoke.side_effect = error
    monkeypatch.setattr(agent, "build_agent", lambda: graph)
    with pytest.raises(agent.ModelUnavailableError, match=message):
        agent.run_agent("Compare the stations")


def test_run_agent_uses_real_graph_and_returns_answer(monkeypatch):
    monkeypatch.setattr(
        agent, "_build_model", lambda: make_model(AIMessage(content="Offline graph completed."))
    )
    assert agent.run_agent("Compare the stations")["answer"] == "Offline graph completed."


@pytest.mark.parametrize("question", ["", " \t\n", "x" * 4001])
def test_invalid_questions_fail_before_building_model(monkeypatch, question):
    build = Mock()
    monkeypatch.setattr(agent, "build_agent", build)
    with pytest.raises(ValueError, match="1-4000"):
        agent.run_agent(question)
    build.assert_not_called()
