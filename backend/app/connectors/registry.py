"""Single place where connector instances and their sync metadata live.

Adapters are mock implementations until credentials land; swapping one for a
real adapter means changing only the instance registered here.
"""
from typing import Any

from .base import Connector
from .mock import MockConnector

_REGISTRY: dict[str, Connector] = {
    "jira": MockConnector("jira", "Jira Software"),
    "asana": MockConnector("asana", "Asana"),
    "linear": MockConnector("linear", "Linear"),
}

# Sync stats are presentation metadata, not part of the Connector contract.
_SYNC_META: dict[str, dict[str, Any]] = {
    "jira": {"status": "connected", "last_sync": "12 min ago", "records": 1248},
    "asana": {"status": "connected", "last_sync": "18 min ago", "records": 863},
    "linear": {"status": "connected", "last_sync": "1 hr ago", "records": 421},
}


def connector_ids() -> list[str]:
    return list(_REGISTRY)


def get_connector(connector_id: str) -> Connector | None:
    return _REGISTRY.get(connector_id)


def describe_connectors() -> list[dict[str, Any]]:
    return [
        {"id": connector.id, "name": connector.display_name, **_SYNC_META.get(connector.id, {})}
        for connector in _REGISTRY.values()
    ]


async def collect_records(source_ids: list[str] | None = None) -> list[dict[str, Any]]:
    """Fetch records from the requested connectors, tagged with their source."""
    selected = source_ids or connector_ids()
    records: list[dict[str, Any]] = []
    for connector_id in selected:
        connector = get_connector(connector_id)
        if connector is None:
            continue
        for record in await connector.list_records():
            records.append({"source": connector_id, **record})
    return records
