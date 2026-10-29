"""Local read-only analytics and durable, bounded investigation jobs."""

from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from typing import Literal
from urllib.parse import quote
from uuid import UUID

from fastapi import (
    APIRouter,
    FastAPI,
    File,
    Form,
    Header,
    HTTPException,
    Query,
    Request,
    UploadFile,
)
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .analytics import ALLOWED_STATIONS, compare_stations, provisional_report, station_metrics
from .drafts import DraftStore
from .evidence import EvidenceConflict, EvidenceNotFound, EvidenceStore
from .exports import export_investigation
from .pdf_ingest import MAX_PDF_BYTES, PDFBusy, PDFUnavailable, parse_pdf
from .runs import STOPPED, QueueFull, RunConflict, RunLimits, RunNotFound
from .service import RunService
from .settings import DATASET_NAME, ROOT
from .uploads import UploadBodyLimit

router = APIRouter()


class InvestigationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=1, max_length=4000)
    limits: RunLimits = Field(default_factory=RunLimits)
    case_id: UUID | None = None
    use_mock_mcp: bool = False

    @field_validator("question")
    @classmethod
    def reject_blank_question(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Question must contain non-whitespace characters")
        return value


@router.get("/api/health")
def health():
    return {"status": "ok", "mode": "synthetic-read-only"}


@router.get("/api/datasets")
def datasets():
    return {"datasets": [{"id": DATASET_NAME, "type": "synthetic-inspection-csv"}]}


@router.get("/api/examples/{name}")
def example(name: Literal["inspection.csv", "maintenance.pdf"]):
    # Fixed generated fixtures only, never a user-supplied host path.
    path = ROOT / (
        "data/synthetic_inspection_v1.csv"
        if name == "inspection.csv"
        else "output/pdf/synthetic-maintenance-note.pdf"
    )
    return FileResponse(path, filename=name)


@router.get("/api/metrics/summary")
def summary():
    return {"ranked_stations": compare_stations()}


@router.get("/api/metrics/stations/{station_id}")
def station(station_id: str):
    if station_id not in ALLOWED_STATIONS:
        raise HTTPException(status_code=404, detail="Unknown station")
    return {
        "baseline": station_metrics(station_id, "baseline"),
        "incident": station_metrics(station_id, "incident"),
    }


@router.get("/api/investigations/demo-report")
def demo_report():
    return provisional_report()


def service(request: Request) -> RunService:
    if not hasattr(request.app.state, "runs"):
        raise HTTPException(status_code=503, detail="Run service is not initialized")
    return request.app.state.runs


@router.post("/api/investigations", status_code=202)
def investigate(payload: InvestigationRequest, request: Request):
    try:
        return service(request).submit(
            payload.question,
            payload.limits,
            case_id=str(payload.case_id) if payload.case_id else None,
            use_mock_mcp=payload.use_mock_mcp,
        )
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/api/investigations")
def investigations(request: Request, case_id: UUID | None = None):
    return {
        "investigations": service(request).store.list(case_id=str(case_id) if case_id else None)
    }


@router.get("/api/investigations/{run_id}")
def investigation(run_id: str, request: Request):
    return service(request).store.get(run_id)


@router.get("/api/investigations/{run_id}/export")
def export(run_id: str, request: Request):
    try:
        return export_investigation(service(request).store, run_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


class CaseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=120)


class DraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=120)
    body: str = Field(min_length=1, max_length=20000)


class DecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["approve", "reject"]
    expected_sha256: str = Field(pattern="^[0-9a-f]{64}$")


@router.get("/api/integrations/mock-mcp")
def mock_mcp_catalog():
    from .mock_mcp import catalog

    return catalog()


@router.post("/api/investigations/{run_id}/draft-proposals", status_code=201)
def propose_draft(run_id: str, payload: DraftRequest, request: Request):
    try:
        return DraftStore(service(request).store).propose(run_id, payload.title, payload.body)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/api/approvals/{proposal_id}")
def proposal(proposal_id: str, request: Request):
    return DraftStore(service(request).store).get(proposal_id)


@router.post("/api/approvals/{proposal_id}/decision")
def decide_draft(proposal_id: str, payload: DecisionRequest, request: Request):
    return DraftStore(service(request).store).decide(
        proposal_id, payload.decision, payload.expected_sha256
    )


@router.get("/api/cases/{case_id}/drafts")
def drafts(case_id: str, request: Request):
    store = DraftStore(service(request).store)
    return {"drafts": store.drafts(case_id), "proposals": store.proposals(case_id)}


def evidence(request):
    return EvidenceStore(service(request).store.directory)


@router.post("/api/cases", status_code=201)
def create_case(payload: CaseRequest, request: Request):
    try:
        return evidence(request).create_case(payload.title)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/api/cases")
def cases(request: Request):
    return {"cases": evidence(request).cases()}


@router.get("/api/cases/{case_id}")
def case(case_id: str, request: Request):
    store = evidence(request)
    return {**store.case(case_id), "sources": store.sources(case_id)}


@router.post("/api/cases/{case_id}/sources", status_code=201)
def upload(
    case_id: str,
    request: Request,
    file: UploadFile = File(),
    data_policy: Literal["synthetic", "licensed-public"] = Form(),
):
    # Read at most one byte over the largest allowed upload. The original name is metadata only.
    try:
        content = file.file.read(MAX_PDF_BYTES + 1)
        parser = getattr(request.app.state, "pdf_parser", parse_pdf)
        return evidence(request).ingest(
            case_id, file.filename, content, pdf_parser=parser, data_policy=data_policy
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        file.file.close()


@router.get("/api/cases/{case_id}/sources/{source_id}/file")
def download(case_id: str, source_id: str, request: Request):
    source = evidence(request).source(case_id, source_id)
    return Response(
        content=source["raw"],
        media_type="application/pdf" if source["kind"] == "pdf" else "text/csv",
        headers={
            "Content-Disposition": "attachment; filename*=UTF-8''"
            + quote(source["filename"], safe="")
        },
    )


@router.get("/api/cases/{case_id}/search")
def search(
    case_id: str,
    request: Request,
    q: str = Query(min_length=1, max_length=500),
    limit: int = Query(default=3, ge=1, le=5),
):
    try:
        return evidence(request).search(case_id, q, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/api/cases/{case_id}/sources/{source_id}/comparison")
def comparison(case_id: str, source_id: str, request: Request):
    try:
        return evidence(request).compare(case_id, source_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/api/cases/{case_id}/citations/{citation_id}")
def citation(case_id: str, citation_id: str, request: Request):
    return evidence(request).resolve(case_id, citation_id)


@router.post("/api/investigations/{run_id}/{action}", status_code=202)
def control(run_id: str, action: Literal["pause", "resume", "cancel"], request: Request):
    return service(request).store.control(run_id, action)


@router.get("/api/investigations/{run_id}/events")
async def events(
    run_id: str,
    request: Request,
    after: int = Query(default=0, ge=0),
    last_event_id: int | None = Header(default=None, ge=0),
):
    store = service(request).store
    store.get(run_id)

    async def stream():
        cursor = max(after, last_event_id or 0)
        idle = 0
        while not await request.is_disconnected():
            batch = store.events(run_id, cursor)
            for event in batch:
                cursor = event["id"]
                yield f"id: {cursor}\nevent: {event['type']}\ndata: {json.dumps(event)}\n\n"
            if batch:
                idle = 0
                continue
            if store.get(run_id)["status"] in STOPPED:
                break
            idle += 1
            if idle % 100 == 0:
                yield ": heartbeat\n\n"
            await asyncio.sleep(0.1)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def create_app(service_factory=RunService):
    @asynccontextmanager
    async def lifespan(app):
        with service_factory() as runner:
            app.state.runs = runner
            yield

    app = FastAPI(title="Engineering Intelligence Lab", version="0.4.0", lifespan=lifespan)
    app.add_middleware(UploadBodyLimit)
    app.include_router(router)

    @app.middleware("http")
    async def local_browser_origin(request, call_next):
        origin = request.headers.get("origin")
        if (
            request.method in {"POST", "PUT", "PATCH", "DELETE"}
            and origin
            and origin
            not in {
                str(request.base_url).rstrip("/"),
                "http://127.0.0.1:5173",
                "http://localhost:5173",
            }
        ):
            return JSONResponse(status_code=403, content={"detail": "Unapproved browser origin"})
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        if request.url.path == "/":
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
                "connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
            )
        return response

    ui = ROOT / "frontend" / "dist"

    @app.get("/", include_in_schema=False)
    def workbench():
        if not (ui / "index.html").is_file():
            raise HTTPException(
                status_code=503, detail="Build the UI: cd frontend; npm ci; npm run build"
            )
        return FileResponse(ui / "index.html", headers={"Cache-Control": "no-cache"})

    # API paths keep their normal 404 behavior; only hashed build assets are mounted.
    app.mount("/assets", StaticFiles(directory=ui / "assets", check_dir=False), name="ui-assets")

    @app.exception_handler(RunNotFound)
    async def missing(request, exc):
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(RunConflict)
    async def conflict(request, exc):
        return JSONResponse(
            status_code=429 if isinstance(exc, QueueFull) else 409, content={"detail": str(exc)}
        )

    @app.exception_handler(EvidenceNotFound)
    async def missing_evidence(request, exc):
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(EvidenceConflict)
    async def conflicting_evidence(request, exc):
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(PDFUnavailable)
    async def unavailable_pdf(request, exc):
        return JSONResponse(
            status_code=429 if isinstance(exc, PDFBusy) else 503, content={"detail": str(exc)}
        )

    return app


app = create_app()
