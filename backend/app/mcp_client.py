"""Thin MCP client used to pull work data from MCP servers over streamable HTTP.

A session is opened per call. Tool calls here are infrequent (a dashboard load,
a chat turn), so a short-lived session is simpler than keeping one alive and
having to recover it when the server restarts.
"""
import json
import logging
from typing import Any

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

logger = logging.getLogger(__name__)


class MCPError(Exception):
    """Raised when an MCP server is unreachable or a tool call fails."""


def _parse_content(result: Any) -> Any:
    """Pull usable data out of a CallToolResult.

    Servers may answer with structured content, with JSON encoded as text, or
    with plain prose. Try them in that order and never guess at a shape.
    """
    structured = getattr(result, "structured_content", None)
    if structured:
        return structured

    texts: list[str] = []
    for block in getattr(result, "content", []) or []:
        text = getattr(block, "text", None)
        if text:
            texts.append(text)
    if not texts:
        return None

    joined = "\n".join(texts)
    try:
        return json.loads(joined)
    except json.JSONDecodeError:
        return joined


async def call_tool(
    url: str,
    tool: str,
    arguments: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 30.0,
) -> Any:
    try:
        async with httpx.AsyncClient(headers=headers or {}, timeout=timeout) as http_client:
            async with streamable_http_client(url, http_client=http_client) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    result = await session.call_tool(tool, arguments or {})
    except MCPError:
        raise
    except Exception as error:  # transport, protocol and timeout failures all land here
        logger.warning("MCP call %s on %s failed: %r", tool, url, error)
        raise MCPError(f"MCP server at {url} failed on '{tool}': {error}") from error

    if getattr(result, "is_error", False):
        raise MCPError(f"MCP tool '{tool}' returned an error: {_parse_content(result)}")
    return _parse_content(result)


async def list_tools(url: str, headers: dict[str, str] | None = None, timeout: float = 15.0) -> list[str]:
    try:
        async with httpx.AsyncClient(headers=headers or {}, timeout=timeout) as http_client:
            async with streamable_http_client(url, http_client=http_client) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    listing = await session.list_tools()
    except Exception as error:
        logger.warning("MCP list_tools on %s failed: %r", url, error)
        raise MCPError(f"MCP server at {url} is unreachable: {error}") from error
    return [tool.name for tool in listing.tools]
