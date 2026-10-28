"""Deterministic, read-only metrics over a generated synthetic dataset."""

from __future__ import annotations

from csv import DictReader
from pathlib import Path

from .settings import DATA_DIR, DATASET_NAME

ALLOWED_STATIONS = frozenset({"S01", "S02", "S03", "S04"})
ALLOWED_PERIODS = frozenset({"baseline", "incident"})
EXPECTED_COLUMNS = frozenset(
    {
        "row_id",
        "timestamp",
        "station_id",
        "period",
        "inspected",
        "false_ejects",
        "true_rejects",
        "illumination_lux",
        "exposure_us",
    }
)


def load_rows(path: Path | None = None) -> list[dict]:
    """Read the single allowlisted fixture; callers cannot supply arbitrary files."""
    allowed = (DATA_DIR / DATASET_NAME).resolve()
    source = path.resolve() if path is not None else allowed
    if (
        Path(DATASET_NAME).name != DATASET_NAME
        or allowed.parent != DATA_DIR.resolve()
        or source != allowed
    ):
        raise ValueError("Dataset path is not allowlisted")
    if not source.is_file():
        raise FileNotFoundError(source)
    rows = []
    with source.open("r", newline="", encoding="utf-8") as handle:
        reader = DictReader(handle)
        if not EXPECTED_COLUMNS.issubset(set(reader.fieldnames or [])):
            raise ValueError("Dataset schema mismatch")
        for raw in reader:
            if raw["station_id"] not in ALLOWED_STATIONS or raw["period"] not in ALLOWED_PERIODS:
                raise ValueError("Invalid station or period")
            entry = {k: raw[k] for k in ("row_id", "timestamp", "station_id", "period")}
            for key in (
                "inspected",
                "false_ejects",
                "true_rejects",
                "illumination_lux",
                "exposure_us",
            ):
                entry[key] = int(raw[key])
            if entry["inspected"] <= 0 or min(entry["false_ejects"], entry["true_rejects"]) < 0:
                raise ValueError("Invalid counts")
            if entry["false_ejects"] + entry["true_rejects"] > entry["inspected"]:
                raise ValueError("Rejected count exceeds inspected count")
            rows.append(entry)
    if not rows:
        raise ValueError("Dataset is empty")
    return rows


def station_metrics(station_id: str, period: str, rows: list[dict] | None = None) -> dict:
    if station_id not in ALLOWED_STATIONS:
        raise ValueError(f"Unknown station {station_id!r}")
    if period not in ALLOWED_PERIODS:
        raise ValueError(f"Unknown period {period!r}")
    selected = [
        row
        for row in (rows if rows is not None else load_rows())
        if row["station_id"] == station_id and row["period"] == period
    ]
    if not selected:
        raise ValueError("No matching observations")
    inspected = sum(row["inspected"] for row in selected)
    false_ejects = sum(row["false_ejects"] for row in selected)
    true_rejects = sum(row["true_rejects"] for row in selected)
    return {
        "station_id": station_id,
        "period": period,
        "inspected": inspected,
        "false_ejects": false_ejects,
        "true_rejects": true_rejects,
        "false_eject_rate": round(false_ejects / inspected, 6),
        "mean_illumination_lux": round(
            sum(r["illumination_lux"] for r in selected) / len(selected), 2
        ),
        "mean_exposure_us": round(sum(r["exposure_us"] for r in selected) / len(selected), 2),
        "source_rows": [r["row_id"] for r in selected],
        "metric_definition": "false_ejects / inspected (synthetic ground-truth labels)",
    }


def compare_stations(rows: list[dict] | None = None) -> list[dict]:
    """Rank stations by absolute percentage-point increase; not causal attribution."""
    data = rows if rows is not None else load_rows()
    comparisons = []
    for station in sorted(ALLOWED_STATIONS):
        before = station_metrics(station, "baseline", data)
        after = station_metrics(station, "incident", data)
        comparisons.append(
            {
                "station_id": station,
                "baseline_false_eject_rate": before["false_eject_rate"],
                "incident_false_eject_rate": after["false_eject_rate"],
                "delta_percentage_points": round(
                    100 * (after["false_eject_rate"] - before["false_eject_rate"]), 4
                ),
                "illumination_delta_lux": round(
                    after["mean_illumination_lux"] - before["mean_illumination_lux"], 2
                ),
                "exposure_delta_us": round(
                    after["mean_exposure_us"] - before["mean_exposure_us"], 2
                ),
                "baseline_source_rows": before["source_rows"],
                "incident_source_rows": after["source_rows"],
            }
        )
    return sorted(comparisons, key=lambda x: x["delta_percentage_points"], reverse=True)


def provisional_report() -> dict:
    comparisons = compare_stations()
    top = comparisons[0]
    return {
        "type": "deterministic_demo_report",
        "dataset": DATASET_NAME,
        "finding": f"{top['station_id']} had the largest increase in false-ejection rate.",
        "hypotheses": [
            "A concurrent illumination/exposure change might be relevant; investigate, do not assume causality."
        ],
        "uncertainty": "Data are synthetic. Concurrent changes do not establish a root cause.",
        "ranking": comparisons,
    }
