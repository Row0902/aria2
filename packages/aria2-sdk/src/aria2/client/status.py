"""StatusManager — query download status and metadata."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from aria2.client._key_utils import snake_keys
from aria2.models import (
    DownloadStatusResponse,
    FileInfo,
    GlobalStat,
    PeerInfo,
    ServerInfo,
    UriInfo,
    _parse_status,
)


class StatusManager:
    """Retrieve download status, files, peers, and server info.

    Accessed via :attr:`Aria2Client.status`.
    """

    def __init__(self, request: Callable[..., Any]) -> None:
        self._request = request

    async def tell_status(
        self,
        gid: str,
        keys: list[str] | None = None,
    ) -> DownloadStatusResponse:
        """Get status of a download by GID."""
        params: list[Any] = [gid]
        if keys is not None:
            params.append(keys)
        result = await self._request("aria2.tellStatus", params)
        return _parse_status(snake_keys(result))

    async def tell_active(
        self,
        keys: list[str] | None = None,
    ) -> list[DownloadStatusResponse]:
        """Get all active downloads."""
        params: list[Any] = []
        if keys is not None:
            params.append(keys)
        result = await self._request("aria2.tellActive", params)
        return [_parse_status(snake_keys(item)) for item in result]

    async def tell_waiting(
        self,
        offset: int = 0,
        num: int = 100,
        keys: list[str] | None = None,
    ) -> list[DownloadStatusResponse]:
        """Get waiting downloads."""
        params: list[Any] = [offset, num]
        if keys is not None:
            params.append(keys)
        result = await self._request("aria2.tellWaiting", params)
        return [_parse_status(snake_keys(item)) for item in result]

    async def tell_stopped(
        self,
        offset: int = 0,
        num: int = 100,
        keys: list[str] | None = None,
    ) -> list[DownloadStatusResponse]:
        """Get stopped downloads."""
        params: list[Any] = [offset, num]
        if keys is not None:
            params.append(keys)
        result = await self._request("aria2.tellStopped", params)
        return [_parse_status(snake_keys(item)) for item in result]

    async def get_files(self, gid: str) -> list[FileInfo]:
        """Get file list for a download."""
        result = await self._request("aria2.getFiles", [gid])
        return [FileInfo.model_validate(snake_keys(item)) for item in result]

    async def get_uris(self, gid: str) -> list[UriInfo]:
        """Get URI list for a download."""
        result = await self._request("aria2.getUris", [gid])
        return [UriInfo.model_validate(snake_keys(item)) for item in result]

    async def get_servers(self, gid: str) -> list[ServerInfo]:
        """Get server connections for a download."""
        result = await self._request("aria2.getServers", [gid])
        return [ServerInfo.model_validate(snake_keys(item)) for item in result]

    async def get_peers(self, gid: str) -> list[PeerInfo]:
        """Get BitTorrent peers for a download."""
        result = await self._request("aria2.getPeers", [gid])
        return [PeerInfo.model_validate(snake_keys(item)) for item in result]

    async def get_global_stat(self) -> GlobalStat:
        """Get global daemon statistics."""
        result = await self._request("aria2.getGlobalStat")
        return GlobalStat.model_validate(snake_keys(result))
