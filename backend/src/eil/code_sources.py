"""Bounded source-text locations and static parsing. Uploaded code is never executed."""

import ast
import io
import tokenize


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
        if len(text) > 32000:
            return {
                "findings": [],
                "scope": "Static parsing skipped above 32,000 characters. Use bounded text search/read; no uploaded code was executed.",
            }
        try:
            tokens = list(tokenize.generate_tokens(io.StringIO(text).readline))
            depth = 0
            for token in tokens:
                if token.type == tokenize.OP:
                    if token.string in {"(", "[", "{"}:
                        depth += 1
                    if token.string in {")", "]", "}"}:
                        depth -= 1
                    if depth > 80:
                        raise RecursionError
            if len(tokens) > 1000:
                raise RecursionError
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
        except (RecursionError, MemoryError, tokenize.TokenError, ValueError):
            return {
                "findings": [],
                "scope": "Static parser complexity limit reached. Use bounded text search/read; no uploaded code was executed.",
            }
        scope = "Python syntax only; code was parsed, never executed. Behaviour and runtime dependencies are unverified."
    else:
        scope = "Source text only. Device/compiler semantics require the appropriate engineering tool; no uploaded code was executed."
    return {"findings": findings, "scope": scope}
