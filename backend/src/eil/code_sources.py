"""Bounded source-text locations and static parsing. Uploaded code is never executed."""

import ast


def chunks(text):
    result = []
    current = []
    first = 1
    for number, line in enumerate(text.splitlines(), 1):
        if current and (len(current) >= 35 or sum(len(x) + 1 for x in current) + len(line) > 1600):
            result.append(
                {
                    "page": 1,
                    "pages": [1],
                    "kind": "code",
                    "line_start": first,
                    "line_end": number - 1,
                    "text": "\n".join(current),
                }
            )
            current = []
        if not current:
            first = number
        if len(line) > 1600:
            for offset in range(0, len(line), 1600):
                result.append(
                    {
                        "page": 1,
                        "pages": [1],
                        "kind": "code",
                        "line_start": number,
                        "line_end": number,
                        "offset": offset,
                        "text": line[offset : offset + 1600],
                    }
                )
        else:
            current.append(line)
    if current:
        result.append(
            {
                "page": 1,
                "pages": [1],
                "kind": "code",
                "line_start": first,
                "line_end": len(text.splitlines()),
                "text": "\n".join(current),
            }
        )
    return result


def inspect(filename, text):
    findings = []
    if filename.lower().endswith(".py"):
        try:
            ast.parse(text)
        except SyntaxError as exc:
            findings.append(
                {
                    "line": exc.lineno,
                    "column": exc.offset,
                    "message": exc.msg,
                    "kind": "syntax_error",
                }
            )
        scope = "Python syntax only; code was parsed, never executed. Behaviour and runtime dependencies are unverified."
    else:
        scope = "Source text only. Device/compiler semantics require the appropriate engineering tool; no uploaded code was executed."
    return {"findings": findings, "scope": scope}
