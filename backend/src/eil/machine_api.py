"""Explicit private machine/source operations, authorized at each resource boundary."""

import json
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel, ConfigDict, Field

from .evidence import EvidenceConflict, EvidenceNotFound
from .ingestion import JobStore
from .library_api import file_response, record
from .machines import MachineStore
from .passages import ProductContext

router = APIRouter(prefix="/api/machines")


def store(request):
    return MachineStore(request.app.state.runs.store.directory)


def owner(request):
    return request.state.principal.id


class MachineRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=120)
    family: str = Field(default="", max_length=60)
    profile: ProductContext = Field(default_factory=ProductContext)


@router.get("")
def machines(request: Request):
    return {"machines": store(request).list(owner(request))}


@router.post("", status_code=201)
def create(payload: MachineRequest, request: Request):
    try:
        result = store(request).create(
            owner(request), payload.name, payload.family, payload.profile.model_dump()
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    record(request, "machine_created", result["id"])
    return result


@router.get("/groups")
def groups(request: Request):
    return store(request).clusters(owner(request))


@router.get("/{machine_id}")
def machine(machine_id: UUID, request: Request):
    machine = store(request).get(str(machine_id), owner(request))
    return machine | {
        "documents": store(request)
        .documents(str(machine_id), owner(request))
        .list(all_documents=True),
        "jobs": JobStore(request.app.state.runs.store.directory).list(
            str(machine_id), owner(request)
        ),
    }


@router.post("/{machine_id}/profile")
def update(machine_id: UUID, payload: MachineRequest, request: Request):
    result = store(request).get(str(machine_id), owner(request))
    result.update(name=payload.name, family=payload.family, profile=payload.profile.model_dump())
    with store(request).evidence.connection() as conn:
        conn.execute(
            "UPDATE machines SET metadata=? WHERE id=? AND owner_id=?",
            (json.dumps(result), str(machine_id), owner(request)),
        )
    record(request, "machine_profile_updated", str(machine_id))
    return result


@router.post("/{machine_id}/sources", status_code=202)
def upload(
    machine_id: UUID,
    request: Request,
    file: UploadFile = File(),
    title: str = Form(max_length=160),
    version: str = Form(default="Unspecified", max_length=80),
    data_policy: Literal["synthetic", "licensed-public", "internal"] = Form(),
    authorized: bool = Form(),
):
    machine = store(request).get(str(machine_id), owner(request))
    try:
        if not authorized:
            raise ValueError("Confirm that you are authorized to process this material locally")
        result = JobStore(request.app.state.runs.store.directory).enqueue(
            str(machine_id),
            owner(request),
            file.filename,
            file.file.read(10 * 1024**2 + 1),
            {
                "title": title,
                "family": machine["family"] or "General",
                "version": version,
                "license_note": "User-authorized internal machine material; local private processing"
                if data_policy == "internal"
                else "User-declared " + data_policy,
                "data_policy": data_policy,
                "profile": machine["profile"],
            },
        )
        record(request, "machine_ingestion_queued", result["id"], {"machine_id": str(machine_id)})
        return result
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        file.file.close()


@router.get("/{machine_id}/sources/{document_id}/file")
def download(machine_id: UUID, document_id: UUID, request: Request):
    return file_response(
        store(request)
        .documents(str(machine_id), owner(request))
        .document(str(document_id), include_inactive=True)
    )


@router.get("/{machine_id}/sources/{document_id}/preview")
def preview(machine_id: UUID, document_id: UUID, request: Request):
    document = (
        store(request)
        .documents(str(machine_id), owner(request))
        .document(str(document_id), include_inactive=True)
    )
    if document["kind"] == "pdf":
        return {"kind": "pdf", "file_url": f"/api/machines/{machine_id}/sources/{document_id}/file"}
    text = document["raw"].decode("utf-8-sig")
    from .code_sources import inspect

    return {
        "kind": document["kind"],
        "text": text[:40000],
        "truncated": len(text) > 40000,
        "static_review": inspect(document["filename"], text),
    }


class Availability(BaseModel):
    model_config = ConfigDict(extra="forbid")
    active: bool = Field(strict=True)


@router.post("/{machine_id}/sources/{document_id}/availability")
def availability(machine_id: UUID, document_id: UUID, payload: Availability, request: Request):
    documents = store(request).documents(str(machine_id), owner(request))
    with documents.evidence.connection() as conn:
        if conn.execute(
            "SELECT 1 FROM ingestion_jobs WHERE machine_id=? AND status IN ('running','queued') AND json_extract(document,'$.document_id')=?",
            (str(machine_id), str(document_id)),
        ).fetchone():
            raise EvidenceConflict("Stop ingestion before changing source availability")
    documents.set_active(str(document_id), payload.active)
    record(
        request,
        "machine_source_enabled" if payload.active else "machine_source_archived",
        str(document_id),
        {"machine_id": str(machine_id)},
    )
    return {"active": payload.active}


@router.post("/{machine_id}/sources/{document_id}/index", status_code=202)
def index(machine_id: UUID, document_id: UUID, request: Request):
    document = (
        store(request)
        .documents(str(machine_id), owner(request))
        .document(str(document_id), include_inactive=True)
    )
    return JobStore(request.app.state.runs.store.directory).enqueue(
        str(machine_id), owner(request), document["filename"], b"", {}, str(document_id)
    )


class Purge(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sha256: str = Field(pattern="^[0-9a-f]{64}$")
    confirmation: Literal["PERMANENTLY DELETE UNREFERENCED SOURCE"]


@router.post("/{machine_id}/sources/{document_id}/purge")
def purge(machine_id: UUID, document_id: UUID, payload: Purge, request: Request):
    from .storage import StorageManager

    StorageManager(request.app.state.runs.store.directory).assert_idle()
    documents = store(request).documents(str(machine_id), owner(request))
    document = documents.document(str(document_id), include_inactive=True)
    if document["active"] or document["sha256"] != payload.sha256:
        raise EvidenceConflict(
            "Archive the source and confirm its current SHA-256 before permanent deletion"
        )
    with request.app.state.runs.store.connection() as conn:
        for row in conn.execute("SELECT document FROM runs"):
            if str(document_id) in json.loads(row[0]).get("machine_document_ids", []):
                raise EvidenceConflict("An investigation snapshot retains this source")
    with documents.evidence.connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        if conn.execute("SELECT 1 FROM sqlite_master WHERE name='notebooks'").fetchone():
            for row in conn.execute("SELECT document FROM notebooks"):
                if str(document_id) in json.loads(row[0]).get("document_ids", []):
                    raise EvidenceConflict("A notebook retains this source")
        conn.execute("DELETE FROM knowledge_passages WHERE document_id=?", (str(document_id),))
        conn.execute(
            "DELETE FROM knowledge_documents WHERE id=? AND machine_id=?",
            (str(document_id), str(machine_id)),
        )
        conn.execute(
            "UPDATE ingestion_jobs SET content=X'' WHERE json_extract(document,'$.document_id')=?",
            (str(document_id),),
        )
    record(
        request,
        "machine_source_purged",
        str(document_id),
        {"machine_id": str(machine_id), "sha256": payload.sha256},
    )
    return {"purged": True}


@router.post("/{machine_id}/jobs/{job_id}/{action}")
def control(machine_id: UUID, job_id: UUID, action: Literal["cancel", "retry"], request: Request):
    store(request).get(str(machine_id), owner(request))
    jobs = JobStore(request.app.state.runs.store.directory)
    if jobs.get(str(job_id), owner(request))["machine_id"] != str(machine_id):
        raise EvidenceNotFound("Job not found")
    result = jobs.control(str(job_id), owner(request), action)
    record(request, "machine_ingestion_" + action, str(job_id), {"machine_id": str(machine_id)})
    return result
