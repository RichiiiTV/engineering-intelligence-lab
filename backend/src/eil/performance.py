"""Content-free local timing; observations never control budgets or model policy."""

import math
import time
from contextlib import contextmanager
from contextvars import ContextVar

from langchain_core.callbacks import BaseCallbackHandler

_observer = ContextVar("eil_performance_observer", default=None)
_model_clock = ContextVar("eil_model_clock", default=None)
STAGES = frozenset(
    {
        "embedding_catalog",
        "embedding",
        "index_build",
        "index_lookup",
        "retrieval_lexical",
        "retrieval_vector",
        "retrieval_resolve",
        "retrieval_total",
    }
)
PROVIDER_FIELDS = frozenset(
    {
        "total_duration",
        "load_duration",
        "prompt_eval_count",
        "prompt_eval_duration",
        "eval_count",
        "eval_duration",
    }
)


def provider_metrics(metadata):
    """Ollama durations are nanoseconds. Missing/invalid timings stay unknown."""
    if not isinstance(metadata, dict):
        return {}
    metrics = {
        key: value
        for key, value in metadata.items()
        if key in PROVIDER_FIELDS
        and isinstance(value, int)
        and not isinstance(value, bool)
        and 0 <= value <= 2**63 - 1
    }
    for prefix, name in (("eval", "decode"), ("prompt_eval", "prefill")):
        count, duration = metrics.get(prefix + "_count"), metrics.get(prefix + "_duration")
        if count is not None and duration:
            metrics[name + "_tokens_per_second"] = round(count * 1e9 / duration, 3)
    return metrics


@contextmanager
def capture_timings(observer):
    token = _observer.set(observer)
    try:
        yield
    finally:
        _observer.reset(token)


def record_timing(stage, *, duration_ms, cache_hit=None):
    if stage not in STAGES or not isinstance(duration_ms, (float, int)):
        raise ValueError("Use a declared timing stage and finite duration")
    if not math.isfinite(duration_ms) or not 0 <= duration_ms <= 86_400_000:
        raise ValueError("Invalid timing duration")
    if cache_hit is not None and not isinstance(cache_hit, bool):
        raise ValueError("cache_hit must be boolean")
    if observer := _observer.get():
        data = {"stage": stage, "duration_ms": round(duration_ms, 3)}
        if cache_hit is not None:
            data["cache_hit"] = cache_hit
        observer(data)


@contextmanager
def timed(stage):
    started = time.perf_counter()
    try:
        yield
    finally:
        record_timing(stage, duration_ms=(time.perf_counter() - started) * 1000)


@contextmanager
def model_clock():
    clock = {"started": time.perf_counter(), "first_output_ms": None}
    token = _model_clock.set(clock)
    try:
        yield clock
    finally:
        _model_clock.reset(token)


class FirstOutputTiming(BaseCallbackHandler):
    """Observe a timestamp only; never retain tokens, tool arguments or reasoning."""

    run_inline = True

    def on_llm_new_token(self, token, *, chunk=None, **kwargs):
        clock = _model_clock.get()
        message = getattr(chunk, "message", None)
        content = getattr(message, "content", token if message is None else "")
        visible = isinstance(content, str) and bool(content.strip())
        if isinstance(content, list):
            visible = any(
                isinstance(part, dict) and part.get("type") == "text" and part.get("text")
                for part in content
            )
        if clock is not None and clock["first_output_ms"] is None and visible:
            clock["first_output_ms"] = round((time.perf_counter() - clock["started"]) * 1000, 3)
