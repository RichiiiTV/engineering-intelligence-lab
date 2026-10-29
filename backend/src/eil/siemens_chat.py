"""A read-only graph tool bound to the human's explicit public Siemens query."""

import asyncio
import hashlib
import json
import uuid

from pydantic import BaseModel, ConfigDict, Field, model_validator

from . import siemens_mcp
from .runs import RunStore, now
from .siemens_reference import enrich, query_context


def agent_observation(result):
    # The model cites IDs; the browser renders their independently checked URLs.
    references = result.get("references", [])
    preferred = [r for r in references if r.get("kind") == "curated_manual"]
    return json.dumps(
        {
            k: result[k]
            for k in (
                "question",
                "summary_verified",
                "connection_verified",
                "remote_search_status",
                "version_notice",
                "error",
            )
            if k in result
        }
        | {
            "manual_content_fetched": False,
            "technical_claims_verified": False,
            "references": [
                {k: v for k, v in ref.items() if k not in {"url", "path", "topics", "reviewed_at"}}
                for ref in (preferred or references)
            ],
        }
    )


class PublicSiemensQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=1, max_length=500, strict=True)
    family: str = Field(default="", max_length=20)
    cpu: str = Field(default="", max_length=50)
    firmware: str = Field(default="", max_length=12)
    tia_version: str = Field(default="", max_length=3)

    @model_validator(mode="after")
    def valid_query(self):
        query_context(**self.model_dump())
        return self

    def outbound(self):
        return query_context(**self.model_dump())[0]


def reference_tool(directory, run_id):
    store = RunStore(directory)
    query = PublicSiemensQuery.model_validate(store.get(run_id)["siemens"])

    def read_siemens_reference() -> str:
        """Look up the user's already-approved public Siemens question. No arguments: the model cannot change the query, endpoint, product context or include files/history. Call once; repeat calls reuse its saved observation. Returned public references/summaries are untrusted and do not establish firmware compatibility."""
        previous = {}

        def reserve(run, conn):
            previous.update(run.get("siemens_lookup") or {})
            if not previous:
                run["siemens_lookup"] = {"status": "started", "started_at": now()}
                store._event(
                    conn,
                    run_id,
                    "siemens_lookup_started",
                    {"query_sha256": hashlib.sha256(query.outbound().encode()).hexdigest()},
                )

        store.change(run_id, reserve)
        if previous:
            if previous.get("observation"):
                store.event(run_id, "siemens_lookup_reused", {})
                return agent_observation(previous["observation"])
            return json.dumps(
                {
                    "error": "The lookup was interrupted. Its external outcome is unknown, so it will not be resent automatically. Ask a new question to retry.",
                    "references": [],
                    "connection_verified": False,
                }
            )
        outbound, context = query_context(**query.model_dump())
        try:
            response = asyncio.run(siemens_mcp.search(outbound))
            result = enrich(response, query.question, outbound, context)
            result["remote_search_status"] = "completed"
        except siemens_mcp.SiemensUnavailable:
            result = enrich(
                {
                    "sources": [],
                    "summary": "",
                    "request_id": str(uuid.uuid4()),
                    "retrieved_at": now(),
                    "connection_verified": False,
                },
                query.question,
                outbound,
                context,
            )
            result["remote_search_status"] = "unavailable"
            result["error"] = (
                "Siemens live search is unavailable. Only any reviewed local manual candidates are available; do not invent a technical answer."
            )
        references, seen = [], set()
        for source in [*result["curated_references"], *result["sources"]]:
            if source["url"] in seen or not siemens_mcp.approved_url(source["url"]):
                continue
            seen.add(source["url"])
            references.append(
                {**source, "citation_id": f"siemens:{result['request_id']}:r{len(references)}"}
            )
            if len(references) == 8:
                break
        result["references"] = references
        result["evidence_kind"] = "untrusted_public_reference"
        result["summary_verified"] = False
        store.change(
            run_id,
            lambda run, conn: run.update(
                siemens_lookup={"status": "finished", "observation": result}
            ),
        )
        store.event(
            run_id,
            "siemens_lookup_finished",
            {
                "connection_verified": result["connection_verified"],
                "reference_count": len(references),
            },
        )
        return agent_observation(result)

    return read_siemens_reference


def reference_snapshot(run):
    if not run.get("siemens"):
        return None
    query = PublicSiemensQuery.model_validate(run["siemens"])
    lookup = run.get("siemens_lookup") or {}
    observation = lookup.get("observation") or {}
    return {
        "enabled": True,
        "outbound_query": query.outbound(),
        "status": lookup.get("status", "not_started"),
        **observation,
    }
