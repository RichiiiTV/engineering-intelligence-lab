"""Deterministic citation/quotation contract, distinct from general claim entailment."""

import re


def assess(run, answer):
    answer = str(answer)
    if run.get("budget_summary"):
        return {"outcome": "budget_limited", "issues": [], "claim_entailment": "not_verified"}
    lookup = run.get("library_lookup")
    if not run.get("use_library") and not run.get("machine_id"):
        return {"outcome": "references_unchecked", "issues": [], "claim_entailment": "not_verified"}
    hits = (lookup or {}).get("hits", []) + ((run.get("machine_lookup") or {}).get("hits", []))
    observed = {h["citation_id"]: h for h in hits}
    cited = set(re.findall(r"\[(kb:[^\]]+)\]", answer))
    issues = []
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
