"""Explicit, bounded local-model microbenchmark using generated fixtures only.

Default invocation prints a plan without network access. This is an operator CLI,
not an agent tool, a diagnostic-quality evaluation or a default-model selector.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import multiprocessing
import platform
import time
from pathlib import Path

import httpx

from .agent import verify_private_model
from .performance import provider_metrics as metrics
from .settings import OLLAMA_BASE_URL, ROOT

MODELS = ("qwen3.5:4b-q8_0", "qwen3.5:4b-q4_K_M")
EMBEDDING_MODEL = "embeddinggemma:300m"
MAX_SECONDS = 300
MAX_BYTES = 2 * 1024**2
MAX_OUTPUT_TOKENS = 128
FIXTURES = (
    {
        "id": "generated-en-controller-v1",
        "prompt": 'Generated test reference: the fictional conveyor XR7 uses controller SYNTH-MCU7 and a 32 KiB buffer. Based only on that reference, return exactly this JSON shape with the documented values: {"controller": "...", "buffer_kib": 0}. No other fields or text.',
        "expected": {"controller": "SYNTH-MCU7", "buffer_kib": 32},
    },
    {
        "id": "generated-de-alarm-v1",
        "prompt": 'Erzeugte Testreferenz: Bei der fiktiven Maschine XR7 bedeutet Alarm SYNTH-E17 einen belegten Sensor. Diese Information beweist keinen defekten Sensor. Antworte nur mit einem JSON-Objekt dieser Form und den dokumentierten Werten: {"alarm": "...", "defekt_bewiesen": false}. Keine weiteren Felder oder Texte.',
        "expected": {"alarm": "SYNTH-E17", "defekt_bewiesen": False},
    },
)
EMBEDDING_TEXT = "task: search result | query: Generated XR7 conveyor SYNTH-E17 sensor occupied"


class ProbeError(RuntimeError):
    """A bounded probe precondition or response contract was violated."""


def score(answer, expected):
    try:
        actual = json.loads(answer)
    except (ValueError, TypeError):
        return {"passed": False, "strict_json": False, "exact_generated_facts": False}
    exact = actual == expected and all(type(actual[k]) is type(v) for k, v in expected.items())
    return {"passed": exact, "strict_json": True, "exact_generated_facts": exact}


class Budget:
    def __init__(self):
        self.deadline = time.monotonic() + MAX_SECONDS
        self.calls = {"generation": 0, "embedding": 0, "control": 0}

    def remaining(self):
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise ProbeError("probe_deadline_exceeded")
        return remaining

    def admit(self, kind):
        self.remaining()
        if self.calls[kind] >= {"generation": 8, "embedding": 4, "control": 12}[kind]:
            raise ProbeError("probe_call_limit_exceeded")
        self.calls[kind] += 1

    def timeout(self):
        remaining = self.remaining()
        return httpx.Timeout(min(30, remaining), connect=min(5, remaining))


def bounded_chunks(response, budget):
    size = 0
    for part in response.iter_bytes():
        budget.remaining()
        size += len(part)
        if size > MAX_BYTES:
            raise ProbeError("probe_response_too_large")
        yield part


def request_json(client, budget, method, path, body=None):
    with client.stream(method, path, json=body, timeout=budget.timeout()) as response:
        response.raise_for_status()
        value = json.loads(b"".join(bounded_chunks(response, budget)))
        if not isinstance(value, dict) or value.get("error"):
            raise ProbeError("invalid_provider_response")
        return value


def unload(client, budget, model):
    budget.admit("control")
    if (
        request_json(
            client, budget, "POST", "/api/generate", {"model": model, "keep_alive": "0s"}
        ).get("done")
        is not True
    ):
        raise ProbeError("model_unload_not_confirmed")


def generate(client, budget, model, fixture, *, context_tokens=2048):
    if context_tokens not in {2048, 8192}:
        raise ValueError("Use a reviewed probe context size")
    budget.admit("generation")
    started = time.perf_counter()
    first_output = None
    answer = []
    final = None
    pending = b""

    def consume(line):
        nonlocal first_output, final
        if not line.strip():
            return
        item = json.loads(line)
        if not isinstance(item, dict) or not isinstance(item.get("message", {}), dict):
            raise ProbeError("invalid_stream_record")
        if item.get("error"):
            raise ProbeError("provider_stream_error")
        content = item.get("message", {}).get("content", "")
        if not isinstance(content, str):
            raise ProbeError("invalid_stream_content")
        if content:
            if first_output is None:
                first_output = round((time.perf_counter() - started) * 1000, 3)
            answer.append(content)
        if item.get("done") is True:
            final = item

    body = {
        "model": model,
        "messages": [{"role": "user", "content": fixture["prompt"]}],
        "stream": True,
        "think": False,
        "keep_alive": "30s",
        "options": {
            "temperature": 0,
            "num_ctx": context_tokens,
            "num_predict": MAX_OUTPUT_TOKENS,
        },
    }
    with client.stream("POST", "/api/chat", json=body, timeout=budget.timeout()) as response:
        response.raise_for_status()
        for part in bounded_chunks(response, budget):
            pending += part
            while b"\n" in pending:
                line, pending = pending.split(b"\n", 1)
                consume(line)
        if pending.strip():
            consume(pending)
    if final is None:
        raise ProbeError("missing_stream_completion")
    if type(final.get("eval_count")) is int and final["eval_count"] > MAX_OUTPUT_TOKENS:
        raise ProbeError("provider_exceeded_output_cap")
    answer = "".join(answer)
    quality = score(answer, fixture["expected"])
    truncated = final.get("done_reason") == "length"
    quality["passed"] = quality["passed"] and not truncated
    return {
        "status": "completed",
        "fixture": fixture["id"],
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
        "time_to_first_output_ms": first_output,
        "provider_metrics": metrics(final),
        "quality": quality,
        "output_truncated": truncated,
        "answer_sha256": hashlib.sha256(answer.encode()).hexdigest(),
    }


def embedding(client, budget, keep_alive):
    budget.admit("embedding")
    started = time.perf_counter()
    data = request_json(
        client,
        budget,
        "POST",
        "/api/embed",
        {
            "model": EMBEDDING_MODEL,
            "input": [EMBEDDING_TEXT],
            "truncate": False,
            "keep_alive": keep_alive,
        },
    )
    vectors = data.get("embeddings")
    if (
        not isinstance(vectors, list)
        or len(vectors) != 1
        or not isinstance(vectors[0], list)
        or not 32 <= len(vectors[0]) <= 2048
        or any(type(v) not in {int, float} or not math.isfinite(v) for v in vectors[0])
    ):
        raise ProbeError("invalid_embedding_vectors")
    return {
        "status": "completed",
        "keep_alive": keep_alive,
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
        "provider_metrics": metrics(data),
        "dimensions": len(vectors[0]),
        "vector_sha256": hashlib.sha256(
            json.dumps(vectors, separators=(",", ":")).encode()
        ).hexdigest(),
    }


def plan():
    return {
        "schema": "eil-local-performance-probe-v1",
        "mode": "plan-only",
        "models": list(MODELS),
        "embedding_model": EMBEDDING_MODEL,
        "fixture_ids": [f["id"] for f in FIXTURES],
        "max_generation_calls": 8,
        "max_embedding_calls": 4,
        "max_output_tokens_per_generation": MAX_OUTPUT_TOKENS,
        "context_tokens": 2048,
        "max_wall_seconds": MAX_SECONDS,
        "measurement": "Generated-fact microbenchmark, separate from engineering diagnostic quality; never promotes a default model.",
    }


def checked_output(output):
    output = Path(output).resolve()
    reports = (ROOT / "reports").resolve()
    if output == reports or not output.is_relative_to(reports):
        raise ValueError("Probe output must be a fresh child directory under reports/")
    if output.exists():
        raise FileExistsError("Probe output already exists; prior artifacts are immutable")
    return output


def run_probe(output):
    """Worker implementation; the CLI additionally enforces a hard process deadline."""
    output = checked_output(output)
    output.mkdir(parents=True, exist_ok=False)
    card = plan() | {"mode": "live", "generation": [], "embedding": [], "errors": []}
    budget = Budget()
    started = time.perf_counter()
    verified = {}
    try:
        # Validate every selected identity before transmitting any fixed prompt.
        for model in (*MODELS, EMBEDDING_MODEL):
            verified[model] = verify_private_model(OLLAMA_BASE_URL, model)
            budget.remaining()
        card["model_identities"] = {
            name: {
                "digest": entry["digest"],
                "quantization": entry["details"].get("quantization_level"),
            }
            for name, entry in verified.items()
        }
        with httpx.Client(
            base_url=OLLAMA_BASE_URL, trust_env=False, follow_redirects=False
        ) as client:
            card["ollama_version"] = request_json(client, budget, "GET", "/api/version")["version"]
            if request_json(client, budget, "GET", "/api/ps").get("models"):
                raise ProbeError("loaded_models_require_an_idle_benchmark_window")
            for model in MODELS:
                try:
                    for fixture in FIXTURES:
                        unload(client, budget, model)
                        for temperature in ("cold", "warm"):
                            row = generate(client, budget, model, fixture)
                            card["generation"].append(row | {"model": model, "load": temperature})
                finally:
                    if budget.deadline > time.monotonic():
                        unload(client, budget, model)
            try:
                for policy in ("0s", "30s"):
                    unload(client, budget, EMBEDDING_MODEL)
                    for repetition in (1, 2):
                        card["embedding"].append(
                            embedding(client, budget, policy) | {"repetition": repetition}
                        )
            finally:
                if budget.deadline > time.monotonic():
                    unload(client, budget, EMBEDDING_MODEL)
    except (httpx.HTTPError, ValueError, KeyError, TypeError, RuntimeError) as exc:
        card["errors"].append(
            {
                "type": type(exc).__name__,
                "code": str(exc) if isinstance(exc, ProbeError) else "probe_failed",
            }
        )
    card["elapsed_seconds"] = round(time.perf_counter() - started, 3)
    card["calls"] = budget.calls
    card["system"] = {"platform": platform.system(), "python": platform.python_version()}
    card["completed"] = (
        not card["errors"] and len(card["generation"]) == 8 and len(card["embedding"]) == 4
    )
    card["embedding_vectors_identical"] = (
        len({r["vector_sha256"] for r in card["embedding"]}) == 1
        if len(card["embedding"]) == 4
        else None
    )
    (output / "scorecard.json").write_text(json.dumps(card, indent=2), encoding="utf-8")
    return card


def contention_plan():
    return plan() | {
        "schema": "eil-local-contention-probe-v1",
        "models": [MODELS[0]],
        "fixture_ids": [FIXTURES[0]["id"]],
        "max_generation_calls": 4,
        "context_tokens": 8192,
        "embedding_keep_alive_policies": ["0s", "30s"],
        "measurement": "Generated-fixture embedding/generation contention; /api/ps VRAM snapshots exclude other applications and are not peak GPU telemetry.",
    }


def residency(client, budget):
    data = request_json(client, budget, "GET", "/api/ps")
    models = data.get("models")
    if not isinstance(models, list):
        raise ProbeError("invalid_model_residency")
    result = []
    for row in models:
        if not isinstance(row, dict) or row.get("name") not in {*MODELS, EMBEDDING_MODEL}:
            raise ProbeError("unexpected_loaded_model_requires_an_idle_window")
        values = {key: row.get(key) for key in ("size", "size_vram")}
        if any(type(value) is not int or not 0 <= value <= 2**63 - 1 for value in values.values()):
            raise ProbeError("invalid_model_residency")
        result.append({"model": row["name"], **values})
    return {"models": result, "sum_model_vram_bytes": sum(r["size_vram"] for r in result)}


def run_contention(output):
    output = checked_output(output)
    output.mkdir(parents=True, exist_ok=False)
    card = contention_plan() | {"mode": "live", "policies": [], "errors": []}
    budget = Budget()
    started = time.perf_counter()
    try:
        card["model_identities"] = {
            model: verify_private_model(OLLAMA_BASE_URL, model)["digest"]
            for model in (MODELS[0], EMBEDDING_MODEL)
        }
        with httpx.Client(
            base_url=OLLAMA_BASE_URL, trust_env=False, follow_redirects=False
        ) as client:
            card["ollama_version"] = request_json(client, budget, "GET", "/api/version")["version"]
            initial = residency(client, budget)  # Never unload an unrelated model.
            for row in initial["models"]:
                unload(client, budget, row["model"])
            try:
                for policy in ("0s", "30s"):
                    unload(client, budget, MODELS[0])
                    unload(client, budget, EMBEDDING_MODEL)
                    warmup = generate(client, budget, MODELS[0], FIXTURES[0], context_tokens=8192)
                    first = embedding(client, budget, policy)
                    before = residency(client, budget)
                    measured = generate(client, budget, MODELS[0], FIXTURES[0], context_tokens=8192)
                    after = residency(client, budget)
                    second = embedding(client, budget, policy)
                    card["policies"].append(
                        {
                            "keep_alive": policy,
                            "warmup": warmup,
                            "first_embedding": first,
                            "before_generation": before,
                            "measured_generation": measured,
                            "after_generation": after,
                            "second_embedding": second,
                            "after_second_embedding": residency(client, budget),
                        }
                    )
            finally:
                if budget.deadline > time.monotonic():
                    for model in (MODELS[0], EMBEDDING_MODEL):
                        unload(client, budget, model)
    except (httpx.HTTPError, ValueError, KeyError, TypeError, RuntimeError) as exc:
        card["errors"].append(
            {
                "type": type(exc).__name__,
                "code": str(exc) if isinstance(exc, ProbeError) else "probe_failed",
            }
        )
    card["elapsed_seconds"] = round(time.perf_counter() - started, 3)
    card["calls"] = budget.calls
    card["completed"] = not card["errors"] and len(card["policies"]) == 2
    vectors = [
        row[key]["vector_sha256"]
        for row in card["policies"]
        for key in ("first_embedding", "second_embedding")
    ]
    card["embedding_vectors_identical"] = len(set(vectors)) == 1 if len(vectors) == 4 else None
    (output / "scorecard.json").write_text(json.dumps(card, indent=2), encoding="utf-8")
    return card


def _probe_child(output, pipe, contention=False):
    try:
        pipe.send(run_contention(output) if contention else run_probe(output))
    except Exception as exc:
        pipe.send(
            (contention_plan() if contention else plan())
            | {
                "mode": "live",
                "completed": False,
                "errors": [{"type": type(exc).__name__, "code": "probe_worker_failed"}],
            }
        )
    finally:
        pipe.close()


def supervised_probe(output, *, contention=False):
    """Kill only this probe worker after 300s; no automatic retry of unknown outcomes."""
    output = checked_output(output)
    context = multiprocessing.get_context("spawn")
    receive, send = context.Pipe(duplex=False)
    arguments = (output, send, True) if contention else (output, send)
    process = context.Process(target=_probe_child, args=arguments, daemon=True)
    process.start()
    send.close()
    card = None
    try:
        if receive.poll(MAX_SECONDS):
            try:
                card = receive.recv()
            except EOFError:
                pass
    finally:
        receive.close()
        if process.is_alive():
            process.terminate()
        process.join(timeout=2)
        if process.is_alive():
            process.kill()
            process.join(timeout=2)
        process.close()
    if card is None:
        card = (contention_plan() if contention else plan()) | {
            "mode": "live",
            "completed": False,
            "errors": [{"type": "ProbeError", "code": "probe_worker_deadline_or_exit"}],
            "outcome": "Unknown partial outcomes; do not retry automatically. Warm models expire within 30s.",
        }
        output.mkdir(parents=True, exist_ok=True)
        # Preserve any partial scorecard that the worker finished before termination.
        with (output / "supervisor-error.json").open("x", encoding="utf-8") as stream:
            json.dump(card, stream, indent=2)
    return card


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Run the fixed bounded local probe")
    parser.add_argument(
        "--contention",
        action="store_true",
        help="Compare fixed embedding keep-alive policies at the workbench context size",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
    )
    args = parser.parse_args(argv)
    output = args.output or ROOT / "reports/performance-followup-20261101" / (
        "contention-v1" if args.contention else "probe"
    )
    card = (
        supervised_probe(output, contention=args.contention)
        if args.live
        else contention_plan()
        if args.contention
        else plan()
    )
    print(json.dumps(card, indent=2))
    return 0 if not args.live or card["completed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
