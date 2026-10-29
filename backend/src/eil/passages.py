"""Canonical extracted locations and bounded product context."""

import re

from pydantic import BaseModel, ConfigDict, Field


class ProductContext(BaseModel):
    model_config = ConfigDict(extra="forbid")
    family: str = Field(default="", max_length=60)
    model: str = Field(default="", max_length=80)
    firmware: str = Field(default="", max_length=40)
    software_version: str = Field(default="", max_length=40)


def context_for(question, explicit=None):
    context = ProductContext.model_validate(explicit or {}).model_dump()
    versions = set(re.findall(r"\bV(\d{1,2}(?:\.\d+)?)\b", question, re.I))
    if not context["software_version"] and len(versions) == 1:
        context["software_version"] = "V" + next(iter(versions))
    return context


def compatible(metadata, context):
    known = {
        "family": metadata.get("family", ""),
        "software_version": metadata.get("version", ""),
        **(metadata.get("profile") or {}),
    }
    unknown = []
    for field, asked in context.items():
        actual = known.get(field, "")
        if not asked:
            continue
        if not actual or actual.casefold() in {"general", "unspecified", "eil starter"}:
            unknown.append(field)
            continue
        if field == "software_version" and not re.fullmatch(r"v\d+(?:\.\d+)?", actual, re.I):
            unknown.append(field)
            continue

        def normalize(v):
            return re.sub(r"[\s_-]", "", v.casefold())

        if normalize(asked) != normalize(actual):
            return False, unknown
    return True, unknown


def location(chunk):
    return {
        k: chunk[k]
        for k in (
            "page",
            "pages",
            "kind",
            "item_ref",
            "offset",
            "bboxes",
            "multi_page_item",
            "line_start",
            "line_end",
            "section",
        )
        if k in chunk
    }
