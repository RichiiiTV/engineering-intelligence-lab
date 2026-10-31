"""Administrator ingestion. New uploads explicitly serve the signed-in workspace."""

import json
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile

from .catalog import CatalogStore
from .evidence import EvidenceNotFound
from .ingestion import JobStore
from .library_api import admin, file_response, record
from .machine_api import Availability, JobControl

router = APIRouter(prefix="/api/admin/machine-knowledge")


def store(request):
    admin(request)
    return CatalogStore(request.app.state.runs.store.directory)


@router.get("")
def overview(request: Request):
    catalog = store(request)
    JobStore(catalog.directory)
    with catalog.evidence.connection() as conn:
        jobs = [
            json.loads(r[0])
            for r in conn.execute(
                "SELECT document FROM ingestion_jobs WHERE json_extract(document,'$.catalog')=1 ORDER BY rowid DESC LIMIT 100"
            )
        ]
    return {
        "machines": catalog.list(all_documents=True),
        "jobs": jobs,
        "scope": "active-workspace-accounts",
        "notice": "New admin uploads are published to this workspace after local automatic classification. User chats and problem attachments remain private.",
    }


@router.post("/uploads", status_code=202)
def upload(
    request: Request,
    file: UploadFile = File(),
    authorized: bool = Form(),
    data_policy: Literal["internal", "synthetic", "licensed-public"] = Form(default="internal"),
):
    catalog = store(request)
    try:
        if not authorized:
            raise ValueError(
                "Confirm you may publish this material to signed-in users in this workspace"
            )
        content = file.file.read(10 * 1024**2 + 1)
        if not file.filename or not content or len(content) > 10 * 1024**2:
            raise ValueError("Upload a nonempty source up to 10 MiB")
        actor = request.state.principal.id
        result = JobStore(catalog.directory).enqueue(
            catalog.inbox(actor),
            actor,
            file.filename,
            content,
            {
                "title": file.filename,
                "family": "Unclassified",
                "version": "Unspecified",
                "data_policy": data_policy,
                "license_note": "Administrator-authorized workspace knowledge; local processing"
                if data_policy == "internal"
                else "Administrator-declared " + data_policy,
            },
            catalog=True,
        )
        record(request, "catalog_upload_queued", result["id"])
        return result
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        file.file.close()


def document(catalog, identity):
    with catalog.evidence.connection() as conn:
        row = conn.execute(
            "SELECT d.machine_id FROM knowledge_documents d JOIN machine_catalog c ON c.machine_id=d.machine_id WHERE d.id=?",
            (identity,),
        ).fetchone()
    if not row:
        raise EvidenceNotFound("Catalog source not found")
    return catalog.library(row[0])


@router.get("/documents/{document_id}/file")
def download(document_id: UUID, request: Request):
    catalog = store(request)
    return file_response(
        document(catalog, str(document_id)).document(str(document_id), include_inactive=True)
    )


@router.post("/documents/{document_id}/availability")
def availability(document_id: UUID, payload: Availability, request: Request):
    catalog = store(request)
    document(catalog, str(document_id)).set_active(str(document_id), payload.active)
    record(
        request,
        "catalog_source_enabled" if payload.active else "catalog_source_archived",
        str(document_id),
    )
    return {"active": payload.active}


@router.post("/jobs/{job_id}/{action}")
def control(
    job_id: UUID,
    action: Literal["retry", "cancel", "discard"],
    request: Request,
    payload: JobControl | None = None,
):
    catalog = store(request)
    jobs = JobStore(catalog.directory)
    job = jobs.get(str(job_id))
    if not job.get("catalog"):
        raise EvidenceNotFound("Catalog job not found")
    if action == "discard":
        if not payload or payload.confirmation != "DISCARD STAGED UPLOAD":
            raise HTTPException(409, "Review and confirm removal of this staged upload")
        result = jobs.discard(str(job_id), job["owner_id"])
    else:
        result = jobs.control(str(job_id), job["owner_id"], action)
    record(request, "catalog_ingestion_" + action, str(job_id))
    return result
