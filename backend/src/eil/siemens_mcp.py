"""Fixed public Siemens knowledge search. Never an investigation agent tool."""

from __future__ import annotations

import asyncio
import hashlib
import json
import threading
import time
import uuid
from datetime import timedelta
from urllib.parse import urlsplit

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from .runs import now

ENDPOINT = "https://mcp.siemens.com/mcp"
TOOL_NAME = "siemens_search"
MAX_RESPONSE_BYTES = 256 * 1024
TIMEOUT_SECONDS = 25
_slot = threading.BoundedSemaphore(1)
_rate_lock = threading.Lock()
_last_started = float("-inf")


class SiemensUnavailable(RuntimeError):
    pass


class SiemensBusy(SiemensUnavailable):
    pass


class SiemensTransport(httpx.AsyncBaseTransport):
    """Limit every response before the SDK parses it; no redirects, proxies or SSE."""

    def __init__(self, transport=None):
        self.inner = transport or httpx.AsyncHTTPTransport(retries=0, trust_env=False)

    async def handle_async_request(self, request):
        if str(request.url) != ENDPOINT or request.method != "POST":
            raise SiemensUnavailable("Unapproved Siemens transport request")
        response = await self.inner.handle_async_request(request)
        try:
            if response.status_code not in {200, 202, 204}:
                raise SiemensUnavailable("Siemens returned an unsuccessful response")
            if response.headers.get("content-encoding", "identity").lower() != "identity":
                raise SiemensUnavailable("Compressed Siemens responses are not accepted")
            if (
                response.status_code == 200
                and response.headers.get("content-type", "").split(";")[0].strip()
                != "application/json"
            ):
                raise SiemensUnavailable("Unexpected Siemens response format")
            content = bytearray()
            async for chunk in response.aiter_raw():
                if len(content) + len(chunk) > MAX_RESPONSE_BYTES:
                    raise SiemensUnavailable("Siemens response exceeds its size limit")
                content.extend(chunk)
            return httpx.Response(
                response.status_code,
                headers=response.headers,
                content=bytes(content),
                request=request,
            )
        finally:
            await response.aclose()

    async def aclose(self):
        await self.inner.aclose()


def approved_tool(tool):
    schema = tool.inputSchema
    props = schema.get("properties", {})
    return (
        tool.name == TOOL_NAME
        and set(schema)
        <= {
            "$schema",
            "title",
            "description",
            "type",
            "properties",
            "required",
            "additionalProperties",
        }
        and schema.get("type") == "object"
        and schema.get("required") == ["query"]
        and set(props) == {"query"}
        and set(props["query"]) <= {"type", "description", "title"}
        and props["query"].get("type") == "string"
        and isinstance(schema.get("additionalProperties", True), bool)
    )


def approved_url(value):
    if (
        not isinstance(value, str)
        or not 1 <= len(value) <= 2048
        or "\\" in value
        or any(c.isspace() or ord(c) < 32 for c in value)
    ):
        return False
    try:
        url = urlsplit(value)
        host = url.hostname or ""
        return (
            url.scheme == "https"
            and not url.username
            and not url.password
            and url.port in {None, 443}
            and (host == "siemens.com" or host.endswith(".siemens.com"))
            and host != "jobs.siemens.com"
        )
    except ValueError:
        return False


def normalize_result(result, question):
    if result.isError:
        raise SiemensUnavailable("Siemens search returned a tool error")
    payload = result.structuredContent
    if payload is None:
        for block in result.content:
            if block.type == "text":
                try:
                    candidate = json.loads(block.text)
                except (ValueError, TypeError):
                    continue
                if isinstance(candidate, dict) and candidate.get("query") == question:
                    payload = candidate
                    break
    if not isinstance(payload, dict) or payload.get("query") != question:
        raise SiemensUnavailable("Siemens response does not match the submitted question")
    sources, seen = [], set()
    excluded = 0
    for key, kind in (("content_results", "content"), ("product_results", "product")):
        rows = payload.get(key, [])
        if not isinstance(rows, list):
            raise SiemensUnavailable("Invalid Siemens result structure")
        group = []
        for item in rows:
            if (
                not isinstance(item, dict)
                or not approved_url(item.get("url"))
                or not isinstance(item.get("title"), str)
                or not isinstance(item.get("description", ""), str)
            ):
                excluded += 1
                continue
            if item["url"] in seen:
                continue
            seen.add(item["url"])
            group.append(
                {
                    "title": item["title"][:180],
                    "url": item["url"],
                    "description": item.get("description", "")[:400],
                    "kind": kind,
                }
            )
        sources.extend(group[:4])
    summary = payload.get("ai_summary", {})
    if not isinstance(summary, dict) or not isinstance(summary.get("text", ""), str):
        raise SiemensUnavailable("Invalid Siemens summary structure")
    return {
        "sources": sources,
        "summary": summary.get("text", "")[:1200] if sources else "",
        "excluded_results": excluded,
        "summary_verified": False,
        "limitations": "Siemens-generated search summary, not verified technical advice. Check the linked product documentation and exact CPU/firmware/TIA version. Search coverage can be incomplete. No equipment connection is provided.",
    }


async def _search(question, *, transport=None):
    started = time.perf_counter()
    async with asyncio.timeout(TIMEOUT_SECONDS):
        async with httpx.AsyncClient(
            transport=SiemensTransport(transport),
            timeout=httpx.Timeout(15, connect=5),
            follow_redirects=False,
            trust_env=False,
            headers={"Accept-Encoding": "identity"},
        ) as client:
            async with streamable_http_client(
                ENDPOINT, http_client=client, terminate_on_close=False
            ) as (read, write, _):
                async with ClientSession(
                    read, write, read_timeout_seconds=timedelta(seconds=20)
                ) as session:
                    initialized = await session.initialize()
                    listed = await session.list_tools()
                    selected = [tool for tool in listed.tools if tool.name == TOOL_NAME]
                    if listed.nextCursor or len(selected) != 1 or not approved_tool(selected[0]):
                        raise SiemensUnavailable("Siemens tool contract changed")
                    # The user-supplied question is the entire external payload.
                    # No case/run identifier, upload, prompt, model output or secret.
                    result = await session.call_tool(TOOL_NAME, {"query": question})
                    observation = normalize_result(result, question)
                    return {
                        "request_id": str(uuid.uuid4()),
                        "question": question,
                        "question_sha256": hashlib.sha256(question.encode()).hexdigest(),
                        "endpoint": ENDPOINT,
                        "tool": TOOL_NAME,
                        "server_version": initialized.serverInfo.version[:80],
                        "retrieved_at": now(),
                        "duration_ms": round((time.perf_counter() - started) * 1000, 3),
                        "connection_verified": True,
                        **observation,
                    }


async def search(question):
    global _last_started
    if not isinstance(question, str) or not question.strip() or len(question) > 500:
        raise ValueError("Enter a public product question of 1-500 characters")
    if not _slot.acquire(blocking=False):
        raise SiemensBusy("A Siemens search is already running. Try again shortly.")
    try:
        with _rate_lock:
            if time.monotonic() - _last_started < 2:
                raise SiemensBusy("Please wait two seconds between Siemens searches.")
            _last_started = time.monotonic()
        try:
            return await _search(question.strip())
        except Exception as exc:
            # AnyIO may wrap SDK errors; never reflect upstream error text or
            # instructions into application errors. No retry or REST fallback.
            raise SiemensUnavailable(
                "Siemens documentation search is unavailable. Try again later."
            ) from exc
    finally:
        _slot.release()


def catalog():
    return {
        "server_id": "siemens-public-knowledge",
        "endpoint": ENDPOINT,
        "tool": TOOL_NAME,
        "transport": "streamable-http-json",
        "connected": None,
        "scope": "Public documentation/product questions only; no PLC access",
        "outbound_data": "Only the explicitly submitted question",
        "max_question_characters": 500,
        "timeout_seconds": TIMEOUT_SECONDS,
        "max_response_bytes": MAX_RESPONSE_BYTES,
    }
