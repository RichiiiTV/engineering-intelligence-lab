"""Human notebook operations; no management tools are exposed to the agent."""

from uuid import UUID

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field

from .library_api import record
from .notebooks import NotebookStore
from .siemens_chat import PublicSiemensQuery

router = APIRouter(prefix="/api/machines/{machine_id}/notebooks")


def store(request):
    return NotebookStore(request.app.state.runs.store.directory)


def owner(request):
    return request.state.principal.id


class Sources(BaseModel):
    model_config = ConfigDict(extra="forbid")
    document_ids: list[UUID] = Field(default_factory=list, max_length=100)
    library_document_ids: list[UUID] = Field(default_factory=list, max_length=100)


class CreateNotebook(Sources):
    title: str = Field(min_length=1, max_length=120, pattern=r"\S")


@router.get("")
def notebooks(machine_id: UUID, request: Request):
    return {"notebooks": store(request).list(str(machine_id), owner(request))}


@router.post("", status_code=201)
def create(machine_id: UUID, payload: CreateNotebook, request: Request):
    result = store(request).create(
        str(machine_id),
        owner(request),
        payload.title,
        [str(i) for i in payload.document_ids],
        [str(i) for i in payload.library_document_ids],
    )
    record(request, "notebook_created", result["id"], {"machine_id": str(machine_id)})
    return result


@router.get("/{notebook_id}")
def notebook(machine_id: UUID, notebook_id: UUID, request: Request):
    result = store(request).get(str(notebook_id), owner(request), str(machine_id))
    return result | {"turns": store(request).turns(str(notebook_id), owner(request))}


@router.post("/{notebook_id}/sources")
def select(machine_id: UUID, notebook_id: UUID, payload: Sources, request: Request):
    store(request).get(str(notebook_id), owner(request), str(machine_id))
    result = store(request).select(
        str(notebook_id),
        owner(request),
        [str(i) for i in payload.document_ids],
        [str(i) for i in payload.library_document_ids],
    )
    record(request, "notebook_sources_selected", str(notebook_id), {"revision": result["revision"]})
    return result


class Question(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=1, max_length=4000, pattern=r"\S")
    request_id: UUID
    siemens: PublicSiemensQuery | None = None


@router.post("/{notebook_id}/questions", status_code=202)
def ask(machine_id: UUID, notebook_id: UUID, payload: Question, request: Request):
    store(request).get(str(notebook_id), owner(request), str(machine_id))
    result = store(request).submit(
        str(notebook_id),
        owner(request),
        payload.question,
        str(payload.request_id),
        request.app.state.runs,
        siemens=payload.siemens.model_dump() if payload.siemens else None,
    )
    record(request, "notebook_question_submitted", result["id"], {"notebook_id": str(notebook_id)})
    return result
