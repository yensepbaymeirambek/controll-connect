"""Jira connector backed by an MCP server (e.g. mcp-atlassian).

Nothing here is Jira-API specific: issues arrive as whatever JSON the MCP server
emits, and are normalized into the workspace record shape. Servers differ on
whether fields sit at the top level or under `fields`, so lookups try both.
"""
import logging
from typing import Any

from ..mcp_client import MCPError, call_tool, list_tools
from .base import Connector

logger = logging.getLogger(__name__)

# Jira's statusCategory keys, mapped to the states the dashboard aggregates on.
_CATEGORY_STATES = {"new": "todo", "indeterminate": "in_progress", "done": "done"}
_DONE_HINTS = ("done", "closed", "resolved", "complete", "shipped")
_PROGRESS_HINTS = ("progress", "review", "testing", "qa", "doing")


def _first(source: dict[str, Any], *paths: str) -> Any:
    """Look up dotted paths in order, returning the first non-empty value."""
    for path in paths:
        value: Any = source
        for part in path.split("."):
            if not isinstance(value, dict):
                value = None
                break
            value = value.get(part)
        if value not in (None, "", [], {}):
            return value
    return None


def _label(value: Any) -> str | None:
    """Jira fields arrive either as a string or as an object with a name."""
    if isinstance(value, str):
        return value or None
    if isinstance(value, dict):
        for key in ("displayName", "name", "value", "key"):
            label = value.get(key)
            if isinstance(label, str) and label:
                return label
    return None


def _derive_state(issue: dict[str, Any], status: str | None) -> str:
    category = _label(
        _first(issue, "status.statusCategory", "fields.status.statusCategory", "statusCategory")
    )
    if category:
        mapped = _CATEGORY_STATES.get(category.strip().lower().replace(" ", "_"))
        if mapped:
            return mapped
        lowered = category.lower()
        if any(hint in lowered for hint in _DONE_HINTS):
            return "done"
        if any(hint in lowered for hint in _PROGRESS_HINTS):
            return "in_progress"
    lowered = (status or "").lower()
    if any(hint in lowered for hint in _DONE_HINTS):
        return "done"
    if any(hint in lowered for hint in _PROGRESS_HINTS):
        return "in_progress"
    return "todo"


def _extract_issues(payload: Any) -> list[dict[str, Any]]:
    """Find the issue list inside whatever envelope the server returned."""
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("issues", "results", "items", "data", "records"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        if payload.get("key") or payload.get("id"):
            return [payload]
    return []


class JiraMCPConnector(Connector):
    id = "jira"
    display_name = "Jira"

    def __init__(
        self,
        url: str,
        tool: str,
        jql: str,
        limit: int,
        site_url: str = "",
        headers: dict[str, str] | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.url = url
        self.tool = tool
        self.jql = jql
        self.limit = limit
        self.site_url = site_url.rstrip("/")
        self.headers = headers or {}
        self.timeout = timeout

    def _normalize(self, issue: dict[str, Any]) -> dict[str, Any]:
        key = _first(issue, "key", "id", "issueKey", "fields.key")
        status = _label(_first(issue, "status", "fields.status"))
        return {
            "source": self.id,
            "id": str(key) if key is not None else "",
            "title": _first(issue, "summary", "fields.summary", "title") or "(no summary)",
            "status": status or "Unknown",
            "state": _derive_state(issue, status),
            "assignee": _label(_first(issue, "assignee", "fields.assignee")) or "Unassigned",
            "project": _label(_first(issue, "project", "fields.project")) or None,
            "type": _label(_first(issue, "issuetype", "issue_type", "fields.issuetype", "type")) or None,
            "priority": _label(_first(issue, "priority", "fields.priority")) or None,
            "created": _first(issue, "created", "fields.created", "createdAt"),
            "updated": _first(issue, "updated", "fields.updated", "updatedAt"),
            "due": _first(issue, "duedate", "fields.duedate", "due_date", "dueDate"),
            "url": _first(issue, "url", "self", "browseUrl")
            or (f"{self.site_url}/browse/{key}" if self.site_url and key else None),
        }

    async def list_records(self, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        filters = filters or {}
        payload = await call_tool(
            self.url,
            self.tool,
            {
                "jql": filters.get("jql") or self.jql,
                "limit": int(filters.get("limit") or self.limit),
            },
            headers=self.headers,
            timeout=self.timeout,
        )
        issues = _extract_issues(payload)
        if not issues:
            logger.info("MCP tool %s returned no issues", self.tool)
        return [self._normalize(issue) for issue in issues]

    async def health(self) -> dict[str, Any]:
        try:
            tools = await list_tools(self.url, headers=self.headers, timeout=self.timeout)
        except MCPError as error:
            return {"id": self.id, "status": "error", "configured": True, "detail": str(error)}
        if self.tool not in tools:
            return {
                "id": self.id,
                "status": "error",
                "configured": True,
                "detail": f"MCP server has no tool '{self.tool}'. Available: {', '.join(sorted(tools)) or 'none'}",
            }
        return {"id": self.id, "status": "connected", "configured": True, "detail": None}
