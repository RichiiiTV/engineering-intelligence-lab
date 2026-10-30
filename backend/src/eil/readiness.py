"""Authenticated functional readiness; no credentials, prompts or device probes."""

import sqlite3
from contextlib import closing

import httpx

from .audit import status
from .database import DATABASE_BYTES
from .embeddings import MODEL
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
            models = reply.json()["models"]
            installed = {m["name"] for m in models}
            embedding = next((m for m in models if m["name"] == MODEL), {})
            embedding_key = f"{MODEL}@{embedding.get('digest', '')}|retrieval-v2"
        checks["generation"] = {"ready": OLLAMA_MODEL in installed}
        checks["embedding"] = {"ready": bool(embedding) and not embedding.get("remote_host")}
    except (httpx.HTTPError, ValueError, KeyError):
        checks["generation"] = {"ready": False}
        checks["embedding"] = {"ready": False}
        embedding_key = None
    documents = KnowledgeStore(directory).list()
    checks["library"] = {
        "ready": all(d["passages"] == d["indexed_passages"] for d in documents),
        "documents": len(documents),
    }
    with KnowledgeStore(directory).evidence.connection() as conn:
        stale = conn.execute(
            "SELECT count(*) FROM knowledge_passages p JOIN knowledge_documents d ON d.id=p.document_id WHERE d.active=1 AND d.machine_id IS NULL AND (p.model IS NULL OR p.model<>?)",
            (embedding_key or "",),
        ).fetchone()[0]
    checks["library"]["stale_passages"] = stale
    checks["library"]["ready"] = checks["library"]["ready"] and stale == 0
    try:
        from .isolated_pdf import command

        command("eil-readiness-probe")
        command("eil-readiness-machine-probe", image="eil-pdf-worker:2")
        parser_ready = DOCLING_ARTIFACTS.is_dir()
    except (RuntimeError, OSError):
        parser_ready = False
    checks["pdf"] = {
        "ready": parser_ready,
        "note": "Isolated image and local assets checked; document parsing remains bounded per job.",
    }
    return {"ready": all(c["ready"] for c in checks.values()), "checks": checks}
