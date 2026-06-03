"""Error download status — a download that ended with an error."""

from __future__ import annotations

from aria2.models.base import _BaseDownloadStatus
from aria2.types import DownloadStatus


class ErrorStatus(_BaseDownloadStatus):
    """A download that ended with an error."""

    status: DownloadStatus = DownloadStatus.ERROR
    error_code: str = ""
    error_message: str = ""


__all__ = [
    "ErrorStatus",
]
