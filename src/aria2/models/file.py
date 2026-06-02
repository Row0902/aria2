"""File information for a download."""

from __future__ import annotations

from pydantic import BaseModel

from aria2.models.uri import UriInfo


class FileInfo(BaseModel):
    """Information about a file within a download."""

    index: str
    path: str
    length: str
    completed_length: str
    selected: str
    uris: list[UriInfo] = []

    @property
    def length_bytes(self) -> int:
        return int(self.length)

    @property
    def completed_bytes(self) -> int:
        return int(self.completed_length)

    @property
    def is_selected(self) -> bool:
        return self.selected == "true"


__all__ = [
    "FileInfo",
]
