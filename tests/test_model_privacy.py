import httpx
import pytest
from ollama import ResponseError

from eil import agent, embeddings


def entry(**overrides):
    return {
        "name": embeddings.MODEL,
        "model": embeddings.MODEL,
        "digest": "a" * 64,
        "details": {"format": "gguf"},
        "size": 2 * 1024**2,
        **overrides,
    }


@pytest.mark.parametrize(
    "metadata",
    [
        entry(remote_model="remote-alias"),
        entry(remote_host="https://external.invalid"),
        entry(details={"format": "unknown"}),
        entry(digest="not-a-digest"),
        entry(size=0),
    ],
)
def test_unverified_embedding_model_never_receives_private_text(monkeypatch, metadata):
    original = httpx.Client
    requests = []

    def handler(request):
        requests.append((request.method, request.url.path))
        assert request.method == "GET" and not request.content
        return httpx.Response(200, json={"models": [metadata]})

    monkeypatch.setattr(
        "eil.embeddings.httpx.Client",
        lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs),
    )
    with pytest.raises(embeddings.EmbeddingUnavailable):
        embeddings.embed(["Generated private-text sentinel"])
    assert requests == [("GET", "/api/tags")]


def test_verified_embedding_digest_and_vector_are_preserved(monkeypatch):
    original = httpx.Client

    def handler(request):
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [entry()]})
        assert request.url.path == "/api/embed" and request.url.host in {"localhost", "127.0.0.1"}
        return httpx.Response(200, json={"embeddings": [[1.0] * 64]})

    monkeypatch.setattr(
        "eil.embeddings.httpx.Client",
        lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs),
    )
    key, vectors = embeddings.embed(["Generated fixture"])
    assert key == embeddings.MODEL + "@" + "a" * 64 and len(vectors[0]) == 64 * 4


def test_local_generation_does_not_forward_prompt_to_redirect_target(monkeypatch):
    original = httpx.Client
    requests = []

    def handler(request):
        requests.append((request.url.host, request.url.path))
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"model": agent.OLLAMA_MODEL}]})
        assert request.url.host in {"localhost", "127.0.0.1"}
        return httpx.Response(307, headers={"Location": "https://external.invalid/collect"})

    monkeypatch.setattr(
        "httpx.Client", lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs)
    )
    model = agent._build_model(max_output_tokens=32)
    assert model._client._client.follow_redirects is False
    assert model._async_client._client.follow_redirects is False
    with pytest.raises(ResponseError):
        model.invoke("Generated private-text sentinel")
    assert all(host in {"localhost", "127.0.0.1"} for host, _ in requests)
    assert requests[-1][1] == "/api/chat"
