"""Trusted deterministic fixture generation; no model or external data."""

import csv
import hashlib
import io
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = root / "data/benchmarks/eil-v1"
destination = root / "data/benchmarks/eil-v2"
destination.mkdir(exist_ok=True)
cases = {}
for key in ("other-station", "no-increase", "conflicting-records", "missing-document"):
    rows = list(csv.DictReader(io.StringIO((source / "known-cause.csv").read_text())))
    if key in {"other-station", "no-increase"}:
        for row in rows:
            row["false_ejects"] = (
                "1800"
                if key == "other-station"
                and row["station_id"] == "S02"
                and row["period"] == "incident"
                else "100"
            )
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    content = stream.getvalue().encode()
    (destination / (key + ".csv")).write_bytes(content)
    cases[key] = {
        "csv_sha256": hashlib.sha256(content).hexdigest(),
        "pdf_records": []
        if key == "missing-document"
        else ["known-cause", "ambiguous"]
        if key == "conflicting-records"
        else ["known-cause"],
        "expected": {
            "station_id": "S02"
            if key == "other-station"
            else "S01"
            if key == "no-increase"
            else "S03",
            "baseline_rate": 0.01,
            "incident_rate": 0.18
            if key == "other-station"
            else 0.01
            if key == "no-increase"
            else 0.14,
            "delta_pp": 17 if key == "other-station" else 0 if key == "no-increase" else 13,
            "cause": "undetermined",
            "cause_status": "unresolved",
        },
    }
(destination / "manifest.json").write_text(
    json.dumps(
        {
            "version": "eil-benchmark-v2",
            "license": "Generated EIL demo data; PDFs reuse hash-verified v1 generated records with their actual cached Docling normalization.",
            "cases": cases,
        },
        indent=2,
    )
    + "\n"
)
