"""Export model text alongside independently resolved, scoped evidence and query history."""

import json
import re

from .claims import evidence_ledger
from .evidence import EvidenceNotFound, EvidenceStore
from .siemens_chat import reference_snapshot


def answer_citations(answer):
    """Expand only explicit same-source shorthand; never silently drop malformed references."""
    cited, malformed = set(), []
    try:
        structured = json.loads(answer)
    except (ValueError, TypeError):
        structured = None
    if isinstance(structured, dict) and isinstance(structured.get("citations"), list):
        for reference in structured["citations"][:32]:
            if isinstance(reference, str) and re.fullmatch(
                r"(?:pdf:[0-9a-f-]{36}:p[0-9]+:c[0-9]+|csv:[0-9a-f-]{36}:r[0-9]+)", reference
            ):
                cited.add(reference)
            else:
                malformed.append(str(reference)[:120])
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
    if not case_id and not run.get("chat_mode"):
        raise ValueError("Evidence export requires a case-backed investigation")
    store = EvidenceStore(run_store.directory)
    allowed = run["source_ids"] or []
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
                    if not hit["citation_id"].startswith("kb:"):
                        supplied.add(hit["citation_id"])
                        supplied.update(c["citation_id"] for c in hit.get("context", []))
                for station in observation.get("ranking", []):
                    supplied.update(station["example_citations"])
                if "citation_id" in observation:
                    supplied.add(observation["citation_id"])
    answer = (run.get("result") or {}).get("answer", "")
    from .answer_contract import assess

    answer_contract = assess(run, answer)
    cited, malformed = answer_citations(answer)
    siemens = reference_snapshot(run)
    public_cited = set(re.findall(r"\[(siemens:[^\]]+)\]", str(answer)))
    public_refs = [
        {**r, "cited_in_answer": r["citation_id"] in public_cited}
        for r in (siemens or {}).get("references", [])
    ]
    resolved, unknown = [], []
    from .knowledge import KnowledgeStore

    library_ids = run.get("library_document_ids", [])
    library_cited = set(re.findall(r"\[(kb:[^\]]+)\]", str(answer)))
    library_supplied = {h["citation_id"] for h in (run.get("library_lookup") or {}).get("hits", [])}
    library_resolved, library_unknown = [], []
    if library_ids:
        library = KnowledgeStore(run_store.directory)
        for cid in sorted(library_cited | library_supplied):
            try:
                ref = library.resolve(cid, library_ids)
                library_resolved.append(
                    ref
                    | {
                        "cited_in_answer": cid in library_cited,
                        "returned_by_tool": cid in library_supplied,
                    }
                )
            except EvidenceNotFound:
                library_unknown.append(cid)
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
        "verified_evidence": evidence_ledger(store, case_id, allowed)
        if case_id
        else {"comparisons": [], "conflicting_csv_measurements": [], "incomplete_sources": []},
        "run_id": run_id,
        "case_id": case_id,
        "status": run["status"],
        "integrations": {
            "siemens": siemens,
            "mock_mcp": {
                "enabled": run.get("use_mock_mcp", False),
                "server_id": "eil-synthetic-maintenance-v1",
                "transport": "in-process-memory",
            },
        },
        "answer": answer,
        "answer_contract": answer_contract,
        "library_snapshot": [
            {
                k: v
                for k, v in KnowledgeStore(run_store.directory)
                .document(identity, include_inactive=True)
                .items()
                if k not in {"raw", "active"}
            }
            for identity in library_ids
        ],
        "library_citations": library_resolved,
        "library_retrieval": {
            k: v for k, v in (run.get("library_lookup") or {}).items() if k != "hits"
        },
        "library_citation_checks": {
            "unresolved": sorted(
                set(library_unknown)
                | (library_cited - {r["citation_id"] for r in library_resolved})
            ),
            "not_returned_by_tools": sorted(library_cited - library_supplied),
            "claim_entailment": "not_verified",
        },
        "external_references": public_refs,
        "external_reference_checks": {
            "unresolved": sorted(public_cited - {r["citation_id"] for r in public_refs}),
            "technical_claims_verified": False,
        },
        "error": run["error"],
        "source_snapshot": store.sources(case_id, allowed) if case_id else [],
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
