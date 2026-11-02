"""No-inference previews of already persisted evidence after a bounded stop.

No model, tool, retrieval, file read or external request is made here. A preview
does not complete an investigation or turn a failed evaluation into a pass.
"""

import json
import re

from .answer_contract import observations


def literal_excerpt(text):
    # Keep source markup inert, including fake citation/link instructions.
    text = re.sub(r"\[(?:kb|log|image|pdf|csv|siemens):[^\]\n]*\]", "", text)
    return "\n".join(
        "> " + re.sub(r"([\\`*_{}\[\]<>#!])", r"\\\1", line) for line in text[:900].splitlines()
    )


def partial_result(run, tool_events=()):
    """Select up to three literal excerpts within the frozen source scope."""
    documents = set(run.get("library_document_ids", [])) | set(run.get("machine_document_ids", []))
    selected = ((run.get("catalog_lookup") or {}).get("machine") or {}).get("id")
    for machine in run.get("catalog_snapshot", []):
        if machine["id"] == selected:
            documents.update(machine["document_ids"])
    scopes = {
        "kb": documents,
        "log": set(run.get("problem_attachment_ids", [])),
        "pdf": set(run.get("source_ids") or []),
        "csv": set(run.get("source_ids") or []),
    }
    hits = list(observations(run))
    # Only successful closed case tools: never delegated/model prose or errors.
    for event in tool_events:
        if event.get("status") != "success" or event.get("name") not in {
            "search_case_documents",
            "read_case_citation",
        }:
            continue
        try:
            value = json.loads(event.get("observation", ""))
        except (ValueError, TypeError):
            continue
        if not isinstance(value, dict) or value.get("error"):
            continue
        hits.extend(value.get("hits", []))
        if "citation_id" in value:
            hits.append(value | {"text": value.get("text") or json.dumps(value.get("row", {}))})
    terms = set(re.findall(r"\w{3,}", run["question"].lower()))
    candidates = {}
    for hit in hits:
        cid, text = hit.get("citation_id", ""), hit.get("text", "")
        parts = cid.split(":")
        if (
            len(parts) < 3
            or parts[1] not in scopes.get(parts[0], set())
            or not re.fullmatch(r"[\w:.-]+", cid)
            or not isinstance(text, str)
            or not text.strip()
        ):
            continue
        candidates.setdefault(cid, text)
    ranked = sorted(
        candidates,
        key=lambda cid: -len(terms & set(re.findall(r"\w{3,}", candidates[cid].lower()))),
    )[:3]
    de = run.get("language") == "de"
    output = [
        "Teilweise Belegprüfung: Die Untersuchung wurde an einer Kapazitätsgrenze gestoppt. Sie ist nicht abgeschlossen. Die folgenden Originalauszüge wurden bereits abgerufen; sie sind keine bestätigte Diagnose. Weitere Belege und Prüfungen können fehlen."
        if de
        else "Partial evidence review: the investigation stopped at a capacity limit and is incomplete. The original excerpts below were already retrieved; they are not a verified diagnosis. Evidence and checks may still be missing."
    ]
    for cid in ranked:
        output.append(literal_excerpt(candidates[cid]) + "\n\n[" + cid + "]")
    if not ranked:
        output.append(
            "Es liegen noch keine geeigneten Textbelege für eine Vorschau vor. Aus diesem Stopp lässt sich keine Ursache ableiten."
            if de
            else "No suitable text evidence is available for a preview yet. This stop does not establish a cause."
        )
    return {
        "answer": "\n\n".join(output),
        "answer_mode": "budget_source_extract",
        "capacity_limited": True,
        "answer_contract": {
            "outcome": "budget_limited",
            "issues": [],
            "claim_entailment": "not_verified",
        },
        "preview_citation_ids": ranked,
        "warning": "Incomplete evidence preview, not a completed model answer or diagnosis.",
    }
