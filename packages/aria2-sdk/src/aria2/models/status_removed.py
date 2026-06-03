"""Removed download status — a download that was removed by the user."""

from __future__ import annotations

from aria2.models.base import _BaseDownloadStatus
from aria2.types import DownloadStatus


class RemovedStatus(_BaseDownloadStatus):
    """A download that was removed by the user."""

    status: DownloadStatus = DownloadStatus.REMOVED


__all__ = [
    "RemovedStatus",
]
