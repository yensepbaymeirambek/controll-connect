"""Stdio MCP server exposing the workspace query surface.

Speaks JSON-RPC 2.0 over stdin/stdout. Stdout carries protocol traffic only --
diagnostics go to stderr. Tool calls are proxied to the FastAPI backend, so this
module stays dependency-free and runs under any interpreter the MCP client picks.
"""
import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any

SERVER_NAME = "signal-workspace"
SERVER_VERSION = "0.1.0"

# Protocol revisions this server understands, newest first.
SUPPORTED_PROTOCOL_VERSIONS = ("2025-06-18", "2025-03-26", "2024-11-05")

API_URL = os.getenv("SIGNAL_API_URL", "http://localhost:8000").rstrip("/")
API_TIMEOUT = float(os.getenv("SIGNAL_API_TIMEOUT", "15"))

PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INTERNAL_ERROR = -32603

TOOLS = [
    {
        "name": "query_workspace",
        "description": "Ask a natural-language question about connected work data (Jira, Asana, Linear).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "The question to answer."},
                "sources": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional connector ids to restrict the query to.",
                },
            },
            "required": ["question"],
        },
    },
    {
        "name": "list_connectors",
        "description": "List connected data sources and their sync status.",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


def log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def call_api(method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
    """Call the backend. Raises RuntimeError with a readable message on failure."""
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(
        f"{API_URL}{path}",
        data=data,
        method=method,
        headers={"Content-Type": "application/json"} if data else {},
    )
    try:
        with urllib.request.urlopen(request, timeout=API_TIMEOUT) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as error:
        raise RuntimeError(f"Backend returned {error.code} for {path}") from error
    except urllib.error.URLError as error:
        raise RuntimeError(f"Backend unreachable at {API_URL} ({error.reason}). Is it running?") from error
    except json.JSONDecodeError as error:
        raise RuntimeError(f"Backend returned a non-JSON response for {path}") from error


def run_tool(name: str, arguments: dict[str, Any]) -> str:
    if name == "query_workspace":
        question = arguments.get("question")
        if not isinstance(question, str) or not question.strip():
            raise ValueError("'question' is required and must be a non-empty string.")
        payload: dict[str, Any] = {"question": question.strip()}
        sources = arguments.get("sources")
        if sources:
            payload["sources"] = sources
        result = call_api("POST", "/api/query", payload)
        lines = [str(result.get("answer", ""))]
        for row in result.get("rows", []):
            lines.append(", ".join(f"{key}: {value}" for key, value in row.items()))
        sources_used = result.get("sources") or []
        if sources_used:
            lines.append(f"Sources: {', '.join(sources_used)}")
        return "\n".join(line for line in lines if line)

    if name == "list_connectors":
        connectors = call_api("GET", "/api/connectors")
        return "\n".join(
            f"{item.get('name')} ({item.get('id')}): {item.get('status')}, "
            f"{item.get('records')} records, synced {item.get('last_sync')}"
            for item in connectors
        )

    raise ValueError(f"Unknown tool: {name}")


def handle_initialize(params: dict[str, Any]) -> dict[str, Any]:
    requested = params.get("protocolVersion")
    version = requested if requested in SUPPORTED_PROTOCOL_VERSIONS else SUPPORTED_PROTOCOL_VERSIONS[0]
    return {
        "protocolVersion": version,
        "capabilities": {"tools": {"listChanged": False}},
        "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
    }


def handle_tools_call(params: dict[str, Any]) -> dict[str, Any]:
    name = params.get("name")
    arguments = params.get("arguments") or {}
    if not isinstance(arguments, dict):
        raise ValueError("'arguments' must be an object.")
    try:
        text = run_tool(name, arguments)
    except (RuntimeError, ValueError) as error:
        # Tool failures are reported in-band so the model can react to them,
        # rather than as protocol-level errors.
        return {"content": [{"type": "text", "text": str(error)}], "isError": True}
    return {"content": [{"type": "text", "text": text}], "isError": False}


def dispatch(method: str, params: dict[str, Any]) -> dict[str, Any]:
    if method == "initialize":
        return handle_initialize(params)
    if method == "tools/list":
        return {"tools": TOOLS}
    if method == "tools/call":
        return handle_tools_call(params)
    if method == "ping":
        return {}
    raise LookupError(method)


def error_response(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def handle_line(line: str) -> dict[str, Any] | None:
    """Return the response to send, or None when the message is a notification."""
    try:
        message = json.loads(line)
    except json.JSONDecodeError:
        return error_response(None, PARSE_ERROR, "Parse error")

    if not isinstance(message, dict):
        return error_response(None, INVALID_REQUEST, "Request must be a JSON object")

    method = message.get("method")
    request_id = message.get("id")
    # No id means a notification: per JSON-RPC, it must never be answered.
    is_notification = "id" not in message

    if not isinstance(method, str):
        return None if is_notification else error_response(request_id, INVALID_REQUEST, "Missing method")

    params = message.get("params") or {}
    if not isinstance(params, dict):
        return None if is_notification else error_response(request_id, INVALID_REQUEST, "'params' must be an object")

    try:
        result = dispatch(method, params)
    except LookupError:
        return None if is_notification else error_response(request_id, METHOD_NOT_FOUND, f"Method not found: {method}")
    except Exception as error:  # noqa: BLE001 - never let one bad message kill the server
        log(f"error handling {method}: {error!r}")
        return None if is_notification else error_response(request_id, INTERNAL_ERROR, str(error))

    if is_notification:
        return None
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def main() -> None:
    log(f"{SERVER_NAME} {SERVER_VERSION} on stdio, backend at {API_URL}")
    for line in sys.stdin:
        if not line.strip():
            continue
        response = handle_line(line)
        if response is not None:
            print(json.dumps(response), flush=True)


if __name__ == "__main__":
    main()
