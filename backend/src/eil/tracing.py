"""Local, content-minimal spans derived from the durable audit log. No exporters/network."""

from decimal import Decimal

from .performance import STAGES, provider_metrics


def run_events(store, run_id):
    cursor = 0
    while batch := store.events(run_id, cursor):
        for event in batch:
            cursor = event["id"]
            yield event


def export_trace(store, run_id, *, input_usd_per_million=None, output_usd_per_million=None):
    run = store.get(run_id)
    spans = {}
    for event in run_events(store, run_id):
        data = event["data"]
        span_id = data.get("span_id")
        if event["type"] == "performance" and span_id in spans:
            if data.get("stage") in STAGES:
                timing = {k: data[k] for k in ("stage", "duration_ms", "cache_hit") if k in data}
                spans[span_id].setdefault("timings", []).append(timing)
            continue
        if not span_id or not event["type"].startswith(("model_", "tool_")):
            continue  # Older audit events remain readable; never invent timing.
        span = spans.setdefault(
            span_id,
            {
                "span_id": span_id,
                "parent_span_id": data.get("parent_span_id"),
                "agent": data.get("agent"),
                "kind": event["type"].split("_")[0],
                "name": data.get("name", "model"),
                "started_at": None,
                "finished_at": None,
                "status": "incomplete",
                "duration_ms": None,
            },
        )
        if event["type"].endswith("_started"):
            span["started_at"] = event["at"]
            if span["kind"] == "model":
                span["reserved_tokens"] = data["reserved_tokens"]
        else:
            span.update(finished_at=event["at"], duration_ms=data.get("duration_ms"))
            span["status"] = (
                "failed" if event["type"].endswith("_failed") else data.get("status", "success")
            )
            for key in ("tokens", "input_tokens", "output_tokens", "usage_known", "error_type"):
                if key in data:
                    span[key] = data[key]
            if "first_output_ms" in data:
                span["first_output_ms"] = data["first_output_ms"]
            if "provider_metrics" in data:
                span["provider_metrics"] = provider_metrics(data["provider_metrics"])
    model_spans = [s for s in spans.values() if s["kind"] == "model"]
    known = (
        bool(model_spans)
        and len(model_spans) == run["model_calls"]
        and all(s.get("usage_known", False) for s in model_spans)
    )
    input_tokens = sum(s.get("input_tokens") or 0 for s in model_spans) if known else None
    output_tokens = sum(s.get("output_tokens") or 0 for s in model_spans) if known else None
    estimate = None
    rates = (input_usd_per_million, output_usd_per_million)
    if any(r is not None for r in rates):
        if not all(
            r is not None and Decimal(str(r)).is_finite() and Decimal(str(r)) >= 0 for r in rates
        ):
            raise ValueError("Supply two finite non-negative USD token rates")
        if known:
            estimate = float(
                (
                    Decimal(input_tokens) * Decimal(str(rates[0]))
                    + Decimal(output_tokens) * Decimal(str(rates[1]))
                )
                / 1_000_000
            )
    return {
        "schema": "eil-local-trace-v1",
        "run_id": run_id,
        "status": run["status"],
        "model": run["model"],
        "model_provider": run.get("model_provider", "ollama"),
        "model_revision": run.get("model_revision") or None,
        "experiment": run.get("experiment"),
        "elapsed_seconds": run["elapsed_seconds"],
        "charged_tokens": run["tokens"],
        "model_calls": run["model_calls"],
        "tool_calls": run["tool_calls"],
        "steps": run["steps"],
        "usage_complete": known,
        "traced_model_calls": len(model_spans),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost": {
            "estimated_usd": estimate,
            "input_usd_per_million": rates[0],
            "output_usd_per_million": rates[1],
            "basis": "operator-supplied token rates; excludes hardware, energy and taxes",
        },
        "spans": list(spans.values()),
        "content_policy": "No prompts, answers, arguments, observations, credentials or reasoning in trace spans. Full evidence remains in the local audit/export.",
    }
