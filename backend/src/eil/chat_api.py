"""Authenticated chat and private problem attachments. No user-managed machine scope."""

import json
from uuid import UUID

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response

from .chat import ChatStore
from .library_api import file_response, record
from .problem_sources import MAX_TOTAL, ProblemStore, parse

router = APIRouter(prefix="/api/chat")


def store(request):
    return ChatStore(request.app.state.runs.store.directory)


def owner(request):
    return request.state.principal.id


@router.get("/conversations")
def conversations(request: Request):
    return {"conversations": store(request).list(owner(request))}


@router.get("/conversations/{conversation_id}")
def conversation(conversation_id: UUID, request: Request):
    chats = store(request)
    result = chats.get(str(conversation_id), owner(request))
    turns = chats.turns(str(conversation_id), owner(request))
    ids = {i for r in turns for i in r.get("problem_attachment_ids", [])}
    attachments = [json.loads(chats.problems.get(i, owner(request))["metadata"]) for i in ids]
    return result | {"turns": turns, "attachments": attachments}


@router.post("/questions", status_code=202)
def ask(
    request: Request,
    question: str = Form(min_length=1, max_length=4000),
    request_id: UUID = Form(),
    conversation_id: UUID | None = Form(default=None),
    files: list[UploadFile] = File(default=[]),
):
    try:
        if len(files) > 4:
            raise ValueError("Attach up to four files, including at most two images")
        parsed = []
        total = 0
        for file in files:
            content = file.file.read(MAX_TOTAL + 1)
            total += len(content)
            if total > MAX_TOTAL:
                raise ValueError("Problem attachments exceed 10 MiB in total")
            parsed.append(parse(file.filename, content))
        if sum(p[0]["kind"] == "image" for p in parsed) > 2:
            raise ValueError("Attach at most two images per question")
        result = store(request).submit(
            owner(request),
            question,
            str(request_id),
            request.app.state.runs,
            parsed,
            str(conversation_id) if conversation_id else None,
        )
        record(
            request,
            "chat_question_submitted",
            result["id"],
            {"conversation_id": result["chat_context"]["id"], "attachments": len(parsed)},
        )
        return result
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    finally:
        for file in files:
            file.file.close()


@router.get("/attachments/{attachment_id}/file")
def download(attachment_id: UUID, request: Request):
    source = ProblemStore(request.app.state.runs.store.directory).get(
        str(attachment_id), owner(request)
    )
    record(request, "problem_attachment_downloaded", str(attachment_id))
    return file_response(source)


@router.get("/attachments/{attachment_id}/preview")
def preview(attachment_id: UUID, request: Request):
    source = ProblemStore(request.app.state.runs.store.directory).get(
        str(attachment_id), owner(request)
    )
    if source["kind"] != "image":
        raise HTTPException(422, "This attachment is a text log")
    return Response(
        source["normalized"],
        media_type="image/jpeg",
        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "no-store"},
    )
