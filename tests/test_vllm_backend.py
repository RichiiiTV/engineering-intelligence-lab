"""Exercise the real compatible SDK/graph with a bounded local mock transport."""

import asyncio
import json
import struct

import httpx
import pytest

pytest.importorskip("langchain_openai")
from langchain.agents.middleware.types import ModelRequest
from langchain_core.messages import HumanMessage

from eil import embeddings, settings, vllm_backend
from eil.agent import ModelUnavailableError
from eil.execution import execute_run
from eil.providers import cap_request
from eil.runs import BudgetExceeded, RunStore

BASE = "http://127.0.0.1:8002/v1"
MODEL = "eil-generation"
REVISION = "a" * 64


@pytest.fixture
def transport(monkeypatch):
    monkeypatch.setenv("EIL_VLLM_API_KEY", "generated-test-runtime-key")
    requests = []
    state = {
        "model_exists": True,
        "count": 100,
        "redirect": False,
        "oversized": False,
        "embedding": [[1.0] * 32],
        "tool": False,
    }

    def handler(request):
        requests.append(request)
        assert request.url.host == "127.0.0.1", "Private data left loopback"
        if request.url.path == "/v1/models":
            if state["oversized"]:
                return httpx.Response(200, content=b"x" * (vllm_backend.MAX_BYTES + 1))
            return httpx.Response(
                200, json={"data": [{"id": MODEL}] if state["model_exists"] else []}
            )
        if request.url.path == "/tokenize":
            return httpx.Response(200, json={"count": state["count"], "max_model_len": 8192})
        if request.url.path == "/v1/embeddings":
            return httpx.Response(
                200,
                json={
                    "data": [{"index": n, "embedding": v} for n, v in enumerate(state["embedding"])]
                },
            )
        assert request.url.path == "/v1/chat/completions"
        if state["redirect"]:
            return httpx.Response(307, headers={"Location": "https://external.invalid/collect"})
        body = json.loads(request.content)
        calls = None
        if state["tool"] and not any(m["role"] == "tool" for m in body["messages"]):
            calls = [
                {
                    "id": "generated-call",
                    "type": "function",
                    "function": {"name": "read_generated_fact", "arguments": "{}"},
                }
            ]
        return httpx.Response(
            200,
            json={
                "id": "generated-completion",
                "object": "chat.completion",
                "created": 1,
                "model": MODEL,
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": None if calls else "Generated observed fact.",
                            **({"tool_calls": calls} if calls else {}),
                        },
                        "finish_reason": "tool_calls" if calls else "stop",
                    }
                ],
                "usage": {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120},
            },
        )

    monkeypatch.setattr(httpx, "HTTPTransport", lambda **kwargs: httpx.MockTransport(handler))
    monkeypatch.setattr(httpx, "AsyncHTTPTransport", lambda **kwargs: httpx.MockTransport(handler))
    return requests, state


@pytest.mark.parametrize(
    "base,revision",
    [
        ("https://external.invalid/v1", REVISION),
        ("http://127.0.0.1:8002/v1?token=bad", REVISION),
        ("http://user:secret@127.0.0.1:8002/v1", REVISION),
        (BASE, ""),
    ],
)
def test_private_vllm_requires_loopback_and_operator_attestation_before_any_http(
    transport, base, revision
):
    requests, state = transport
    with pytest.raises(ModelUnavailableError):
        vllm_backend.build_model(base, MODEL, revision)
    assert requests == []


def test_no_default_vllm_credential_is_created(transport, monkeypatch):
    requests, _ = transport
    monkeypatch.delenv("EIL_VLLM_API_KEY", raising=False)
    with pytest.raises(ModelUnavailableError, match="API key"):
        vllm_backend.build_model(BASE, MODEL, REVISION)
    assert requests == []


def test_bounded_transport_rejects_oversized_and_compressed_responses():
    oversized = httpx.MockTransport(
        lambda request: httpx.Response(200, content=b"x" * (vllm_backend.MAX_BYTES + 1))
    )
    with httpx.Client(transport=vllm_backend.BoundedTransport(oversized)) as http:
        with pytest.raises(ModelUnavailableError, match="byte limit"):
            http.get(BASE + "/models")
    compressed = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            headers={"Content-Encoding": "gzip"},
            stream=httpx.ByteStream(b"unread encoded content"),
        )
    )
    with httpx.Client(transport=vllm_backend.BoundedTransport(compressed)) as http:
        with pytest.raises(ModelUnavailableError, match="Compressed"):
            http.get(BASE + "/models")


def test_missing_alias_and_oversized_catalog_never_receive_prompt(transport):
    requests, state = transport
    for option in ("model_exists", "oversized"):
        state["model_exists"], state["oversized"] = False, False
        if option == "oversized":
            state["oversized"] = True
        with pytest.raises(ModelUnavailableError):
            vllm_backend.build_model(BASE, MODEL, REVISION)
    assert all(r.method == "GET" for r in requests)


def test_sdk_output_cap_local_tokenizer_and_native_schema(transport):
    requests, state = transport
    model = vllm_backend.build_model(BASE, MODEL, REVISION)
    request = ModelRequest(
        model=model, messages=[HumanMessage(content="Generated private text")], tools=[]
    )
    limited = cap_request(request, 73)
    limited.model.bind(format={"type": "object", "properties": {}}).invoke(request.messages)
    body = json.loads(next(r for r in requests if r.url.path.endswith("chat/completions")).content)
    assert body.get("max_completion_tokens", body.get("max_tokens")) == 73
    assert body["response_format"]["type"] == "json_schema"
    assert model.max_retries == 0 and model.http_client.follow_redirects is False
    assert model.http_async_client.follow_redirects is False
    assert any(r.url.path == "/tokenize" for r in requests)
    requests.clear()
    state["count"] = 8190
    with pytest.raises(BudgetExceeded):
        limited.model.invoke(request.messages)
    assert not any(r.url.path.endswith("chat/completions") for r in requests)


def test_generation_redirect_does_not_forward_private_prompt(transport):
    requests, state = transport
    model = vllm_backend.build_model(BASE, MODEL, REVISION)
    state["redirect"] = True
    with pytest.raises(Exception):
        model.invoke("Generated private sentinel")
    assert sum(r.url.path.endswith("chat/completions") for r in requests) == 1
    assert all(r.url.host == "127.0.0.1" for r in requests)


def test_async_sdk_uses_same_local_preflight_and_bounded_transport(transport):
    requests, state = transport
    model = vllm_backend.build_model(BASE, MODEL, REVISION)
    answer = asyncio.run(model.ainvoke("Generated async test"))
    assert answer.text == "Generated observed fact."
    assert any(r.url.path == "/tokenize" for r in requests)
    assert all(r.url.host == "127.0.0.1" for r in requests)


def test_native_vision_rejects_external_images_before_text_bearing_http(transport):
    requests, state = transport
    model = vllm_backend.build_model(BASE, MODEL, REVISION, vision=True)
    requests.clear()
    with pytest.raises(ModelUnavailableError, match="normalized local images"):
        model.invoke(
            [
                HumanMessage(
                    content=[
                        {
                            "type": "image_url",
                            "image_url": {"url": "https://external.invalid/image.jpg"},
                        }
                    ]
                )
            ]
        )
    assert requests == []


def test_model_messages_cannot_smuggle_unreviewed_media_fetches(transport):
    requests, state = transport
    model = vllm_backend.build_model(BASE, MODEL, REVISION, vision=True)
    requests.clear()
    with pytest.raises(ModelUnavailableError, match="Unreviewed vLLM media"):
        model.invoke(
            [
                HumanMessage(
                    content=[
                        {
                            "type": "video_url",
                            "video_url": {"url": "https://external.invalid/video.mp4"},
                        }
                    ]
                )
            ]
        )
    assert requests == []


def test_vllm_vectors_are_normalized_namespaced_and_reject_invalid_data(transport):
    requests, state = transport
    config = {"provider": "vllm", "base_url": BASE, "model_name": MODEL, "revision": REVISION}
    with embeddings.use_embedding_config(config):
        key, vectors = embeddings.embed(["Generated document"])
        assert key == "vllm:" + MODEL + "@sha256:" + REVISION
        assert abs(sum(v * v for v in struct.unpack("<32f", vectors[0])) - 1) < 1e-6
        state["embedding"] = [[0.0] * 32]
        with pytest.raises(embeddings.EmbeddingUnavailable):
            embeddings.embed(["Generated document"])
    assert all(r.url.host == "127.0.0.1" for r in requests)


def test_run_freezes_provider_revision_and_embedding_settings_without_credentials(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(settings, "MODEL_PROVIDER", "vllm")
    monkeypatch.setattr(settings, "VLLM_BASE_URL", BASE)
    monkeypatch.setattr(settings, "VLLM_MODEL", MODEL)
    monkeypatch.setattr(settings, "VLLM_REVISION", REVISION)
    monkeypatch.setenv("EIL_VLLM_API_KEY", "generated-key-not-to-be-persisted")
    store = RunStore(tmp_path)
    row = store.create("Generated question")
    monkeypatch.setattr(settings, "VLLM_REVISION", "b" * 64)
    saved = store.get(row["id"])
    assert saved["model_provider"] == "vllm" and saved["model_revision"] == REVISION
    assert "generated-key" not in json.dumps(saved)


def test_selected_vllm_backend_runs_without_injected_model(transport, tmp_path, monkeypatch):
    requests, state = transport
    monkeypatch.setattr(settings, "MODEL_PROVIDER", "vllm")
    monkeypatch.setattr(settings, "VLLM_BASE_URL", BASE)
    monkeypatch.setattr(settings, "VLLM_MODEL", MODEL)
    monkeypatch.setattr(settings, "VLLM_REVISION", REVISION)
    store = RunStore(tmp_path)
    row = store.create("Generated automatic backend question", chat_mode=True)
    store.claim()
    execute_run(tmp_path, row["id"])
    saved = store.get(row["id"])
    assert saved["status"] == "completed", saved["error"]
    assert saved["model_provider"] == "vllm" and saved["tokens"] == 120
    assert sum(r.url.path.endswith("chat/completions") for r in requests) == 1


def test_legacy_run_cannot_silently_switch_to_current_vllm_config(tmp_path, monkeypatch):
    from langchain_core.messages import AIMessage

    from tests.test_agent import make_model

    store = RunStore(tmp_path)
    row = store.create("Generated legacy question", chat_mode=True)

    def legacy(saved, conn):
        for key in ("model_provider", "model_revision", "model_vision", "embedding_config"):
            saved.pop(key, None)

    store.change(row["id"], legacy)
    monkeypatch.setattr(settings, "MODEL_PROVIDER", "vllm")
    monkeypatch.setattr(settings, "VLLM_BASE_URL", "http://external.invalid/v1")
    calls = []

    def build(**kwargs):
        calls.append(kwargs)
        return make_model(AIMessage(content="Generated legacy answer"))

    monkeypatch.setattr("eil.agent._build_model", build)
    store.claim()
    execute_run(tmp_path, row["id"])
    assert store.get(row["id"])["status"] == "completed"
    assert calls[0]["provider"] == "ollama" and calls[0]["model_name"] == row["model"]


def test_ingestion_freezes_operator_backends_and_preserves_them_on_retry(tmp_path, monkeypatch):
    from eil.ingestion import JobStore
    from eil.machines import MachineStore

    machine = MachineStore(tmp_path).create("generated-owner", "Generated machine")
    monkeypatch.setattr(settings, "MODEL_PROVIDER", "vllm")
    monkeypatch.setattr(settings, "VLLM_BASE_URL", BASE)
    monkeypatch.setattr(settings, "VLLM_MODEL", MODEL)
    monkeypatch.setattr(settings, "VLLM_REVISION", REVISION)
    jobs = JobStore(tmp_path)
    job = jobs.enqueue(machine["id"], "generated-owner", "generated.txt", b"Generated source", {})
    monkeypatch.setattr(settings, "VLLM_REVISION", "b" * 64)
    jobs.change(job["id"], status="failed")
    retried = jobs.control(job["id"], "generated-owner", "retry")
    assert retried["classifier_model_config"]["revision"] == REVISION
    assert retried["embedding_config"] == job["embedding_config"]


def test_credentials_in_endpoint_are_rejected_before_persistence(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "VLLM_EMBEDDING_BASE_URL", "http://user:secret@127.0.0.1:8003/v1")
    monkeypatch.setattr(settings, "EMBEDDING_PROVIDER", "vllm")
    store = RunStore(tmp_path)
    with pytest.raises(ValueError, match="credential-free"):
        store.create("Generated question")
    assert not store.list()


def test_real_graph_uses_sdk_tools_and_actual_usage(transport, tmp_path, monkeypatch):
    requests, state = transport
    state["tool"] = True
    model = vllm_backend.build_model(BASE, MODEL, REVISION)

    def read_generated_fact() -> str:
        """Read one generated immutable test fact."""
        return "Generated observed fact."

    # Use an ordinary case-free graph with one explicitly supplied closed tool.
    original = __import__("eil.execution", fromlist=["build_agent"]).build_agent

    def build(**kwargs):
        kwargs["evidence_tools"] = [read_generated_fact]
        return original(**kwargs)

    monkeypatch.setattr("eil.execution.build_agent", build)
    store = RunStore(tmp_path)
    row = store.create("Generated fact question", chat_mode=True)
    store.claim()
    execute_run(tmp_path, row["id"], model=model)
    saved = store.get(row["id"])
    assert saved["status"] == "completed", saved["error"]
    assert saved["model_calls"] == 2 and saved["tool_calls"] == 1 and saved["tokens"] == 240
    chat = [json.loads(r.content) for r in requests if r.url.path.endswith("chat/completions")]
    assert len(chat) == 2 and {t["function"]["name"] for t in chat[0]["tools"]} == {
        "read_generated_fact"
    }
