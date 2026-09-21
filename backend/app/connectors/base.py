from abc import ABC, abstractmethod
from typing import Any

class Connector(ABC):
    id: str
    display_name: str

    @abstractmethod
    async def list_records(self, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    async def health(self) -> dict[str, Any]:
        raise NotImplementedError
