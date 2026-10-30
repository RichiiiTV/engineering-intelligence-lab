"""Human-operated knowledge administration and audit views. No agent mutations."""

import json
from typing import Literal
from urllib.parse import quote

from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field

from .audit import AuditStore
from .audit import status as audit_status
from .auth import AuthStore
from .embeddings import EmbeddingUnavailable
from .evidence import EvidenceNotFound
from .knowledge import KnowledgeStore
from .pdf_ingest import MAX_PDF_BYTES, parse_pdf

router = APIRouter()


def store(request):
    return KnowledgeStore(request.app.state.runs.store.directory)


def admin(request):
    if request.state.principal.role != "admin":
        raise HTTPException(status_code=403, detail="Administrator access is required")


def record(request, kind, subject, details=None):
    auth = AuthStore(request.app.state.runs.store.directory)
    with auth.connection() as conn:
        auth.audit(conn, request.state.principal.id, kind, subject, details)


@router.get("/api/library/documents")
def documents(request: Request):
    return {"documents": store(request).list(all_documents=request.state.principal.role == "admin")}


@router.post("/api/library/documents", status_code=201)
def upload(
    request: Request,
    file: UploadFile = File(),
    title: str = Form(max_length=160),
    family: str = Form(max_length=60),
    version: str = Form(max_length=80),
    license_note: str = Form(max_length=300),
    data_policy: Literal["synthetic", "licensed-public"] = Form(),
    confirmed: bool = Form(),
):
    admin(request)
    try:
        if not confirmed:
            raise ValueError("Confirm that this document can be shared with all workspace users")
        result = store(request).add(
            file.filename,
            file.file.read(MAX_PDF_BYTES + 1),
            title=title,
            family=family,
            version=version,
            license_note=license_note,
            data_policy=data_policy,
            actor=request.state.principal.id,
            pdf_parser=getattr(request.app.state, "pdf_parser", parse_pdf),
        )
        record(
            request,
            "library_document_added",
            result["id"],
            {"sha256": result["sha256"], "version": result["version"]},
        )
        return result
    except (ValueError, UnicodeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        file.file.close()


class Availability(BaseModel):
    model_config = ConfigDict(extra="forbid")
    active: bool = Field(strict=True)


@router.post("/api/library/documents/{document_id}/availability")
def availability(document_id: str, payload: Availability, request: Request):
    admin(request)
    store(request).set_active(document_id, payload.active)
    record(
        request,
        "library_document_enabled" if payload.active else "library_document_disabled",
        document_id,
    )
    return {"active": payload.active}


@router.post("/api/library/documents/{document_id}/index")
def index(document_id: str, request: Request):
    admin(request)
    try:
        result = store(request).index(document_id)
        record(request, "library_document_indexed", document_id, result)
        return result
    except EmbeddingUnavailable as exc:
        record(request, "library_index_failed", document_id)
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def file_response(document):
    return Response(
        document["raw"],
        media_type="application/pdf" if document["kind"] == "pdf" else "text/plain; charset=utf-8",
        headers={
            "Content-Disposition": "attachment; filename*=UTF-8''"
            + quote(document["filename"], safe="")
        },
    )


@router.get("/api/library/documents/{document_id}/file")
def document_file(document_id: str, request: Request):
    return file_response(
        store(request).document(
            document_id, include_inactive=request.state.principal.role == "admin"
        )
    )


@router.get("/api/investigations/{run_id}/library/documents/{document_id}/file")
def run_document_file(run_id: str, document_id: str, request: Request):
    run = request.app.state.runs.store.get(run_id)
    if document_id in run.get("machine_document_ids", []) and run.get("machine_id"):
        from .machines import MachineStore

        return file_response(
            MachineStore(request.app.state.runs.store.directory)
            .documents(run["machine_id"], run["owner_id"])
            .document(document_id, include_inactive=True)
        )
    if document_id not in run.get("library_document_ids", []):
        raise EvidenceNotFound("Document is outside this investigation's library snapshot")
    return file_response(store(request).document(document_id, include_inactive=True))


@router.get("/api/admin/audit")
def audit(
    request: Request,
    after: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    actor: str = Query(default="", max_length=40),
    kind: str = Query(default="", max_length=80),
):
    admin(request)
    auth = AuthStore(request.app.state.runs.store.directory)
    names = {u["id"]: u["username"] for u in auth.users(limit=1000)}
    audit_store = AuditStore(auth.directory)
    rows = audit_store.events(after, limit + 1, actor, kind)
    integrity = audit_store.integrity()
    return {
        "events": [
            dict(r) | {"details": json.loads(r["details"]), "actor": names.get(r["actor_id"])}
            for r in rows[:limit]
        ],
        "next_after": rows[limit - 1]["id"] if len(rows) > limit else None,
        "integrity": integrity,
        "delivery": audit_status(auth.directory),
    }


@router.get("/api/admin/audit/export")
def audit_export(request: Request, after: int = Query(default=0, ge=0)):
    result = audit(request, after=after, limit=100, actor="", kind="")
    record(request, "audit_page_exported", None, {"after": after, "count": len(result["events"])})
    return Response(
        json.dumps(result, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="eil-audit-page.json"'},
    )


@router.post("/api/admin/audit/archive")
def audit_archive(request: Request):
    admin(request)
    from .api import maintenance

    maintenance(request)
    result = AuditStore(request.app.state.runs.store.directory).archive()
    record(request, "audit_archived", None, result)
    return result


@router.get("/api/admin/audit/complete")
def audit_complete(request: Request):
    admin(request)
    from fastapi.responses import StreamingResponse

    directory = request.app.state.runs.store.directory

    def stream():
        audit_store = AuditStore(directory)
        yield json.dumps({"integrity": audit_store.integrity()}) + "\n"
        after = 0
        while rows := audit_store.events(after, 500):
            for row in rows:
                yield json.dumps(row) + "\n"
            after = rows[-1]["id"]

    return StreamingResponse(
        stream(),
        media_type="application/x-ndjson",
        headers={"Content-Disposition": 'attachment; filename="eil-complete-audit.jsonl"'},
    )
