"""BitTorrent metadata for a download."""

from __future__ import annotations

from pydantic import BaseModel


class BittorrentInfo(BaseModel):
    """BitTorrent metadata for a download."""

    announce_list: list[list[str]] = []
    comment: str = ""
    creation_date: str = "0"
    mode: str = ""
    info: dict[str, str] = {}


__all__ = [
    "BittorrentInfo",
]
