"""Optional official SDK transport checks. No API key or network is used."""

import json

import httpx
import pytest

pytest.importorskip("langchain_openai")
from langchain.agents.middleware.types import ModelRequest, ModelResponse
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from eil.execution import RunMiddleware, execute_run
from eil.providers import benchmark_model, cap_request
from eil.runs import BudgetExceeded, RunStore
from eil.tracing import export_trace


@pytest.fixture(autouse=True)
def offline_token_counter(monkeypatch):
    # SDK tokenization may fetch a tokenizer on first use. Keep ordinary CI
    # offline; the schema-count guard itself is tested independently below.
    monkeypatch.setattr(ChatOpenAI, "get_num_tokens_from_messages", lambda *a, **k: 100)
    monkeypatch.setattr(ChatOpenAI, "get_num_tokens", lambda *a, **k: 20)


def test_hosted_adapter_requires_credentials_and_pins_official_endpoint(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="requires"):
        benchmark_model("openai", "gpt-4o-mini")
    monkeypatch.setenv("OPENAI_API_KEY", "fake-test-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://untrusted.invalid")
    model = benchmark_model("openai", "gpt-4o-mini")
    assert model.openai_api_base == "https://api.openai.com/v1"
    assert model.max_retries == 0 and model.store is False
    with pytest.raises(ValueError, match="Unsupported"):
        benchmark_model("unreviewed", "model")


@pytest.mark.parametrize("finish_reason", ["stop", "length"])
def test_actual_sdk_request_honors_output_cap_and_accounts_usage(tmp_path, finish_reason):
    requests = []

    def transport(request):
        requests.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-offline",
                "object": "chat.completion",
                "created": 1,
                "model": "gpt-4o-mini",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "A synthetic bounded answer."},
                        "finish_reason": finish_reason,
                    }
                ],
                "usage": {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120},
            },
        )

    store = RunStore(tmp_path)
    run = store.create("Synthetic question", {"max_output_tokens": 400})
    store.claim()
    with httpx.Client(transport=httpx.MockTransport(transport)) as client:
        model = ChatOpenAI(
            model="gpt-4o-mini",
            api_key="fake-test-key",
            http_client=client,
            max_retries=0,
            store=False,
        )
        execute_run(tmp_path, run["id"], model=model)
    assert len(requests) == 1
    assert requests[0]["max_completion_tokens"] == 400
    assert requests[0]["store"] is False
    saved = store.get(run["id"])
    assert saved["tokens"] == 120
    assert saved["status"] == ("completed" if finish_reason == "stop" else "budget_exceeded")
    trace = export_trace(store, run["id"], input_usd_per_million=1, output_usd_per_million=2)
    assert trace["cost"]["estimated_usd"] == 0.00014
    assert "fake-test-key" not in json.dumps(trace)


def test_tool_schema_size_is_included_in_hosted_context_guard(monkeypatch):
    monkeypatch.setattr(ChatOpenAI, "get_num_tokens", lambda *a, **k: 8000)

    def tool(query: str) -> str:
        """Synthetic read-only tool."""
        return query

    model = ChatOpenAI(model="gpt-4o-mini", api_key="fake-test-key")
    request = ModelRequest(
        model=model,
        messages=[HumanMessage(content="Short question")],
        system_message=SystemMessage(content="Read only"),
        tools=[tool],
    )
    with pytest.raises(BudgetExceeded, match="context envelope"):
        cap_request(request, 256)


def test_hosted_failure_does_not_retry_or_emit_credentials(tmp_path):
    attempts = []

    def transport(request):
        attempts.append(1)
        return httpx.Response(
            429,
            json={
                "error": {
                    "message": "fake-test-key",
                    "type": "rate_limit_error",
                    "code": "rate_limit_exceeded",
                }
            },
        )

    store = RunStore(tmp_path)
    run = store.create("Synthetic question")
    store.claim()
    with httpx.Client(transport=httpx.MockTransport(transport)) as client:
        model = ChatOpenAI(
            model="gpt-4o-mini", api_key="fake-test-key", http_client=client, max_retries=0
        )
        execute_run(tmp_path, run["id"], model=model)
    assert len(attempts) == 1
    assert store.get(run["id"])["status"] == "failed"
    trace = export_trace(store, run["id"])
    assert trace["model_calls"] == 1 and not trace["usage_complete"]
    assert trace["spans"][0]["status"] == "failed"
    assert "fake-test-key" not in json.dumps(trace)


def test_unknown_usage_keeps_full_reservation(tmp_path):
    from langchain_core.messages import AIMessage

    store = RunStore(tmp_path)
    run = store.create("Synthetic question")
    store.claim()
    request = ModelRequest(
        model=ChatOpenAI(model="gpt-4o-mini", api_key="fake-test-key"),
        messages=[HumanMessage(content="Question")],
        tools=[],
    )
    RunMiddleware(store, run["id"]).wrap_model_call(
        request, lambda r: ModelResponse(result=[AIMessage(content="No usage supplied")])
    )
    assert store.get(run["id"])["tokens"] == 8192 + 1024
    assert not export_trace(store, run["id"])["usage_complete"]
