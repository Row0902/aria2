"""Aria2 version information."""

from __future__ import annotations

from pydantic import BaseModel


class Aria2Version(BaseModel):
    """Aria2 version information."""

    version: str = ""
    enabled_features: list[str] = []


__all__ = [
    "Aria2Version",
]
