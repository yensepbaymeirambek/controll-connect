"""A stand-in Jira MCP server for running the stack without Jira credentials.

Serves a `jira_search` tool over streamable HTTP, returning issues in the nested
shape the Jira REST API uses. Data is generated from a fixed seed, so counts are
stable between runs, and dates are relative to now so overdue and weekly-trend
logic actually gets exercised.

    python -m dev.fake_jira_mcp        # listens on :9100/mcp
"""
import random
from datetime import datetime, timedelta, timezone
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings

PROJECTS = [("PLAT", "Platform"), ("WEB", "Frontend"), ("GRW", "Growth")]
ASSIGNEES = ["Alex Morgan", "Priya Nair", "Tom Okafor", "Lena Fischer", "Sam Reyes", None]
TYPES = ["Bug", "Story", "Task"]
PRIORITIES = ["Highest", "High", "Medium", "Low"]
STATUSES = [
    ("To Do", "new"),
    ("In Progress", "indeterminate"),
    ("In Review", "indeterminate"),
    ("Done", "done"),
]


def _build_issues(count: int = 64) -> list[dict[str, Any]]:
    rng = random.Random(20260921)
    now = datetime.now(timezone.utc)
    issues = []
    for index in range(count):
        key_prefix, project_name = rng.choice(PROJECTS)
        status_name, category = rng.choice(STATUSES)
        created = now - timedelta(days=rng.randint(0, 55), hours=rng.randint(0, 23))
        updated = created + timedelta(days=rng.randint(0, 12))
        due = None
        if rng.random() < 0.55:
            due = (created + timedelta(days=rng.randint(3, 40))).date().isoformat()
        assignee = rng.choice(ASSIGNEES)
        issues.append(
            {
                "key": f"{key_prefix}-{100 + index}",
                "self": f"https://example.atlassian.net/browse/{key_prefix}-{100 + index}",
                "fields": {
                    "summary": f"{rng.choice(['Fix', 'Add', 'Investigate', 'Refactor', 'Document'])} "
                    f"{rng.choice(['sync retries', 'export pipeline', 'auth flow', 'rate limiting', 'webhook parser', 'chart rendering'])}",
                    "status": {"name": status_name, "statusCategory": {"key": category, "name": status_name}},
                    "assignee": {"displayName": assignee} if assignee else None,
                    "project": {"key": key_prefix, "name": project_name},
                    "issuetype": {"name": rng.choice(TYPES)},
                    "priority": {"name": rng.choice(PRIORITIES)},
                    "created": created.isoformat(),
                    "updated": min(updated, now).isoformat(),
                    "duedate": due,
                },
            }
        )
    return issues


ISSUES = _build_issues()

mcp = MCPServer(name="fake-jira", instructions="Test double for a Jira MCP server.")


@mcp.tool(description="Search Jira issues with JQL.")
def jira_search(jql: str = "", limit: int = 50) -> dict[str, Any]:
    """Only the ORDER BY direction and project filter are honoured; enough to prove the wiring."""
    issues = list(ISSUES)
    lowered = jql.lower()
    for key, _ in PROJECTS:
        if f"project = {key.lower()}" in lowered:
            issues = [issue for issue in issues if issue["fields"]["project"]["key"] == key]
    if "order by created" in lowered:
        issues.sort(key=lambda issue: issue["fields"]["created"], reverse="desc" in lowered)
    return {"issues": issues[: max(1, limit)], "total": len(issues)}


if __name__ == "__main__":
    mcp.run(
        transport="streamable-http",
        host="0.0.0.0",
        port=9100,
        stateless_http=True,
        # Reached only over the internal compose network, and the container name
        # in the Host header trips the default DNS-rebinding guard.
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    )
