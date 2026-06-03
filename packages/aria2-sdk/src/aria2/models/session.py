"""Current session information."""

from __future__ import annotations

from pydantic import BaseModel


class SessionInfo(BaseModel):
    """Current session information."""

    session_id: str = ""


__all__ = [
    "SessionInfo",
]
