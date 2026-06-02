"""URI information for a file within a download."""

from __future__ import annotations

from pydantic import BaseModel


class UriInfo(BaseModel):
    """A URI associated with a file in a download."""

    uri: str
    status: str  # "used" or "waiting"


__all__ = [
    "UriInfo",
]
