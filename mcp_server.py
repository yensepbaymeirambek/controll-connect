"""Minimal stdio MCP-compatible entry point for the workspace."""
import json
import sys


def main() -> None:
    for line in sys.stdin:
        request = json.loads(line)
        method = request.get("method")
        if method == "tools/list":
            result = {"tools": [{"name": "query_workspace", "description": "Query connected work data", "inputSchema": {"type": "object", "properties": {"question": {"type": "string"}}, "required": ["question"]}}]}
        elif method == "tools/call":
            result = {"content": [{"type": "text", "text": "Local MCP mode: connect provider credentials to query live data."}]}
        else:
            result = {"error": {"code": -32601, "message": "Method not found"}}
        print(json.dumps({"jsonrpc": "2.0", "id": request.get("id"), "result": result}), flush=True)


if __name__ == "__main__":
    main()
