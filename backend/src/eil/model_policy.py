"""Pure local-model identity checks shared by generation and embeddings."""

import re


def checked_local_model(entry, model_name):
    if (
        not isinstance(entry, dict)
        or entry.get("remote_host")
        or entry.get("remote_model")
        or "cloud" in model_name.casefold()
        or not isinstance(entry.get("details"), dict)
        or entry["details"].get("format") != "gguf"
        or not isinstance(entry.get("size"), int)
        or entry["size"] < 1024**2
        or not isinstance(entry.get("digest"), str)
        or not re.fullmatch(r"(?:sha256:)?[0-9a-f]{64}", entry["digest"])
    ):
        raise ValueError("A downloaded local GGUF model is required")
    return entry
