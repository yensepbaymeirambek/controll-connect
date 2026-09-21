from typing import Any
from .base import Connector

class MockConnector(Connector):
    def __init__(self, connector_id: str, display_name: str) -> None:
        self.id = connector_id
        self.display_name = display_name

    async def list_records(self, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        return [{"id": "demo-1", "title": "Connect credentials to load live data", "status": "todo"}]

    async def health(self) -> dict[str, Any]:
        return {"id": self.id, "status": "mock", "configured": False}
