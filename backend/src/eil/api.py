"""Read-only local prototype API. Agent endpoint is experimental."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator

from .analytics import ALLOWED_STATIONS, compare_stations, provisional_report, station_metrics
from .settings import DATASET_NAME

app = FastAPI(title="Engineering Intelligence Lab", version="0.1.0")


class InvestigationRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)

    @field_validator("question")
    @classmethod
    def reject_blank_question(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Question must contain non-whitespace characters")
        return value


@app.get("/api/health")
def health():
    return {"status": "ok", "mode": "synthetic-read-only"}


@app.get("/api/datasets")
def datasets():
    return {"datasets": [{"id": DATASET_NAME, "type": "synthetic-inspection-csv"}]}


@app.get("/api/metrics/summary")
def summary():
    return {"ranked_stations": compare_stations()}


@app.get("/api/metrics/stations/{station_id}")
def station(station_id: str):
    if station_id not in ALLOWED_STATIONS:
        raise HTTPException(status_code=404, detail="Unknown station")
    return {
        "baseline": station_metrics(station_id, "baseline"),
        "incident": station_metrics(station_id, "incident"),
    }


@app.get("/api/investigations/demo-report")
def demo_report():
    return provisional_report()


@app.post("/api/investigations")
def investigate(payload: InvestigationRequest):
    from .agent import ModelUnavailableError, run_agent

    try:
        return run_agent(payload.question)
    except ModelUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
