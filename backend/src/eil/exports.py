"""Export model text alongside independently resolved, scoped evidence and query history."""

import json
import re

from .evidence import EvidenceNotFound, EvidenceStore


def answer_citations(answer):
    """Expand only explicit same-source shorthand; never silently drop malformed references."""
    cited, malformed = set(), []
    for body in re.findall(r"\[((?:pdf|csv):[^\]]*)\]", str(answer)):
        first, *rest = [part.strip() for part in body.split(",")]
        if not re.fullmatch(
            r"(?:pdf:[0-9a-f-]{36}:p[0-9]+:c[0-9]+|csv:[0-9a-f-]{36}:r[0-9]+)", first
        ):
            malformed.append(body)
            continue
        cited.add(first)
        for part in rest:
            if re.fullmatch(
                r"(?:pdf:[0-9a-f-]{36}:p[0-9]+:c[0-9]+|csv:[0-9a-f-]{36}:r[0-9]+)", part
            ):
                cited.add(part)
            elif first.startswith("csv:") and re.fullmatch(r"r[0-9]+", part):
                cited.add(first.rsplit(":", 1)[0] + ":" + part)
            elif first.startswith("pdf:") and re.fullmatch(r"c[0-9]+", part):
                cited.add(first.rsplit(":", 1)[0] + ":" + part)
            elif first.startswith("pdf:") and re.fullmatch(r"p[0-9]+:c[0-9]+", part):
                cited.add(":".join(first.split(":")[:2]) + ":" + part)
            else:
                malformed.append(body)
    return cited, sorted(set(malformed))


def export_investigation(run_store, run_id):
    run = run_store.get(run_id)
    case_id = run.get("case_id")
    if not case_id:
        raise ValueError("Evidence export requires a case-backed investigation")
    store = EvidenceStore(run_store.directory)
    allowed = run["source_ids"]
    observations, queries, supplied = [], [], set()
    cursor = 0
    while batch := run_store.events(run_id, cursor):
        for event in batch:
            cursor = event["id"]
            if event["type"] == "tool_requested":
                queries.append({"event_id": event["id"], "phase": "requested", **event["data"]})
            if event["type"] == "tool_finished":
                observations.append({"event_id": event["id"], **event["data"]})
                try:
                    observation = json.loads(event["data"]["observation"])
                except (ValueError, KeyError, TypeError):
                    continue
                if not isinstance(observation, dict):
                    continue
                if "method" in observation or "query_provenance" in observation:
                    queries.append(
                        {
                            "event_id": event["id"],
                            "phase": "observed",
                            "name": event["data"]["name"],
                            "definition": observation.get("query_provenance")
                            or {
                                k: observation.get(k)
                                for k in ("method", "query", "terms", "limit", "source_ids")
                            },
                        }
                    )
                for hit in observation.get("hits", []):
                    supplied.add(hit["citation_id"])
                for station in observation.get("ranking", []):
                    supplied.update(station["example_citations"])
                if "citation_id" in observation:
                    supplied.add(observation["citation_id"])
    answer = (run.get("result") or {}).get("answer", "")
    cited, malformed = answer_citations(answer)
    resolved, unknown = [], []
    for cid in sorted(cited | supplied):
        try:
            citation = store.resolve(case_id, cid, allowed)
        except EvidenceNotFound:
            unknown.append(cid)
        else:
            resolved.append(
                {**citation, "cited_in_answer": cid in cited, "returned_by_tool": cid in supplied}
            )
    return {
        "schema": "eil-evidence-report-v1",
        "run_id": run_id,
        "case_id": case_id,
        "status": run["status"],
        "integrations": {
            "mock_mcp": {
                "enabled": run.get("use_mock_mcp", False),
                "server_id": "eil-synthetic-maintenance-v1",
                "transport": "in-process-memory",
            }
        },
        "answer": answer,
        "error": run["error"],
        "source_snapshot": store.sources(case_id, allowed),
        "citations": resolved,
        "query_provenance": queries,
        "tool_observations": observations,
        "citation_checks": {
            "unresolved": unknown,
            "not_returned_by_tools": sorted(cited - supplied),
            "malformed": malformed,
            "answer_citation_count": len(cited),
            "has_answer_citations": bool(cited),
        },
        "uncertainty": {
            "causation": "not_established",
            "statistical_confidence": "not_estimated",
            "claim_entailment": "not_verified",
            "limitations": [
                "Citation resolution checks location and source identity, not whether a claim follows.",
                "Lexical scores are relevance scores, not calibrated probabilities.",
                "CSV example rows are not the full aggregation; source hashes and query definitions identify its inputs.",
                "PDF extraction can lose layout; OCR is disabled; absence from search is not evidence of absence.",
            ],
        },
    }
