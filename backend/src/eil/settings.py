"""Local development settings; loads .env when python-dotenv is installed."""

from __future__ import annotations

import os
from pathlib import Path

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
STATE_DIR = Path(os.environ.get("EIL_STATE_DIR", str(ROOT / ".eil"))).resolve()
DOCLING_ARTIFACTS = Path(
    os.environ.get("EIL_DOCLING_ARTIFACTS", str(ROOT / ".eil/docling-models"))
).resolve()
