"""Exact line locations for plain-text chunks, including legacy source snapshots."""

import json
import re
from bisect import bisect_right


def plain_chunks(text):
    starts = [0, *(m.end() for m in re.finditer(r"\r\n|[\n\r\v\f\x1c-\x1e\x85\u2028\u2029]", text))]
    offset = 0
    chunks = []
    for page, body in enumerate(text.split("\f"), 1):
        for start in range(0, len(body), 1000):
            value = body[start : start + 1200]
            if value.strip():
                first = offset + start
                chunks.append(
                    {
                        "page": page,
                        "text": value,
                        "offset": first,
                        "line_start": bisect_right(starts, first),
                        "line_end": bisect_right(starts, first + len(value) - 1),
                    }
                )
        offset += len(body) + 1
    return chunks


def line_hits(library, document, start_line, end_line):
    """Never assign missing line metadata to the whole document.

    Legacy Markdown/text chunk locations can be reconstructed exactly using the
    original deterministic chunker and checked bytes. No stored source is changed.
    Returned text is the actually requested line intersection, not unrelated chunks.
    """
    text = document["raw"].decode("utf-8-sig")
    starts = [0, *(m.end() for m in re.finditer(r"\r\n|[\n\r\v\f\x1c-\x1e\x85\u2028\u2029]", text))]
    read_start = starts[start_line - 1] if start_line <= len(starts) else len(text)
    read_end = starts[end_line] if end_line < len(starts) else len(text)
    legacy = plain_chunks(text) if document["kind"] in {"md", "txt"} else []
    with library.evidence.connection() as conn:
        rows = conn.execute(
            "SELECT id,page,text,metadata FROM knowledge_passages WHERE document_id=? ORDER BY rowid",
            (document["id"],),
        ).fetchall()
    hits = []
    for row in rows:
        loc = json.loads(row["metadata"])
        first, last = loc.get("line_start"), loc.get("line_end")
        chunk = None
        if legacy:
            index = int(row["id"].rsplit(":c", 1)[-1])
            if index >= len(legacy):
                continue
            chunk = legacy[index]
            if chunk["page"] != row["page"] or chunk["text"] != row["text"]:
                continue
            first, last = chunk["line_start"], chunk["line_end"]
        if first is None or last is None:
            continue
        if first <= end_line and last >= start_line:
            hit = library.resolve(row["id"], [document["id"]])
            low, high = max(first, start_line), min(last, end_line)
            if chunk is not None:
                start = max(chunk["offset"], read_start)
                end = min(chunk["offset"] + len(chunk["text"]), read_end)
                excerpt = text[start:end]
            else:
                excerpt = "\n".join(row["text"].splitlines()[low - first : high - first + 1])
            if not excerpt:
                continue
            hit.update(text=excerpt, line_start=low, line_end=high)
            hits.append(hit)
    if len(hits) > 8:
        raise ValueError("Read fewer lines (eight source passages maximum)")
    return hits
