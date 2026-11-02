"""Local development settings; loads .env when python-dotenv is installed."""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlsplit

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

ROOT = Path(__file__).resolve().parents[3]
if load_dotenv is not None:
    load_dotenv(ROOT / ".env", override=False)
DATA_DIR = ROOT / "data"
DATASET_NAME = os.environ.get("EIL_DATASET", "synthetic_inspection_v1.csv")
OLLAMA_BASE_URL = os.environ.get("EIL_OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("EIL_OLLAMA_MODEL", "qwen3.5:4b-q8_0")
MODEL_PROVIDER = os.environ.get("EIL_MODEL_PROVIDER", "ollama")
VLLM_BASE_URL = os.environ.get("EIL_VLLM_BASE_URL", "http://127.0.0.1:8002/v1")
VLLM_MODEL = os.environ.get("EIL_VLLM_MODEL", "")
VLLM_REVISION = os.environ.get("EIL_VLLM_REVISION", "")
VLLM_VISION = os.environ.get("EIL_VLLM_VISION", "0") == "1"
EMBEDDING_PROVIDER = os.environ.get("EIL_EMBEDDING_PROVIDER", MODEL_PROVIDER)
VLLM_EMBEDDING_BASE_URL = os.environ.get("EIL_VLLM_EMBEDDING_BASE_URL", "http://127.0.0.1:8003/v1")
VLLM_EMBEDDING_MODEL = os.environ.get("EIL_VLLM_EMBEDDING_MODEL", "")
VLLM_EMBEDDING_REVISION = os.environ.get("EIL_VLLM_EMBEDDING_REVISION", "")


def inference_config(*, ollama_base_url=None, ollama_model=None):
    """Trusted operator settings only; snapshot these without any credentials."""
    if MODEL_PROVIDER not in {"ollama", "vllm"} or EMBEDDING_PROVIDER not in {"ollama", "vllm"}:
        raise ValueError("Select an explicit supported model/embedding provider")
    generation = {
        "provider": MODEL_PROVIDER,
        "model_name": VLLM_MODEL if MODEL_PROVIDER == "vllm" else (ollama_model or OLLAMA_MODEL),
        "base_url": VLLM_BASE_URL
        if MODEL_PROVIDER == "vllm"
        else (ollama_base_url or OLLAMA_BASE_URL),
        "revision": VLLM_REVISION if MODEL_PROVIDER == "vllm" else "",
        "vision": VLLM_VISION if MODEL_PROVIDER == "vllm" else False,
    }
    embedding = {
        "provider": EMBEDDING_PROVIDER,
        "model_name": VLLM_EMBEDDING_MODEL
        if EMBEDDING_PROVIDER == "vllm"
        else os.environ.get("EIL_EMBEDDING_MODEL", "embeddinggemma:300m"),
        "base_url": VLLM_EMBEDDING_BASE_URL if EMBEDDING_PROVIDER == "vllm" else OLLAMA_BASE_URL,
        "revision": VLLM_EMBEDDING_REVISION if EMBEDDING_PROVIDER == "vllm" else "",
    }
    for config in (generation, embedding):
        try:
            url = urlsplit(config["base_url"])
            if (
                url.scheme not in {"http", "https"}
                or not url.hostname
                or url.username
                or url.password
                or url.query
                or url.fragment
            ):
                raise ValueError("Invalid model endpoint")
            _ = url.port
        except (TypeError, ValueError) as exc:
            if config["provider"] == "ollama":
                raise ValueError(
                    "Configure an HTTP Ollama URL without embedded credentials"
                ) from exc
            raise ValueError("Model endpoints must be credential-free HTTP URLs") from exc
    return generation, embedding


STATE_DIR = Path(os.environ.get("EIL_STATE_DIR", str(ROOT / ".eil"))).resolve()
DOCLING_ARTIFACTS = Path(
    os.environ.get("EIL_DOCLING_ARTIFACTS", str(ROOT / ".eil/docling-models"))
).resolve()
