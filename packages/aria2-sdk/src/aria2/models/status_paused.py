"""Paused download status — a download that has been paused."""

from __future__ import annotations

from aria2.models.base import _BaseDownloadStatus
from aria2.types import DownloadStatus


class PausedStatus(_BaseDownloadStatus):
    """A download that has been paused."""

    status: DownloadStatus = DownloadStatus.PAUSED
    bitfield: str = ""
    connections: str = "0"

    @property
    def is_active(self) -> bool:
        return False


__all__ = [
    "PausedStatus",
]
