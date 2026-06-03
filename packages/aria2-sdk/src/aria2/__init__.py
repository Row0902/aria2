"""aria2 — async JSON-RPC SDK for the aria2 download manager."""

from __future__ import annotations

from aria2.client import Aria2Client
from aria2.errors import Aria2ConnectionError, Aria2Error, Aria2RpcError
from aria2.models import (
    ActiveStatus,
    Aria2Version,
    CompleteStatus,
    DownloadStatusResponse,
    ErrorStatus,
    FileInfo,
    GlobalStat,
    PausedStatus,
    RemovedStatus,
    UriInfo,
)
from aria2.types import GID, DownloadStatus, PositionHow, StatusType

__all__ = [
    "GID",
    "ActiveStatus",
    "Aria2Client",
    "Aria2ConnectionError",
    "Aria2Error",
    "Aria2RpcError",
    "Aria2Version",
    "CompleteStatus",
    "DownloadStatus",
    "DownloadStatusResponse",
    "ErrorStatus",
    "FileInfo",
    "GlobalStat",
    "PausedStatus",
    "PositionHow",
    "RemovedStatus",
    "StatusType",
    "UriInfo",
]
