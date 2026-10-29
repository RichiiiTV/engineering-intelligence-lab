"""Deterministic verification of explicit metrics and exact quotations, not a prose judge."""

import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .evidence import EvidenceNotFound


class MetricClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_id: str = Field(max_length=36)
    station_id: Literal["S01", "S02", "S03", "S04"]
    baseline_rate: float = Field(ge=0, le=1, allow_inf_nan=False)
    incident_rate: float = Field(ge=0, le=1, allow_inf_nan=False)
    delta_pp: float = Field(ge=-100, le=100, allow_inf_nan=False)


class QuoteClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")
    citation_id: str = Field(max_length=100)
    quotation: str = Field(min_length=8, max_length=1200)


class Claims(BaseModel):
    model_config = ConfigDict(extra="forbid")
    metrics: list[MetricClaim] = Field(default_factory=list, max_length=16)
    quotations: list[QuoteClaim] = Field(default_factory=list, max_length=16)


def verify(store, case_id, source_ids, claims):
    metrics, quotations = [], []
    for claim in claims.metrics:
        expected = None
        try:
            comparison = store.compare(case_id, claim.source_id, source_ids)
            expected = next(
                (r for r in comparison["ranking"] if r["station_id"] == claim.station_id), None
            )
        except (EvidenceNotFound, ValueError):
            pass
        matches = bool(expected) and all(
            abs(getattr(claim, key) - expected[field]) <= tolerance
            for key, field, tolerance in (
                ("baseline_rate", "baseline_rate", 1e-6),
                ("incident_rate", "incident_rate", 1e-6),
                ("delta_pp", "delta_percentage_points", 1e-4),
            )
        )
        metrics.append(
            {
                "claim": claim.model_dump(),
                "verified": matches,
                "expected": expected,
                "reason": "Recomputed from this immutable CSV snapshot"
                if matches
                else "Claim does not match the selected CSV/station or its source is unavailable",
            }
        )
    for claim in claims.quotations:
        try:
            citation = store.resolve(case_id, claim.citation_id, source_ids)
            matches = claim.quotation in citation.get("text", "")
        except EvidenceNotFound:
            matches = False
        quotations.append(
            {
                "claim": claim.model_dump(),
                "verified": matches,
                "reason": "Exact quotation exists at this citation"
                if matches
                else "Quotation is absent or citation is outside this snapshot",
            }
        )
    return {
        "schema": "eil-claim-checks-v1",
        "metrics": metrics,
        "quotations": quotations,
        "all_submitted_claims_verified": bool(metrics or quotations)
        and all(r["verified"] for r in metrics + quotations),
        "prose_entailment": "not_verified",
        "causation": "not_established",
        "limitations": "Checks apply only to the submitted typed claims. A quotation proves what the document says, not that it is true. Conflicting datasets remain separate; hypotheses, causation and other prose remain unverified.",
    }


def evidence_ledger(store, case_id, allowed):
    """Recompute all bounded case CSVs and expose disagreements without choosing a winner."""
    comparisons, incomplete, by_station = [], [], {}
    for source in store.sources(case_id, allowed):
        if source["kind"] != "csv":
            continue
        try:
            comparison = store.compare(case_id, source["id"], allowed)
        except ValueError:
            incomplete.append(source["id"])
            continue
        comparisons.append(comparison)
        for row in comparison["ranking"]:
            by_station.setdefault(row["station_id"], []).append({"source_id": source["id"], **row})
    conflicts = [
        {"station_id": station, "observations": rows}
        for station, rows in by_station.items()
        if len({(r["baseline_rate"], r["incident_rate"]) for r in rows}) > 1
    ]
    return {
        "comparisons": comparisons,
        "conflicting_csv_measurements": conflicts,
        "incomplete_sources": incomplete,
        "interpretation": "Different CSV measurements are a potential conflict until their scope/time is reconciled. They are never silently merged. No general document contradiction detector is claimed.",
    }


def check_closed_finding(run_store, run_id, finding):
    """Validate the benchmark's closed station/replay contract using observed evidence.

    No fixture key, expected-answer manifest, or ground-truth file is consulted.
    General prose and arbitrary document causality remain outside this checker.
    """
    supplied, comparisons, paragraphs = set(), [], {}
    cursor = 0
    while batch := run_store.events(run_id, cursor):
        for event in batch:
            cursor = event["id"]
            if event["type"] != "tool_finished":
                continue
            try:
                value = json.loads(event["data"].get("observation", ""))
            except (ValueError, TypeError):
                continue
            if not isinstance(value, dict):
                continue
            if "ranking" in value:
                comparisons.append(value)
                for row in value["ranking"]:
                    supplied.update(row["example_citations"])
            for hit in value.get("hits", []):
                for item in [hit, *hit.get("context", [])]:
                    supplied.add(item["citation_id"])
                    paragraphs.setdefault(item["source_id"], {})[item["citation_id"]] = item.get(
                        "text", ""
                    )
            if "citation_id" in value:
                supplied.add(value["citation_id"])
                paragraphs.setdefault(value["source_id"], {})[value["citation_id"]] = value.get(
                    "text", ""
                )
    if not comparisons:
        return ["No CSV comparison was observed."]
    row = comparisons[0]["ranking"][0]
    errors = []
    if finding["station_id"] != row["station_id"] or any(
        abs(finding[key] - row[field]) > tolerance
        for key, field, tolerance in [
            ("baseline_rate", "baseline_rate", 1e-6),
            ("incident_rate", "incident_rate", 1e-6),
            ("delta_pp", "delta_percentage_points", 1e-4),
        ]
    ):
        errors.append(
            "CSV comparison says "
            + str(
                {
                    k: row[k]
                    for k in (
                        "station_id",
                        "baseline_rate",
                        "incident_rate",
                        "delta_percentage_points",
                    )
                }
            )
            + ". Use this aggregation, rather than numeric claims in a PDF."
        )
    if not set(finding["citations"]) <= supplied:
        errors.append("Some citations were not returned by tools. Use full returned IDs.")
    if not set(row["example_citations"]) <= set(finding["citations"]):
        errors.append(
            "Include the selected station CSV baseline and incident references: "
            + str(row["example_citations"])
        )
    for source_id, values in paragraphs.items():
        candidates = [cid for cid in values if cid.startswith("pdf:") and ":p2:" in cid]
        if candidates and not set(candidates).intersection(finding["citations"]):
            errors.append(
                "Include a returned page-2 reference for each inspected PDF, including records that do not explain the selected station: "
                + str(candidates)
            )
    positive, negative = False, False
    for values in paragraphs.values():
        text = " ".join(values.values()).lower()
        if (
            row["station_id"].lower() in text
            and "controlled-replay" in text
            and "supports illumination as the cause within this simulator" in text
        ):
            positive = True
        if "cause is unresolved" in text or "competing hypotheses" in text:
            negative = True
    supported = positive and not negative and row["delta_percentage_points"] > 0
    expected = (
        ("illumination", "supported_in_simulator") if supported else ("undetermined", "unresolved")
    )
    if (finding["cause"], finding["cause_status"]) != expected:
        errors.append(
            "Observed replay evidence "
            + (
                "explicitly supports illumination for this station only within the simulator."
                if supported
                else "does not consistently establish a controlled illumination effect for the selected station; abstain with undetermined/unresolved."
            )
        )
    return errors
