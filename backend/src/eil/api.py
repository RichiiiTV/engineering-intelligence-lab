"""Local read-only analytics and durable, bounded investigation jobs."""

from __future__ import annotations

import asyncio
import json
import re
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
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .analytics import ALLOWED_STATIONS, compare_stations, provisional_report, station_metrics
from .auth import (
    COOKIE,
    AuthenticationError,
    AuthenticationLimited,
    AuthStore,
    adopt_legacy,
    local_owner,
)
from .auth_api import router as auth_router
from .claims import Claims, verify
from .database import StorageFull
from .drafts import DraftStore
from .evidence import EvidenceConflict, EvidenceNotFound, EvidenceStore
from .exports import export_investigation
from .library_api import router as library_router
from .machine_api import router as machine_router
from .notebook_api import router as notebook_router
from .pdf_ingest import MAX_PDF_BYTES, PDFBusy, PDFUnavailable, parse_pdf
from .runs import STOPPED, QueueFull, RunConflict, RunLimits, RunNotFound
from .service import RunService
from .settings import DATASET_NAME, ROOT
from .siemens_chat import PublicSiemensQuery
from .storage import CASE_LOCK, StorageManager
from .uploads import UploadBodyLimit

router = APIRouter()


class InvestigationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=1, max_length=4000)
    limits: RunLimits = Field(default_factory=RunLimits)
    case_id: UUID | None = None
    use_mock_mcp: bool = False
    siemens: PublicSiemensQuery | None = None
    chat_mode: bool = Field(default=False, strict=True)
    use_library: bool = Field(default=False, strict=True)
    library_document_ids: list[UUID] | None = Field(default=None, max_length=100)
    machine_id: UUID | None = None
    machine_document_ids: list[UUID] | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def validate_chat_scope(self):
        if self.chat_mode and self.case_id is not None:
            raise ValueError("Use a case investigation when files are attached")
        if self.library_document_ids is not None and not self.use_library:
            raise ValueError("Enable the library to select library documents")
        return self

    @field_validator("question")
    @classmethod
    def reject_blank_question(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Question must contain non-whitespace characters")
        return value


@router.get("/api/health")
def health():
    return {"status": "ok", "mode": "synthetic-read-only"}


@router.get("/api/ready")
def ready(request: Request):
    from .readiness import readiness

    result = readiness(service(request).store.directory)
    ingestion = getattr(request.app.state, "ingestion", None)
    result["checks"]["ingestion"] = {
        "ready": bool(
            ingestion
            and ingestion.thread
            and ingestion.thread.is_alive()
            and not ingestion.fatal_error
        )
    }
    result["ready"] = result["ready"] and result["checks"]["ingestion"]["ready"]
    return JSONResponse(result, status_code=200 if result["ready"] else 503)


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


def owned_case(request, case_id, *, include_deleted=False):
    row = evidence(request).case(case_id, include_deleted=include_deleted)
    if row["owner_id"] != request.state.principal.id:
        raise EvidenceNotFound("Case not found")
    return row


def maintenance(request):
    if service(request)._active_id is not None:
        raise RunConflict("Wait for the active investigation worker to stop before maintenance")
    manager = StorageManager(service(request).store.directory)
    manager.assert_idle()
    return manager


def administrator(request):
    if request.state.principal.role != "admin":
        raise HTTPException(status_code=403, detail="Administrator access is required")


@router.post("/api/cases/{case_id}/trash")
def trash_case(case_id: str, request: Request):
    return StorageManager(service(request).store.directory).trash(case_id, request.state.principal)


@router.post("/api/cases/{case_id}/restore")
def restore_case(case_id: str, request: Request):
    return StorageManager(service(request).store.directory).trash(
        case_id, request.state.principal, restore=True
    )


@router.get("/api/admin/storage")
def storage_status(request: Request):
    administrator(request)
    return StorageManager(service(request).store.directory).status()


@router.post("/api/admin/backups", status_code=201)
def backup(request: Request):
    administrator(request)
    return maintenance(request).create_backup(request.state.principal)


@router.get("/api/admin/backups/{backup_id}/file")
def backup_download(backup_id: str, request: Request):
    administrator(request)
    path = StorageManager(service(request).store.directory).backup_path(backup_id)
    return FileResponse(path, filename=path.name)


@router.post("/api/retention/plan")
def retention_plan(request: Request):
    return maintenance(request).retention_plan(request.state.principal)


class RetentionDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    plan_id: UUID
    expected_sha256: str = Field(pattern="^[0-9a-f]{64}$")
    confirmation: Literal["PERMANENTLY PURGE REVIEWED TRASH"]


@router.post("/api/retention/apply")
def retention_apply(payload: RetentionDecision, request: Request):
    return maintenance(request).apply_retention(
        str(payload.plan_id), payload.expected_sha256, request.state.principal, payload.confirmation
    )


@router.post("/api/investigations", status_code=202)
def investigate(payload: InvestigationRequest, request: Request):
    try:
        with CASE_LOCK:
            if payload.case_id:
                owned_case(request, str(payload.case_id))
            run = service(request).submit(
                payload.question,
                payload.limits,
                case_id=str(payload.case_id) if payload.case_id else None,
                use_mock_mcp=payload.use_mock_mcp,
                owner_id=request.state.principal.id,
                siemens=payload.siemens.model_dump() if payload.siemens else None,
                chat_mode=payload.chat_mode,
                use_library=payload.use_library,
                library_document_ids=[str(i) for i in payload.library_document_ids]
                if payload.library_document_ids is not None
                else None,
                machine_id=str(payload.machine_id) if payload.machine_id else None,
                machine_document_ids=[str(i) for i in payload.machine_document_ids]
                if payload.machine_document_ids is not None
                else None,
            )
            return run
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/api/investigations")
def investigations(
    request: Request,
    case_id: UUID | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=100000),
):
    if case_id:
        owned_case(request, str(case_id))
    rows = service(request).store.list(
        limit + 1,
        case_id=str(case_id) if case_id else None,
        offset=offset,
        owner_id=request.state.principal.id,
    )
    return {
        "investigations": rows[:limit],
        "next_offset": offset + limit if len(rows) > limit else None,
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


@router.get("/api/investigations/{run_id}/trace")
def trace(run_id: str, request: Request):
    from .tracing import export_trace

    return export_trace(service(request).store, run_id)


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


class SiemensQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=1, max_length=500, strict=True)
    family: str = Field(default="", max_length=20)
    cpu: str = Field(default="", max_length=50)
    firmware: str = Field(default="", max_length=12)
    tia_version: str = Field(default="", max_length=3)


@router.get("/api/integrations/siemens-mcp")
def siemens_catalog():
    from .siemens_mcp import catalog

    return catalog()


@router.post("/api/knowledge/siemens/search")
async def siemens_search(payload: SiemensQuestion):
    from .siemens_mcp import SiemensBusy, SiemensUnavailable, search
    from .siemens_reference import enrich, query_context

    try:
        outbound, context = query_context(**payload.model_dump())
        result = await search(outbound)
        return enrich(result, payload.question, outbound, context)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except SiemensBusy as exc:
        raise HTTPException(status_code=429, detail=str(exc), headers={"Retry-After": "2"}) from exc
    except SiemensUnavailable as exc:
        candidates = enrich({}, payload.question, outbound, context)
        if candidates["curated_references"]:
            return {
                **candidates,
                "connection_verified": False,
                "remote_search_status": "unavailable",
                "sources": [],
                "summary": "",
                "retrieved_at": None,
                "limitations": "Live Siemens MCP search is unavailable. The reviewed manual candidates below come from the local metadata index, not this remote search.",
            }
        raise HTTPException(status_code=503, detail=str(exc)) from exc


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
        proposal_id,
        payload.decision,
        payload.expected_sha256,
        actor=request.state.principal.public(),
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
        return evidence(request).create_case(payload.title, owner_id=request.state.principal.id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/api/cases")
def cases(
    request: Request,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=100000),
    deleted: bool = False,
):
    rows = evidence(request).cases(
        limit=limit + 1, offset=offset, owner_id=request.state.principal.id, deleted=deleted
    )
    return {"cases": rows[:limit], "next_offset": offset + limit if len(rows) > limit else None}


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


@router.post("/api/cases/{case_id}/verify-claims")
def verify_claims(case_id: str, payload: Claims, request: Request):
    store = evidence(request)
    return verify(store, case_id, store.snapshot(case_id), payload)


class ContinuationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    additional_tokens: int = Field(default=0, ge=0, le=65536, strict=True)


@router.post("/api/investigations/{run_id}/continue", status_code=202)
def continue_investigation(run_id: str, payload: ContinuationRequest, request: Request):
    return service(request).store.continue_tokens(run_id, payload.additional_tokens)


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
        next_auth = 0
        while not await request.is_disconnected():
            current = asyncio.get_running_loop().time()
            if current >= next_auth:
                try:
                    await asyncio.to_thread(
                        AuthStore(store.directory).authenticate, request.cookies.get(COOKIE)
                    )
                except AuthenticationError:
                    break
                next_auth = current + 1
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
            app.state.mutation_guard = asyncio.Lock()
            app.state.active_mutations = 0
            app.state.maintenance_active = False
            owner = local_owner(runner.store.directory)
            if owner:
                adopt_legacy(runner.store.directory, owner)
            from .knowledge import KnowledgeStore

            KnowledgeStore(runner.store.directory).seed()
            from .ingestion import IngestionService

            jobs = IngestionService(runner.store.directory).start()
            app.state.ingestion = jobs
            try:
                yield
            finally:
                jobs.close()

    app = FastAPI(title="Engineering Intelligence Lab", version="0.5.0", lifespan=lifespan)
    app.add_middleware(UploadBodyLimit)
    app.include_router(router)
    app.include_router(auth_router)
    app.include_router(library_router)
    app.include_router(machine_router)
    app.include_router(notebook_router)

    @app.middleware("http")
    async def local_browser_origin(request, call_next):
        origin = request.headers.get("origin")
        if (
            request.url.path.startswith("/api/")
            and origin
            and origin
            not in {
                str(request.base_url).rstrip("/"),
                "http://127.0.0.1:5173",
                "http://localhost:5173",
            }
        ):
            return JSONResponse(status_code=403, content={"detail": "Unapproved browser origin"})
        if (
            request.url.path.startswith("/api/")
            and request.headers.get("sec-fetch-site") == "cross-site"
        ):
            return JSONResponse(
                status_code=403, content={"detail": "Cross-site API request rejected"}
            )
        public = {
            "/api/health",
            "/api/auth/status",
            "/api/auth/login",
            "/api/auth/enroll",
            "/api/auth/logout",
        }
        if (
            request.url.path.startswith("/api/") and request.url.path not in public
        ) or request.url.path in {"/docs", "/redoc", "/openapi.json"}:
            try:
                auth = AuthStore(service(request).store.directory)
                request.state.principal = await asyncio.to_thread(
                    auth.authenticate, request.cookies.get(COOKIE)
                )
                parts = request.url.path.strip("/").split("/")
                if len(parts) >= 3 and parts[1] == "cases":
                    owned_case(request, parts[2], include_deleted=parts[-1] == "restore")
                elif len(parts) >= 3 and parts[1] == "investigations" and parts[2] != "demo-report":
                    run = service(request).store.get(parts[2])
                    if run.get("owner_id") != request.state.principal.id:
                        raise RunNotFound("Investigation not found")
                    if run.get("case_id"):
                        owned_case(request, run["case_id"])
                elif len(parts) >= 3 and parts[1] == "approvals":
                    proposal = DraftStore(service(request).store).get(parts[2])
                    owned_case(request, proposal["case_id"])
            except AuthenticationError as exc:
                with auth.connection() as conn:
                    auth.audit(conn, None, "authorization_denied", details={"status": 401})
                return JSONResponse(
                    status_code=401,
                    content={"detail": str(exc)},
                    headers={"Cache-Control": "no-store"},
                )
            except (EvidenceNotFound, RunNotFound) as exc:
                with auth.connection() as conn:
                    auth.audit(
                        conn,
                        request.state.principal.id,
                        "authorization_denied",
                        details={"status": 404},
                    )
                return JSONResponse(status_code=404, content={"detail": str(exc)})
        mutating = request.method in {
            "POST",
            "PUT",
            "PATCH",
            "DELETE",
        } and request.url.path.startswith("/api/")
        exclusive = request.url.path.endswith("/purge") or request.url.path in {
            "/api/admin/backups",
            "/api/retention/apply",
            "/api/admin/audit/archive",
        }
        if mutating:
            async with request.app.state.mutation_guard:
                if request.app.state.maintenance_active or (
                    exclusive and request.app.state.active_mutations
                ):
                    return JSONResponse(
                        status_code=409,
                        content={
                            "detail": "Another write or maintenance operation is active; retry shortly"
                        },
                    )
                if exclusive:
                    request.app.state.maintenance_active = True
                else:
                    request.app.state.active_mutations += 1
        try:
            response = await call_next(request)
        finally:
            if mutating:
                async with request.app.state.mutation_guard:
                    if exclusive:
                        request.app.state.maintenance_active = False
                    else:
                        request.app.state.active_mutations -= 1
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
            route = request.scope.get("route")
            if (
                mutating
                or request.url.path.endswith(("/export", "/file"))
                or response.status_code in {403, 404}
            ) and request.url.path not in public:
                auth = AuthStore(service(request).store.directory)
                with auth.connection() as conn:
                    auth.audit(
                        conn,
                        request.state.principal.id,
                        "authorization_denied"
                        if response.status_code in {403, 404}
                        else "request_completed",
                        next(
                            (
                                str(v)
                                for v in request.path_params.values()
                                if re.fullmatch(r"[0-9a-f]{8}-[0-9a-f-]{27}", str(v))
                            ),
                            None,
                        ),
                        details={
                            "method": request.method,
                            "route": getattr(route, "path", "unmatched"),
                            "status": response.status_code,
                        },
                    )
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

    @app.exception_handler(AuthenticationError)
    async def authentication_error(request, exc):
        return JSONResponse(
            status_code=429 if isinstance(exc, AuthenticationLimited) else 401,
            content={"detail": str(exc)},
            headers={"Cache-Control": "no-store"},
        )

    @app.exception_handler(StorageFull)
    async def storage_full(request, exc):
        return JSONResponse(status_code=507, content={"detail": str(exc)})

    # Host validation is outermost: reject rebinding before reading a body or
    # deriving any origin from request.base_url. Loopback binding alone is not
    # a browser security boundary.
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "[::1]"], www_redirect=False
    )
    return app


app = create_app()
