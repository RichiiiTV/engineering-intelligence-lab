"""Bounded local Ollama embeddings; no remote provider or agent-selected model/URL."""

import math
import os
import re
import struct
from urllib.parse import urlsplit

import httpx

from .settings import OLLAMA_BASE_URL

MODEL = os.environ.get("EIL_EMBEDDING_MODEL", "embeddinggemma:300m")


class EmbeddingUnavailable(RuntimeError):
    pass


def embed(texts):
    if (
        not texts
        or len(texts) > 16
        or any(not isinstance(t, str) or not 1 <= len(t) <= 4500 for t in texts)
    ):
        raise ValueError("Embedding batches require 1-16 bounded text passages")
    url = urlsplit(OLLAMA_BASE_URL)
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
    if not re.fullmatch(r"[a-zA-Z0-9_.:/-]{1,100}", MODEL):
        raise EmbeddingUnavailable("Invalid configured embedding model")
    try:
        with httpx.Client(
            base_url=OLLAMA_BASE_URL, timeout=30, trust_env=False, follow_redirects=False
        ) as client:
            tags = client.get("/api/tags")
            tags.raise_for_status()
            model = next((m for m in tags.json()["models"] if m["name"] == MODEL), None)
            if not model or not model.get("digest"):
                raise ValueError("Embedding model is not installed")
            if model.get("remote_host") or MODEL.endswith(":cloud"):
                raise ValueError("Cloud embedding models are not allowed")
            with client.stream(
                "POST",
                "/api/embed",
                json={"model": MODEL, "input": texts, "truncate": False, "keep_alive": "0s"},
            ) as response:
                response.raise_for_status()
                content = bytearray()
                for part in response.iter_bytes():
                    content.extend(part)
                    if len(content) > 2 * 1024**2:
                        raise ValueError("Embedding response exceeded its limit")
            import json

            vectors = json.loads(content)["embeddings"]
        if len(vectors) != len(texts):
            raise ValueError("Embedding count mismatch")
        dimensions = len(vectors[0])
        if not 32 <= dimensions <= 2048:
            raise ValueError("Invalid embedding dimensions")
        packed = []
        for vector in vectors:
            if len(vector) != dimensions or any(
                not isinstance(v, (int, float)) or not math.isfinite(v) for v in vector
            ):
                raise ValueError("Invalid vector")
            norm = math.sqrt(sum(v * v for v in vector))
            if not norm or not math.isfinite(norm):
                raise ValueError("Invalid vector norm")
            packed.append(struct.pack(f"<{dimensions}f", *(v / norm for v in vector)))
        return f"{MODEL}@{model['digest']}", packed
    except (httpx.HTTPError, ValueError, KeyError, TypeError, StopIteration, OverflowError) as exc:
        raise EmbeddingUnavailable(
            "Local semantic search is unavailable. Install the configured embedding model and index the library; keyword search remains available."
        ) from exc
