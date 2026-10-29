"""Authenticated functional readiness; no credentials, prompts or device probes."""

import sqlite3
from contextlib import closing

import httpx

from .audit import status
from .database import DATABASE_BYTES
from .knowledge import KnowledgeStore
from .settings import DOCLING_ARTIFACTS, OLLAMA_BASE_URL, OLLAMA_MODEL


def readiness(directory):
    from pathlib import Path

    checks = {}
    for name, kind in [
        ("auth.sqlite3", "auth"),
        ("runs.sqlite3", "runs"),
        ("data/evidence.sqlite3", "evidence"),
    ]:
        with closing(sqlite3.connect(Path(directory) / name)) as conn:
            used = (
                conn.execute("PRAGMA page_count").fetchone()[0]
                - conn.execute("PRAGMA freelist_count").fetchone()[0]
            ) * conn.execute("PRAGMA page_size").fetchone()[0]
            checks[kind] = {
                "ready": used < DATABASE_BYTES[kind] * 0.9,
                "used_bytes": used,
                "limit_bytes": DATABASE_BYTES[kind],
            }
    checks["audit"] = status(directory)
    checks["audit"]["ready"] = checks["audit"]["healthy"] and checks["audit"]["pending"] == 0
    try:
        with httpx.Client(timeout=3, trust_env=False, follow_redirects=False) as client:
            reply = client.get(OLLAMA_BASE_URL.rstrip("/") + "/api/tags")
            reply.raise_for_status()
            installed = {m["name"] for m in reply.json()["models"]}
        checks["generation"] = {"ready": OLLAMA_MODEL in installed}
    except (httpx.HTTPError, ValueError, KeyError):
        checks["generation"] = {"ready": False}
    documents = KnowledgeStore(directory).list()
    checks["library"] = {
        "ready": all(d["passages"] == d["indexed_passages"] for d in documents),
        "documents": len(documents),
    }
    try:
        from .isolated_pdf import command

        command("eil-readiness-probe")
        parser_ready = DOCLING_ARTIFACTS.is_dir()
    except (RuntimeError, OSError):
        parser_ready = False
    checks["pdf"] = {
        "ready": parser_ready,
        "note": "Isolated image and local assets checked; document parsing remains bounded per job.",
    }
    return {"ready": all(c["ready"] for c in checks.values()), "checks": checks}
