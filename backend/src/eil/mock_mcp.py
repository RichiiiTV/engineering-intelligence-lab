"""Reviewed read-only MCP integration; only an in-process synthetic server is supported."""

import asyncio
import json
from datetime import timedelta
from typing import Literal

from mcp.server.fastmcp import FastMCP
from mcp.shared.memory import create_connected_server_and_client_session
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict

Station = Literal["S01", "S02", "S03", "S04"]
SERVER_ID = "eil-synthetic-maintenance-v1"
TOOL_NAME = "get_station_context"
APPROVED_SCHEMA = {
    "type": "object",
    "properties": {"station_id": {"type": "string", "enum": ["S01", "S02", "S03", "S04"]}},
    "required": ["station_id"],
}


class StationContext(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    station_id: Station
    synthetic: Literal[True]
    source: Literal["eil-synthetic-maintenance-v1"]
    record_id: str
    note: str
    uncertainty: str


def mock_server():
    server = FastMCP(SERVER_ID)

    @server.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=False))
    def get_station_context(station_id: Station) -> StationContext:
        """Read a fictional maintenance note for a synthetic station. Not production evidence."""
        return StationContext(
            station_id=station_id,
            synthetic=True,
            source=SERVER_ID,
            record_id=f"MOCK-{station_id}-20261010",
            note=(
                "Fictional note: S03 illumination and camera exposure changed on 2026-10-10."
                if station_id == "S03"
                else "Fictional note: no settings change in this mock dataset."
            ),
            uncertainty="Synthetic context only. Not a case citation or proof of cause; verify uploaded evidence.",
        )

    return server


def approved_tool(tool):
    # Descriptions and annotations are untrusted hints, never authorization.
    schema = tool.inputSchema
    props = schema.get("properties", {})
    return (
        tool.name == TOOL_NAME
        and schema.get("type") == "object"
        and schema.get("required") == ["station_id"]
        and set(props) == {"station_id"}
        and props["station_id"].get("type") == "string"
        and props["station_id"].get("enum") == ["S01", "S02", "S03", "S04"]
        and schema.get("additionalProperties", False) is False
    )


async def call_mock_tool(name, arguments):
    if name != TOOL_NAME or set(arguments) != {"station_id"}:
        raise ValueError("MCP tool/arguments are outside the reviewed allowlist")
    if arguments["station_id"] not in ("S01", "S02", "S03", "S04"):
        raise ValueError("Station must be S01-S04")
    async with asyncio.timeout(3):
        async with create_connected_server_and_client_session(
            mock_server(), read_timeout_seconds=timedelta(seconds=2)
        ) as session:
            listed = await session.list_tools()
            if listed.nextCursor or len(listed.tools) != 1 or not approved_tool(listed.tools[0]):
                raise ValueError("MCP catalog differs from the reviewed contract")
            result = await session.call_tool(name, arguments)
            if result.isError or not result.structuredContent:
                raise ValueError("Mock MCP returned an error or missing structured content")
            if len(json.dumps(result.structuredContent)) > 4096:
                raise ValueError("Mock MCP observation exceeds its size limit")
            observation = StationContext.model_validate(result.structuredContent)
            if observation.station_id != arguments["station_id"]:
                raise ValueError("Mock MCP returned a different station")
            return observation.model_dump()


def read_mock_station_context(station_id: Station) -> str:
    """Read optional synthetic maintenance context via the approved local MCP mock. Not case evidence."""
    try:
        return json.dumps(asyncio.run(call_mock_tool(TOOL_NAME, {"station_id": station_id})))
    except Exception as exc:
        # AnyIO can wrap protocol/validation failures in an ExceptionGroup.
        return json.dumps(
            {"error": f"Mock MCP unavailable ({type(exc).__name__})", "synthetic": True}
        )


def catalog():
    return {
        "server_id": SERVER_ID,
        "transport": "in-process-memory",
        "synthetic": True,
        "enabled_by_default": False,
        "tools": [{"name": TOOL_NAME, "input_schema": APPROVED_SCHEMA, "read_only": True}],
        "limitations": "Fixed local mock only. No external servers, credentials, writes or production data.",
    }
