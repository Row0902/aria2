"""Complete download status — a successfully completed download."""

from __future__ import annotations

from aria2.models.base import _BaseDownloadStatus
from aria2.models.bittorrent import BittorrentInfo
from aria2.types import DownloadStatus


class CompleteStatus(_BaseDownloadStatus):
    """A successfully completed download."""

    status: DownloadStatus = DownloadStatus.COMPLETE
    bittorrent: BittorrentInfo | None = None


__all__ = [
    "CompleteStatus",
]
