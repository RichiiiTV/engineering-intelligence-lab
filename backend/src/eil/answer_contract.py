"""Deterministic citation/quotation contract, distinct from general claim entailment."""

import re


def normalize_citations(run, answer):
    """Normalize only exact, observed local citation links; unknown URLs stay inert."""
    hits = []
    for key in ("catalog_lookup", "library_lookup", "machine_lookup"):
        hits.extend((run.get(key) or {}).get("hits", []))
    for key in ("catalog_source_reads", "machine_source_reads", "problem_source_reads"):
        hits.extend(run.get(key, []))
    known = {h["citation_id"] for h in hits} | set(run.get("problem_images_supplied", []))
    return "".join(
        part
        if part.startswith("`")
        else re.sub(
            r"\[([^\]\n]{1,240})\]\(((?:kb|log|image):[^\s()]+)\)",
            lambda match: match[1] + " [" + match[2] + "]" if match[2] in known else match[0],
            part,
        )
        for part in re.split(r"(```[\s\S]*?(?:```|$)|`[^`\n]*`)", answer)
    )


def assess(run, answer):
    answer = normalize_citations(run, str(answer))
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
    affirmative = re.sub(
        r"[^.!?\n]*(?:does not establish|does not support|cannot determine|cannot confirm|cannot verify|can't determine|not documented|not verified|\bwhether\b|\b(?:might|could|may)\s+(?:be|require|use)\b|\bkönnte\b|\bunklar\b|\bunbekannt\b|nicht.{0,30}(?:belegt|bestimmt|bestätigt|dokumentiert)|keine.{0,30}(?:Angaben|Belege|Information))[^.!?\n]*",
        "",
        answer,
        flags=re.I,
    )
    technical = re.findall(
        r"\b(?:STM32[0-9A-Z]+|ATmega[0-9A-Z]+|RP2040|ESP32(?:-[0-9A-Z]+)?|\d+(?:[.,]\d+)?\s*(?:KiB|MiB|GiB))\b",
        affirmative,
        re.I,
    )
    cited_text = " ".join(h.get("text", "") for h in hits if h["citation_id"] in cited)

    def literal(value):
        return re.sub(r"[\s_-]+", "", value.casefold())

    if cited and any(literal(value) not in literal(cited_text) for value in technical):
        issues.append(
            "Some technical identifiers or memory sizes are absent from the cited passages."
        )
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
    text = " ".join(h.get("text", "") for h in hits)
    critical = set(
        re.findall(
            r"\b(?:safety[- ](?:alarm|rated|interlock|circuit|function)|interlock|emergency[- ]stop|SIL\s*[1-4]|sicherheits(?:funktion|kreis|verriegelung|alarm)|sicherheitsgerichtet\w*|not[- ]?halt|not[- ]?aus|türverriegelung)\b",
            answer,
            re.I,
        )
    )
    source_terms = re.sub(r"[\s_-]+", " ", text.casefold())
    human_and_source = str(run.get("question", "")) + " " + text
    vendor_text = re.sub(
        r"\b(?:does not|do not|cannot|doesn't|don't)\s+(?:suggest|indicate|identify|establish)\b[^.\n]{0,40}\bsiemens\b|\b(?:no|without|keine?\w*|ohne)\s+siemens\s+(?:PLC|SPS|controller|Steuerung)\b|\b(?:keine?|nicht)\b[^.\n]{0,35}\bsiemens\b",
        "",
        answer,
        flags=re.I,
    )
    if not re.search(r"\bsiemens\b", human_and_source, re.I) and re.search(
        r"\bsiemens\s+(?:PLC|SPS|controller|Steuerung)|\b(?:PLC|SPS|controller|Steuerung)\s+(?:from|von)\s+siemens|\b(?:indicates?|suggests?)\b[^.\n]{0,40}\bsiemens\b",
        vendor_text,
        re.I,
    ):
        issues.append(
            "Vendor identification is not established by the human question or source text; citation IDs are opaque."
        )
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
