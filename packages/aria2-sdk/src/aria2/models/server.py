"""Server connection information."""

from __future__ import annotations

from pydantic import BaseModel


class ServerInfo(BaseModel):
    """Information about a connected server."""

    index: str
    servers: list[dict[str, str]] = []


__all__ = [
    "ServerInfo",
]
