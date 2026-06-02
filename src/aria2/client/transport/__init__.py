"""Abstract transport interface for aria2 RPC communication."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class Transport(ABC):
    """Abstract base class for RPC transport implementations."""

    @abstractmethod
    async def connect(self) -> None:
        """Establish a connection to the RPC server."""

    @abstractmethod
    async def send_request(self, method: str, params: list[Any]) -> Any:
        """Send a JSON-RPC request and return the result."""

    @abstractmethod
    async def close(self) -> None:
        """Close the connection."""

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """Whether the transport has an active connection."""
