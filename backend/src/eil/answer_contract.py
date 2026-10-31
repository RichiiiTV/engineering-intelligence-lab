"""Deterministic citation/quotation contract, distinct from general claim entailment."""

import re


def assess(run, answer):
    answer = str(answer)
    if run.get("budget_summary"):
        return {"outcome": "budget_limited", "issues": [], "claim_entailment": "not_verified"}
    if not answer.strip() and run.get("status") not in {None, "queued", "running", "completed"}:
        return {"outcome": "not_completed", "issues": [], "claim_entailment": "not_verified"}
    if (
        run.get("automatic_catalog")
        and (run.get("catalog_lookup") or {}).get("status") == "needs_clarification"
    ):
        return {
            "outcome": "clarification_required",
            "issues": [],
            "claim_entailment": "not_verified",
        }
    lookup = run.get("library_lookup")
    if (run.get("catalog_lookup") or {}).get("status") == "public_reference" and not run.get(
        "problem_attachment_ids"
    ):
        return {"outcome": "public_references", "issues": [], "claim_entailment": "not_verified"}
    if (
        not run.get("use_library")
        and not run.get("machine_id")
        and not run.get("automatic_catalog")
    ):
        return {"outcome": "references_unchecked", "issues": [], "claim_entailment": "not_verified"}
    hits = (
        (lookup or {}).get("hits", [])
        + ((run.get("machine_lookup") or {}).get("hits", []))
        + run.get("machine_source_reads", [])
        + (run.get("catalog_lookup") or {}).get("hits", [])
        + run.get("catalog_source_reads", [])
        + run.get("problem_source_reads", [])
        + [
            {
                "citation_id": cid,
                "text": (run.get("problem_visual_observations", {}).get(cid) or {}).get(
                    "visible_text", ""
                ),
            }
            for cid in run.get("problem_images_supplied", [])
        ]
    )
    observed = {h["citation_id"]: h for h in hits}
    cited = set(re.findall(r"\[((?:kb|log|image):[^\]]+)\]", answer))
    issues = []
    if run.get("automatic_catalog") and run.get("catalog_lookup") is None:
        issues.append("Automatic machine knowledge retrieval was not completed.")
    if run.get("problem_has_logs") and not run.get("problem_lookup_done"):
        issues.append("The provided error logs were not read.")
    if run.get("attachment_notice"):
        issues.append(run["attachment_notice"])
    if (lookup is None and run.get("use_library")) or (
        run.get("machine_id") and run.get("machine_lookup") is None
    ):
        issues.append("Selected sources were not retrieved.")
    if cited - set(observed):
        issues.append("Some references were not returned by the source tools.")
    abstains = bool(
        re.search(
            r"does not establish|cannot (?:answer|determine)|not (?:found|contain|available)|insufficient|no supporting|keine|nicht belegt",
            answer,
            re.I,
        )
    )
    if not cited and hits and not abstains:
        issues.append("The answer has no observed source citations.")
    quotes = re.findall(r"^>\s*(.+)$", answer, re.M)
    text = " ".join(h.get("text", "") for h in observed.values())
    critical = set(
        re.findall(
            r"\b(?:safety[- ](?:alarm|rated|interlock|circuit|function)|interlock|emergency[- ]stop|SIL\s*[1-4])\b",
            answer,
            re.I,
        )
    )
    source_terms = re.sub(r"[\s_-]+", " ", text.casefold())
    if any(re.sub(r"[\s_-]+", " ", term.casefold()) not in source_terms for term in critical):
        issues.append(
            "Safety classification or interlock role is not established by the retrieved sources."
        )

    def normalize(s):
        return " ".join(s.split()).casefold()

    for quote in quotes:
        quote = re.sub(r"\[[^\]]+\]", "", quote).strip()
        if len(quote) >= 20 and normalize(quote) not in normalize(text):
            issues.append("An evidence quotation does not match an observed passage.")
    outcome = (
        "needs_review" if issues else "no_support" if not hits or abstains else "references_checked"
    )
    return {
        "outcome": outcome,
        "issues": issues,
        "observed_citation_count": len(cited & set(observed)),
        "checked_block_quotes": len(quotes),
        "claim_entailment": "not_verified",
    }
