"""Pydantic models for aria2 JSON-RPC responses — with discriminated unions.

Each download status variant has its own model, selected at parse time
via the ``status`` field discriminator.  Use ``DownloadStatusResponse``
(which is a Union) to catch all variants.
"""

from __future__ import annotations

from aria2.models.bittorrent import BittorrentInfo
from aria2.models.download_response import (
    DownloadStatusResponse,
    _parse_status,
)
from aria2.models.file import FileInfo
from aria2.models.global_stat import GlobalStat
from aria2.models.peer import PeerInfo
from aria2.models.server import ServerInfo
from aria2.models.session import SessionInfo
from aria2.models.status_active import ActiveStatus
from aria2.models.status_complete import CompleteStatus
from aria2.models.status_error import ErrorStatus
from aria2.models.status_paused import PausedStatus
from aria2.models.status_removed import RemovedStatus
from aria2.models.uri import UriInfo
from aria2.models.version import Aria2Version

__all__ = [
    "ActiveStatus",
    "Aria2Version",
    "BittorrentInfo",
    "CompleteStatus",
    "DownloadStatusResponse",
    "ErrorStatus",
    "FileInfo",
    "GlobalStat",
    "PausedStatus",
    "PeerInfo",
    "RemovedStatus",
    "ServerInfo",
    "SessionInfo",
    "UriInfo",
]
