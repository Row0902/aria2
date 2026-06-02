"""Active download status — a download that is currently running or queued."""

from __future__ import annotations

from aria2.models.base import _BaseDownloadStatus
from aria2.models.bittorrent import BittorrentInfo
from aria2.types import DownloadStatus


class ActiveStatus(_BaseDownloadStatus):
    """A download that is currently running or queued."""

    status: DownloadStatus = DownloadStatus.ACTIVE
    bitfield: str = ""
    connections: str = "0"
    info_hash: str = ""
    num_seeders: str = "0"
    seeder: str = "false"
    bittorrent: BittorrentInfo | None = None
    verified_length: str = "0"
    verify_integrity_pending: str = "false"

    @property
    def is_active(self) -> bool:
        return True


__all__ = [
    "ActiveStatus",
]
