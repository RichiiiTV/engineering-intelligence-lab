import json
from types import SimpleNamespace

import pytest
from langchain.agents.middleware.types import ModelRequest, ModelResponse
from langchain_core.messages import AIMessage, HumanMessage
from langchain_ollama import ChatOllama

from eil.execution import RunMiddleware
from eil.performance import (
    FirstOutputTiming,
    capture_timings,
    model_clock,
    provider_metrics,
    record_timing,
    timed,
)
from eil.runs import RunStore
from eil.tracing import export_trace


def test_provider_rates_require_actual_counts_and_nonzero_nanoseconds():
    metrics = provider_metrics(
        {
            "eval_count": 30,
            "eval_duration": 2_000_000_000,
            "prompt_eval_count": 300,
            "prompt_eval_duration": 1_000_000_000,
            "load_duration": 5_000_000_000,
            "total_duration": 9_000_000_000,
            "prompt": "PRIVATE SENTINEL",
        }
    )
    assert metrics["decode_tokens_per_second"] == 15
    assert metrics["prefill_tokens_per_second"] == 300
    assert "prompt" not in metrics
    assert provider_metrics({"eval_count": 4, "eval_duration": 0}) == {
        "eval_count": 4,
        "eval_duration": 0,
    }
    assert provider_metrics({"eval_count": True, "eval_duration": -1}) == {}
    assert provider_metrics(None) == {}


def test_timing_observers_are_nested_scoped_and_content_free():
    outer, inner = [], []
    with capture_timings(outer.append):
        with timed("index_build"):
            pass
        with capture_timings(inner.append):
            record_timing("index_lookup", duration_ms=1.25, cache_hit=True)
        record_timing("retrieval_total", duration_ms=2)
    record_timing("retrieval_total", duration_ms=4)
    assert [row["stage"] for row in outer] == ["index_build", "retrieval_total"]
    assert inner == [{"stage": "index_lookup", "duration_ms": 1.25, "cache_hit": True}]
    with pytest.raises(ValueError):
        record_timing("PRIVATE SENTINEL", duration_ms=1)
    with pytest.raises(ValueError):
        record_timing("embedding", duration_ms=float("inf"))


def test_first_output_ignores_reasoning_and_keeps_no_text():
    callback = FirstOutputTiming()
    with model_clock() as clock:
        callback.on_llm_new_token("", chunk=SimpleNamespace(message=SimpleNamespace(content="")))
        callback.on_llm_new_token(
            "PRIVATE REASONING",
            chunk=SimpleNamespace(message=SimpleNamespace(content=[{"type": "reasoning"}])),
        )
        assert clock["first_output_ms"] is None
        callback.on_llm_new_token("Generated visible text")
        first = clock["first_output_ms"]
        callback.on_llm_new_token("another text")
        assert first is not None and first >= 0 and clock["first_output_ms"] == first
    assert "REASONING" not in json.dumps(clock) and "visible" not in json.dumps(clock)


def test_model_metadata_and_first_output_export_without_changing_accounting(tmp_path):
    store = RunStore(tmp_path)
    run = store.create("PRIVATE QUESTION")
    store.claim()
    request = ModelRequest(
        model=ChatOllama(model="offline"),
        messages=[HumanMessage(content="PRIVATE QUESTION")],
        tools=[],
    )

    def handler(request):
        FirstOutputTiming().on_llm_new_token("PRIVATE ANSWER")
        return ModelResponse(
            result=[
                AIMessage(
                    content="PRIVATE ANSWER",
                    usage_metadata={"input_tokens": 100, "output_tokens": 20, "total_tokens": 120},
                    response_metadata={
                        "eval_count": 20,
                        "eval_duration": 1_000_000_000,
                        "prompt_eval_count": 100,
                        "prompt_eval_duration": 500_000_000,
                        "reasoning": "PRIVATE REASONING",
                    },
                )
            ]
        )

    RunMiddleware(store, run["id"]).wrap_model_call(request, handler)
    trace = export_trace(store, run["id"])
    span = trace["spans"][0]
    assert span["provider_metrics"]["decode_tokens_per_second"] == 20
    assert span["first_output_ms"] is not None
    assert store.get(run["id"])["tokens"] == 120
    assert store.get(run["id"])["model_calls"] == 1
    assert "PRIVATE" not in json.dumps(trace)


def test_failed_model_does_not_invent_provider_timing(tmp_path):
    store = RunStore(tmp_path)
    run = store.create("Generated question")
    store.claim()
    request = ModelRequest(model=ChatOllama(model="offline"), messages=[], tools=[])

    def fail(request):
        raise RuntimeError("Generated failure")

    with pytest.raises(RuntimeError):
        RunMiddleware(store, run["id"]).wrap_model_call(request, fail)
    span = export_trace(store, run["id"])["spans"][0]
    assert span["status"] == "failed" and "provider_metrics" not in span
    assert span["first_output_ms"] is None
