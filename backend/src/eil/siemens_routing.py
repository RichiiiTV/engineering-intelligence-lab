"""Public diagnostic routing from the current human question only.

Never accepts a run, catalog, attachment, history or model output. Only canonical
product families and explicitly typed diagnostic identifiers enter a fixed query.
"""

import re

from .siemens_chat import PublicSiemensQuery


def automatic_public_query(question: str, *, language="de"):
    if language not in {"de", "en"}:
        raise ValueError("Choose de or en")
    if re.search(
        r"(?:nur|ausschließlich)\s+(?:lokal|intern)|(?:nicht|keine?)\b.{0,30}"
        r"(?:extern|online|internet|mcp|siemens|senden|übertragen)|"
        r"(?:local only|no external)|(?:don't|do not|never)\b.{0,30}(?:send|search|mcp|siemens)",
        question,
        re.I,
    ):
        return None
    families = {
        "S7-" + match.group(1) + (" G2" if match.group(2) else "")
        for match in re.finditer(r"\bS7[- ]?(1200|1500)(\s+G2)?\b", question, re.I)
        if not (match.group(1) == "1500" and match.group(2))
    }
    if len(families) != 1:
        return None
    # Hex-looking passwords/serials are not diagnostic identifiers. A normal
    # automatic search also needs diagnostic intent, not just a product mention.
    if not re.search(
        r"\b(?:fehler\w*|error\w*|status\w*|diagnos\w*|meld\w*|störung\w*|OB\s*\d+)\b",
        question,
        re.I,
    ):
        return None

    def public_field(match):
        return not re.search(
            r"\b(?:passwort|password|secret|token|api[-_ ]?key|kennwort|seriennummer|serial)\b[^.\n]{0,24}$",
            question[max(0, match.start() - 60) : match.start()],
            re.I,
        )

    codes = {
        "16#" + m.group(1).upper()
        for m in re.finditer(r"(?<![\w#])(?:16#|0x)([0-9a-f]{4})(?![\w])", question, re.I)
        if public_field(m)
    }
    codes.update(
        "16#" + m.group(1).upper()
        for m in re.finditer(
            r"\b(?:Fehlercode|Statuscode|Diagnosecode|error\s*code|status)\s*[:=]?\s*"
            r"([0-9a-f]{4})(?!\w)",
            question,
            re.I,
        )
        if re.search(r"[a-f]", m.group(1), re.I) and public_field(m)
    )
    blocks = {
        "OB" + m.group(1)
        for m in re.finditer(r"\bOB\s*(80|82|83|85|86|87|121|122)\b", question, re.I)
        if public_field(m)
    }
    identifiers = sorted(codes | blocks)
    if not identifiers or len(identifiers) > 3:
        return None
    family = families.pop()
    return PublicSiemensQuery(
        question=(
            f"SIMATIC {family}: Diagnose zu {', '.join(identifiers)}. "
            "Öffentliche Siemens-Dokumentation zu Bedeutung, Voraussetzungen und "
            "dokumentierten Prüfungen suchen. Antwort auf Deutsch."
        )
        if language == "de"
        else (
            f"SIMATIC {family}: diagnostics for {', '.join(identifiers)}. "
            "Find public Siemens documentation on meaning, prerequisites and documented checks. Answer in English."
        ),
        family=family,
    ).model_dump()
