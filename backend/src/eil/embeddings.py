"""Bounded local Ollama embeddings; no remote provider or agent-selected model/URL."""

import json
import math
import os
import re
import struct
from contextlib import contextmanager
from contextvars import ContextVar
from urllib.parse import urlsplit

import httpx

from .model_policy import checked_local_model
from .performance import timed
from .settings import OLLAMA_BASE_URL

MODEL = os.environ.get("EIL_EMBEDDING_MODEL", "embeddinggemma:300m")
_lifetime = ContextVar("eil_embedding_lifetime", default="0s")
_configuration = ContextVar("eil_embedding_configuration", default=None)


@contextmanager
def use_embedding_config(config):
    token = _configuration.set(config)
    try:
        yield
    finally:
        _configuration.reset(token)


@contextmanager
def batch_lifetime(more_batches):
    """Keep a local model warm only between batches; failures expire within 30 seconds."""
    token = _lifetime.set("30s" if more_batches else "0s")
    try:
        yield
    finally:
        _lifetime.reset(token)


class EmbeddingUnavailable(RuntimeError):
    pass


def embed(texts):
    if (
        not texts
        or len(texts) > 16
        or any(not isinstance(t, str) or not 1 <= len(t) <= 4500 for t in texts)
    ):
        raise ValueError("Embedding batches require 1-16 bounded text passages")
    config = _configuration.get()
    if config is None:
        from .settings import inference_config

        _, config = inference_config()
        if config["provider"] == "ollama":
            config = config | {"model_name": MODEL, "base_url": OLLAMA_BASE_URL}
    provider = config.get("provider", "ollama")
    if provider == "vllm":
        from .agent import ModelUnavailableError
        from .vllm_backend import embedding_vectors

        try:
            with timed("embedding"):
                key, vectors = embedding_vectors(config, texts)
            return key, _packed_vectors(texts, vectors)
        except (ModelUnavailableError, ValueError, KeyError, TypeError, OverflowError) as exc:
            raise EmbeddingUnavailable(
                "Verified local vLLM embeddings are unavailable; keyword search remains available"
            ) from exc
    if provider != "ollama":
        raise EmbeddingUnavailable("Unsupported configured embedding provider")
    base_url, model_name = config["base_url"], config["model_name"]
    url = urlsplit(base_url)
    if (
        url.scheme != "http"
        or url.hostname not in {"localhost", "127.0.0.1", "::1"}
        or url.username
        or url.password
        or url.path not in {"", "/"}
        or url.query
        or url.fragment
    ):
        raise EmbeddingUnavailable("Embeddings require a loopback Ollama endpoint")
    if not re.fullmatch(r"[a-zA-Z0-9_.:/-]{1,100}", model_name):
        raise EmbeddingUnavailable("Invalid configured embedding model")
    try:
        with httpx.Client(
            base_url=base_url, timeout=30, trust_env=False, follow_redirects=False
        ) as client:
            with timed("embedding_catalog"), client.stream("GET", "/api/tags") as tags:
                tags.raise_for_status()
                catalogue = bytearray()
                for part in tags.iter_bytes():
                    catalogue.extend(part)
                    if len(catalogue) > 2 * 1024**2:
                        raise ValueError("Oversized model catalogue")
            model = checked_local_model(
                next(m for m in json.loads(catalogue)["models"] if m["name"] == model_name),
                model_name,
            )
            with (
                timed("embedding"),
                client.stream(
                    "POST",
                    "/api/embed",
                    json={
                        "model": model_name,
                        "input": texts,
                        "truncate": False,
                        "keep_alive": _lifetime.get(),
                    },
                ) as response,
            ):
                response.raise_for_status()
                content = bytearray()
                for part in response.iter_bytes():
                    content.extend(part)
                    if len(content) > 2 * 1024**2:
                        raise ValueError("Embedding response exceeded its limit")
            vectors = json.loads(content)["embeddings"]
        return f"{model_name}@{model['digest']}", _packed_vectors(texts, vectors)
    except (httpx.HTTPError, ValueError, KeyError, TypeError, StopIteration, OverflowError) as exc:
        raise EmbeddingUnavailable(
            "Local semantic search is unavailable. Install the configured embedding model and index the library; keyword search remains available."
        ) from exc


def _packed_vectors(texts, vectors):
    if len(vectors) != len(texts):
        raise ValueError("Embedding count mismatch")
    dimensions = len(vectors[0])
    if not 32 <= dimensions <= 2048:
        raise ValueError("Invalid embedding dimensions")
    packed = []
    for vector in vectors:
        if len(vector) != dimensions or any(
            not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v)
            for v in vector
        ):
            raise ValueError("Invalid vector")
        norm = math.sqrt(sum(v * v for v in vector))
        if not norm or not math.isfinite(norm):
            raise ValueError("Invalid vector norm")
        packed.append(struct.pack(f"<{dimensions}f", *(v / norm for v in vector)))
    return packed
