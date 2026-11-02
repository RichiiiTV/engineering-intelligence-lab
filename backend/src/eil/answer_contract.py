"""Deterministic citation/quotation contract, distinct from general claim entailment."""

import json
import re


def observations(run):
    hits = []
    for key in ("catalog_lookup", "library_lookup", "machine_lookup"):
        hits.extend((run.get(key) or {}).get("hits", []))
    for key in ("catalog_source_reads", "machine_source_reads", "problem_source_reads"):
        hits.extend(run.get(key, []))
    return hits


def source_document_id(run, value):
    """Accept an exact observed citation as a source selector, never parse a guessed one.

    The caller must still apply its frozen source/owner authorization afterwards.
    """
    for hit in observations(run):
        if value == hit["citation_id"]:
            return hit.get("id", value)
    return value


def technical_values(text):
    affirmative = re.sub(
        r"[^.!?\n]*(?:does not establish|does not support|cannot determine|cannot confirm|cannot verify|can't determine|not documented|not verified|\bwhether\b|\b(?:might|could|may)\s+(?:be|require|use)\b|\bkönnte\b|\bunklar\b|\bunbekannt\b|nicht.{0,30}(?:belegt|bestimmt|bestätigt|dokumentiert)|keine.{0,30}(?:Angaben|Belege|Information))[^.!?\n]*",
        "",
        text,
        flags=re.I,
    )
    return re.findall(
        r"\b(?:STM32[0-9A-Z]+|ATmega[0-9A-Z]+|RP2040|ESP32(?:-[0-9A-Z]+)?|\d+(?:[.,]\d+)?\s*(?:KiB|MiB|GiB))\b",
        affirmative,
        re.I,
    )


def has_literal(text, value):
    # Preserve identifier boundaries: STM32F446RE cannot establish STM32F446.
    memory = re.fullmatch(r"(\d+(?:[.,]\d+)?)\s*(KiB|MiB|GiB)", value, re.I)
    pattern = (
        r"(?<!\d)" + re.escape(memory[1]) + r"\s*" + memory[2] + r"(?!\w)"
        if memory
        else r"(?<!\w)" + re.escape(value) + r"(?!\w)"
    )
    return bool(re.search(pattern, text, re.I))


def claim_blocks(answer):
    """Paragraph/list-item support, including a following citation-only paragraph."""
    blocks = []
    for block in re.split(r"\n\s*\n|\n(?=\s*(?:[-*+]|\d+[.)])\s+)", answer):
        if not block.strip():
            continue
        references = re.findall(r"\[(?:kb|log|image):[^\]]+\]", block)
        heading = re.sub(r"[\[\]*_#>]", "", block[:100]).strip()
        source_block = references and (
            not re.sub(r"\[(?:kb|log|image):[^\]]+\]|[\s.,;]", "", block)
            or re.match(r"(?:citation(?: evidence| ID)?|source|quelle|beleg)\s*:", heading, re.I)
        )
        if blocks and source_block:
            # A labelled source immediately after a list can support that list.
            # Never replace an explicit (possibly incorrect) citation on an item.
            for index in range(len(blocks) - 1, -1, -1):
                previous = blocks[index]
                if re.search(r"\[(?:kb|log|image):", previous):
                    break
                blocks[index] += "\n" + " ".join(references)
                if not re.match(r"\s*(?:[-*+]|\d+[.)])\s+", previous):
                    break
        blocks.append(block)
    # A quotation immediately following a labelled source belongs to that source.
    for index, block in enumerate(blocks[1:], 1):
        if block.lstrip().startswith(">") and not re.search(r"\[(?:kb|log|image):", block):
            previous = blocks[index - 1]
            if re.match(
                r"(?:citation(?: evidence| ID)?|source|quelle|beleg)\s*:",
                re.sub(r"[\[\]*_#>]", "", previous).strip(),
                re.I,
            ):
                blocks[index] += "\n" + " ".join(
                    re.findall(r"\[(?:kb|log|image):[^\]]+\]", previous)
                )
    return blocks


def repair_evidence(run, answer):
    """Repeat bounded observed excerpt/ID pairs; never silently reassign citations."""
    values = technical_values(answer)
    terms = set(re.findall(r"[\w-]{4,}", str(run.get("question", "")) + " " + answer))
    terms = sorted(terms, key=lambda value: (-len(value), value))[:64]
    hits = sorted(
        observations(run),
        key=lambda h: (
            -(
                100 * sum(has_literal(h.get("text", ""), value) for value in values)
                + sum(term.casefold() in h.get("text", "").casefold() for term in terms)
            )
        ),
    )
    rows = []
    seen = set()
    for hit in hits:
        if hit["citation_id"] not in seen:
            rows.append({"citation_id": hit["citation_id"], "excerpt": hit.get("text", "")[:1200]})
            seen.add(hit["citation_id"])
        if len(rows) == 3:
            break
    return json.dumps(rows, ensure_ascii=False)


def normalize_citations(run, answer):
    """Normalize only exact, observed local citation links; unknown URLs stay inert."""
    hits = observations(run)
    known = {h["citation_id"] for h in hits} | set(run.get("problem_images_supplied", []))
    return "".join(
        part
        if part.startswith("`")
        else re.sub(
            r"\[(?:Citation|Source|Quelle):\s*((?:kb|log|image):[^\]\s]+)\]",
            lambda match: "[" + match[1] + "]" if match[1] in known else match[0],
            re.sub(
                r"\[([^\]\n]{1,240})\]\(((?:kb|log|image):[^\s()]+)\)",
                lambda match: match[1] + " [" + match[2] + "]" if match[2] in known else match[0],
                part,
            ),
            flags=re.I,
        )
        for part in re.split(r"(```[\s\S]*?(?:```|$)|`[^`\n]*`)", answer)
    )


def assess(run, answer):
    answer = normalize_citations(run, str(answer))
    if run.get("budget_summary") or (
        run.get("status") in {"budget_exceeded", "timed_out"}
        and (run.get("result") or {}).get("answer_mode") == "budget_source_extract"
    ):
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
    if any(
        technical_values(block)
        and not all(
            has_literal(
                " ".join(
                    h.get("text", "")
                    for h in hits
                    if h["citation_id"] in set(re.findall(r"\[((?:kb|log|image):[^\]]+)\]", block))
                ),
                value,
            )
            for value in technical_values(block)
        )
        for block in claim_blocks(answer)
    ):
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
    quotes = [
        (quote, set(re.findall(r"\[((?:kb|log|image):[^\]]+)\]", block)))
        for block in claim_blocks(answer)
        for quote in re.findall(r"^>[ \t]*(.*)$", block, re.M)
    ]
    text = " ".join(h.get("text", "") for h in hits)
    # Narrow terminology confusions found in the public pilot, not a general
    # translation/entailment checker. Never invent a replacement translation.
    translated = re.sub(
        r"\b(?:nicht|keine?\w*)\s+(?:Riemenscheib\w*|eingerastet|verrastet)\b",
        "",
        answer,
        flags=re.I,
    )
    if (
        re.search(r"\bbelts?\b", text, re.I)
        and not re.search(r"\bpulleys?\b|Riemenscheib", text, re.I)
        and any(
            re.search(r"\bbelts?\b", block, re.I) and re.search(r"Riemenscheib", block, re.I)
            for block in claim_blocks(translated)
        )
    ) or (
        re.search(r"\bracked\b", text, re.I)
        and not re.search(r"\blatch(?:ed)?\b|\block(?:ed)?\b", text, re.I)
        and any(
            re.search(r"\bracked\b", block, re.I)
            and re.search(r"\b(?:eingerastet|verrastet)\b", block, re.I)
            for block in claim_blocks(translated)
        )
    ):
        issues.append(
            "Some translated technical terms change the source component; retain the original terminology."
        )
    prose = "\n".join(line for line in answer.splitlines() if not line.lstrip().startswith(">"))
    if not run.get("problem_lookup_done") and re.search(
        r"\b(?:Suche in (?:den |diesen |Ihren )?(?:Problem|Fehler)?logs|Logsuche)\b[^.\n]{0,120}\b(?:ergab|lieferte)\b|\bI (?:searched|checked|reviewed) (?:the |your )?(?:provided )?(?:error |problem )?logs\b|\b(?:log search|search in (?:the )?(?:error |problem )?logs)\b[^.\n]{0,100}\b(?:found|returned)\b",
        prose,
        re.I,
    ):
        issues.append("Some investigation claims describe log checks that were not performed.")
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

    for quote, references in quotes:
        quote = re.sub(r"\[(?:kb|log|image):[^\]]+\]", "", quote).strip()
        quote = re.sub(r"\\([\\`*_{}\[\]<>#!])", r"\1", quote)
        quote = quote.replace(r"\"", '"')
        for opening, closing in (('"', '"'), ("“", "”"), ("„", "“")):
            if quote.startswith(opening) and quote.endswith(closing):
                quote = quote[1:-1].strip()
                break
        supporting_text = " ".join(
            h.get("text", "") for h in hits if h["citation_id"] in references
        )
        if len(quote) >= 20 and normalize(quote) not in normalize(supporting_text):
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


def finalize_answer(run, answer):
    """Fail closed after bounded repairs: show original evidence, never bad citations.

    This is explicitly an extractive fallback, not another model answer or an
    entailment proof. Preserve the failed draft contract for quality reporting.
    """
    contract = assess(run, answer)
    if not any(
        issue.startswith(
            (
                "Some references",
                "Some technical identifiers",
                "Some translated technical terms",
                "Some investigation claims",
                "An evidence quotation",
                "The answer has no observed source citations",
            )
        )
        for issue in contract.get("issues", [])
    ) or run.get("experiment"):
        return answer, contract, "generated", None
    pairs = json.loads(repair_evidence(run, answer))
    if not pairs:
        text = (
            "Die Quellenangaben des Entwurfs konnten nicht geprüft werden. Bitte stellen Sie passende Dokumentation bereit; ich kann daraus noch keine belegte Antwort ableiten."
            if run.get("language") == "de"
            else "The draft's citations could not be verified. Please provide the relevant documentation; I cannot give a supported answer from these references."
        )
        return text, assess(run, text), "citation_abstention", contract
    de = run.get("language") == "de"
    output = [
        "Der Entwurf hat die Quellenprüfung nicht bestanden. Ich kann daraus noch keine belegte Bedeutung oder Diagnose ableiten. Hier sind Originalauszüge aus den abgerufenen Quellen; bitte prüfen Sie die passende Dokumentversion."
        if de
        else "The draft did not pass the citation checks. Here are original excerpts from the retrieved sources. These are references, not a verified diagnosis; check the applicable document version."
    ]
    values = technical_values(answer)
    for pair in pairs[:2]:
        excerpt = pair["excerpt"]
        if not excerpt.strip():
            continue
        if len(excerpt) > 1000:
            anchors = [
                m.start() for token in values for m in re.finditer(re.escape(token), excerpt, re.I)
            ]
            start = max(0, min(anchors, default=0) - 80)
            excerpt = excerpt[start : start + 1000]
        lines = [
            line for line in excerpt.splitlines() if not re.search(r"\[(?:kb|log|image):", line)
        ]
        literal = "\n".join("> " + re.sub(r"([\\`*_{}\[\]<>#!])", r"\\\1", line) for line in lines)
        output.append(literal + "\n\n[" + pair["citation_id"] + "]")
    if len(output) == 1:
        output.extend("[" + pair["citation_id"] + "]" for pair in pairs[:2])
    text = "\n\n".join(output)
    final_contract = assess(run, text)
    return text, final_contract, "source_extract", contract
