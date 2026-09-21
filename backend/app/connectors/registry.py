"""Connector registry.

Only configured connectors are registered: with nothing configured the
workspace reports that it is empty rather than inventing sources. Fetched
records are cached briefly so a dashboard load does not hammer the MCP server.
"""
import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from ..settings import Settings
from .base import Connector
from .jira_mcp import JiraMCPConnector

logger = logging.getLogger(__name__)


def build_connectors(settings: Settings) -> dict[str, Connector]:
    connectors: dict[str, Connector] = {}
    if settings.jira_enabled:
        connectors["jira"] = JiraMCPConnector(
            url=settings.jira_mcp_url,
            tool=settings.jira_mcp_tool,
            jql=settings.jira_jql,
            limit=settings.jira_limit,
            site_url=settings.jira_base_url,
            headers=settings.jira_headers,
            timeout=settings.jira_timeout,
        )
    return connectors


@dataclass
class Snapshot:
    """One fetch of every connector. `at` is monotonic for TTL, `synced_at` is wall time."""

    at: float
    synced_at: str
    records: list[dict[str, Any]]
    errors: list[dict[str, str]]


class Workspace:
    """Owns the connector instances and the record cache for one process."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.connectors = build_connectors(settings)
        self._snapshot: Snapshot | None = None
        self._lock = asyncio.Lock()

    def ids(self) -> list[str]:
        return list(self.connectors)

    async def describe(self) -> list[dict[str, Any]]:
        """Report each connector's real health, plus what it currently holds."""
        records, _ = await self.records()
        counts: dict[str, int] = {}
        for record in records:
            source = str(record.get("source", ""))
            counts[source] = counts.get(source, 0) + 1

        described = []
        for connector in self.connectors.values():
            health = await connector.health()
            described.append(
                {
                    "id": connector.id,
                    "name": connector.display_name,
                    "status": health.get("status", "unknown"),
                    "detail": health.get("detail"),
                    "records": counts.get(connector.id, 0),
                    "last_sync": self.last_sync_iso(),
                }
            )
        return described

    def last_sync_iso(self) -> str | None:
        return self._snapshot.synced_at if self._snapshot else None

    async def _fetch(self) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
        records: list[dict[str, Any]] = []
        errors: list[dict[str, str]] = []
        for connector in self.connectors.values():
            try:
                records.extend(await connector.list_records())
            except Exception as error:  # one broken source must not blank the dashboard
                logger.warning("connector %s failed: %r", connector.id, error)
                errors.append({"source": connector.id, "message": str(error)})
        return records, errors

    async def records(self, refresh: bool = False) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
        async with self._lock:
            now = time.monotonic()
            cached = self._snapshot
            if not refresh and cached and now - cached.at < self.settings.records_cache_ttl:
                return cached.records, cached.errors
            records, errors = await self._fetch()
            # Keep serving the last good snapshot if a refresh failed outright.
            if not records and errors and cached:
                return cached.records, errors
            self._snapshot = Snapshot(
                at=now,
                synced_at=datetime.now(timezone.utc).isoformat(),
                records=records,
                errors=errors,
            )
            return records, errors
