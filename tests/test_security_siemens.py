import asyncio
import json
import time

import httpx
import pytest
from fastapi.testclient import TestClient
from mcp.types import CallToolResult, Tool

from eil import siemens_mcp as sm
from eil.api import create_app
from eil.service import RunService
from tests.auth_helpers import sign_in


class BytesStream(httpx.AsyncByteStream):
    def __init__(self, content):
        self.content = content

    async def __aiter__(self):
        yield self.content


def rpc_transport(calls, *, schema=None, payload=None, status=200):
    async def respond(request):
        assert str(request.url) == sm.ENDPOINT and request.method == "POST"
        body = json.loads(request.content)
        calls.append(body)
        method = body["method"]
        if method == "notifications/initialized":
            return httpx.Response(202, stream=BytesStream(b""))
        if method == "initialize":
            value = {
                "protocolVersion": body["params"]["protocolVersion"],
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "siemens-test", "version": "test"},
            }
        elif method == "tools/list":
            value = {
                "tools": [
                    {
                        "name": "siemens_search",
                        "inputSchema": schema
                        or {
                            "type": "object",
                            "properties": {"query": {"type": "string"}},
                            "required": ["query"],
                        },
                    }
                ]
            }
        elif method == "tools/call":
            assert body["params"]["name"] == "siemens_search"
            value = {"content": [], "structuredContent": payload or search_payload()}
        else:
            raise AssertionError(f"Unreviewed MCP method: {method}")
        raw = json.dumps({"jsonrpc": "2.0", "id": body["id"], "result": value}).encode()
        return httpx.Response(
            status, headers={"Content-Type": "application/json"}, stream=BytesStream(raw)
        )

    return httpx.MockTransport(respond)


def search_payload():
    return {
        "query": "OB1 cycle time",
        "ai_summary": {"text": "<script>untrusted</script> Search summary."},
        "content_results": [
            {
                "title": "S7 manual",
                "description": "Cycle times",
                "url": "https://support.industry.siemens.com/manual",
            }
        ],
        "product_results": [],
    }


def test_real_sdk_sends_only_the_submitted_question():
    calls = []
    result = asyncio.run(sm._search("OB1 cycle time", transport=rpc_transport(calls)))
    assert result["connection_verified"] and result["summary_verified"] is False
    request = next(c for c in calls if c["method"] == "tools/call")
    assert request["params"]["arguments"] == {"query": "OB1 cycle time"}
    assert "case_id" not in json.dumps(calls) and "authorization" not in json.dumps(calls)
    assert result["sources"][0]["url"].startswith("https://support.industry.siemens.com/")


def test_catalog_drift_prevents_dispatch():
    calls = []
    schema = {
        "type": "object",
        "properties": {"query": {"type": "string"}, "command": {"type": "string"}},
        "required": ["query"],
    }
    with pytest.raises(Exception):
        asyncio.run(sm._search("OB1 cycle time", transport=rpc_transport(calls, schema=schema)))
    assert not any(c["method"] == "tools/call" for c in calls)
    assert not sm.approved_tool(Tool(name="plc_write", inputSchema=schema))


@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)",
        "http://siemens.com/",
        "https://siemens.com.evil.test/",
        "https://evilsiemens.com/",
        "https://siemens.com@127.0.0.1/",
        "https://127.0.0.1/",
        "https://siemens.com:444/",
        "https://evil.test\\@siemens.com/",
        "https://jobs.siemens.com/job",
        "https://siemens.com/\nattack",
    ],
)
def test_untrusted_result_urls_are_rejected(url):
    assert not sm.approved_url(url)
    data = search_payload()
    data["content_results"][0]["url"] = url
    result = sm.normalize_result(
        CallToolResult(content=[], structuredContent=data), "OB1 cycle time"
    )
    assert result["sources"] == [] and result["summary"] == ""


def test_wrong_question_and_error_results_fail_closed():
    with pytest.raises(sm.SiemensUnavailable):
        sm.normalize_result(
            CallToolResult(content=[], structuredContent=search_payload()), "Different question"
        )
    with pytest.raises(sm.SiemensUnavailable):
        sm.normalize_result(CallToolResult(content=[], isError=True), "OB1 cycle time")


@pytest.mark.parametrize(
    "status,headers,body",
    [
        (302, {"Location": "http://127.0.0.1/private"}, b""),
        (200, {"Content-Type": "application/json"}, b"x" * (sm.MAX_RESPONSE_BYTES + 1)),
        (200, {"Content-Type": "text/event-stream"}, b"data: unlimited\n"),
        (200, {"Content-Type": "application/json", "Content-Encoding": "gzip"}, b"compressed"),
    ],
)
def test_transport_rejects_redirects_oversize_streams_and_compression(status, headers, body):
    calls = []

    async def run():
        def respond(request):
            calls.append(str(request.url))
            return httpx.Response(status, headers=headers, stream=BytesStream(body))

        async with httpx.AsyncClient(
            transport=sm.SiemensTransport(httpx.MockTransport(respond))
        ) as client:
            await client.post(sm.ENDPOINT, json={})

    with pytest.raises(sm.SiemensUnavailable):
        asyncio.run(run())
    assert calls == [sm.ENDPOINT]


def test_global_deadline_and_capacity_are_bounded(monkeypatch):
    async def slow(request):
        await asyncio.sleep(1)
        return httpx.Response(200)

    monkeypatch.setattr(sm, "TIMEOUT_SECONDS", 0.03)
    before = time.monotonic()
    with pytest.raises(TimeoutError):
        asyncio.run(sm._search("OB1 cycle time", transport=httpx.MockTransport(slow)))
    assert time.monotonic() - before < 0.5

    async def concurrent():
        entered, release = asyncio.Event(), asyncio.Event()

        async def paused(question):
            entered.set()
            await release.wait()
            return {"question": question}

        monkeypatch.setattr(sm, "_search", paused)
        monkeypatch.setattr(sm, "_last_started", float("-inf"))
        first = asyncio.create_task(sm.search("First public question"))
        await entered.wait()
        with pytest.raises(sm.SiemensBusy):
            await sm.search("Second public question")
        release.set()
        await first

    asyncio.run(concurrent())


def test_host_origin_fetch_metadata_and_json_body_boundaries(tmp_path, monkeypatch):
    sent = []

    async def fake_search(question):
        sent.append(question)
        return {"question": question, "sources": []}

    monkeypatch.setattr(sm, "search", fake_search)
    with TestClient(
        create_app(lambda: RunService(tmp_path)), base_url="http://127.0.0.1"
    ) as client:
        sign_in(client)
        for path in ("/api/cases", "/api/integrations/siemens-mcp"):
            assert (
                client.get(
                    path, headers={"Host": "attacker.example", "Origin": "http://attacker.example"}
                ).status_code
                == 400
            )
            assert (
                client.get(path, headers={"Origin": "https://attacker.example"}).status_code == 403
            )
        assert (
            client.post(
                "/api/cases",
                headers={"Host": "attacker.example", "Origin": "http://attacker.example"},
                json={"title": "Attack"},
            ).status_code
            == 400
        )
        assert client.get("/api/cases", headers={"Sec-Fetch-Site": "cross-site"}).status_code == 403
        assert client.post("/api/cases", content=b"x" * (128 * 1024 + 1)).status_code == 413
        assert client.get("/api/cases").json()["cases"] == []
        path = "/api/knowledge/siemens/search"
        assert (
            client.post(
                path, json={"question": "OB1 cycle time", "url": "http://127.0.0.1"}
            ).status_code
            == 422
        )
        assert client.post(path, json={"question": "x" * 501}).status_code == 422
        assert sent == []
        assert client.get("/api/integrations/siemens-mcp").json()["connected"] is None
        assert sent == []
        assert client.post(path, json={"question": "OB1 cycle time"}).status_code == 200
        assert sent == ["OB1 cycle time"]
