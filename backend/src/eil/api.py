"""Local read-only analytics and durable, bounded investigation jobs."""

from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import APIRouter, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .analytics import ALLOWED_STATIONS, compare_stations, provisional_report, station_metrics
from .runs import STOPPED, QueueFull, RunConflict, RunLimits, RunNotFound
from .service import RunService
from .settings import DATASET_NAME

router = APIRouter()


class InvestigationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=1, max_length=4000)
    limits: RunLimits = Field(default_factory=RunLimits)

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
        return service(request).submit(payload.question, payload.limits)
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/api/investigations")
def investigations(request: Request):
    return {"investigations": service(request).store.list()}


@router.get("/api/investigations/{run_id}")
def investigation(run_id: str, request: Request):
    return service(request).store.get(run_id)


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

    app = FastAPI(title="Engineering Intelligence Lab", version="0.2.0", lifespan=lifespan)
    app.include_router(router)

    @app.exception_handler(RunNotFound)
    async def missing(request, exc):
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(RunConflict)
    async def conflict(request, exc):
        return JSONResponse(
            status_code=429 if isinstance(exc, QueueFull) else 409, content={"detail": str(exc)}
        )

    return app


app = create_app()
