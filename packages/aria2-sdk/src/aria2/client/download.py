"""DownloadManager — add, remove, pause, and control downloads."""

from __future__ import annotations

import base64
from collections.abc import Callable
from typing import Any


def _build_torrent_params(
    b64: str,
    uris: list[str] | None,
    options: dict[str, str] | None,
    position: int | None,
) -> list[Any]:
    """Build RPC params array for aria2.addTorrent."""
    params: list[Any] = [b64]
    has_uris = uris is not None
    if has_uris:
        params.append(uris)
    if options is not None:
        params.append(options)
    if position is not None:
        if has_uris and options is None:
            params.append([])  # placeholder for skipped options slot
        params.append(position)
    return params


def _build_metalink_params(
    b64: str,
    options: dict[str, str] | None,
    position: int | None,
) -> list[Any]:
    """Build RPC params array for ``aria2.addMetalink``."""
    params: list[Any] = [b64]
    if options is not None:
        params.append(options)
    if position is not None:
        params.append(position)
    return params


class DownloadManager:
    """Manage download lifecycle — add, remove, pause, resume, reorder.

    Accessed via :attr:`Aria2Client.downloads`.
    """

    def __init__(self, request: Callable[..., Any], secret: str | None) -> None:
        self._request = request
        self._secret = secret

    # ── Add ─────────────────────────────────────────────────

    async def add_uri(
        self,
        uris: list[str],
        options: dict[str, str] | None = None,
        position: int | None = None,
    ) -> str:
        """Add a download by URI."""
        params: list[Any] = [uris]
        if options is not None:
            params.append(options)
            if position is not None:
                params.append(position)
        elif position is not None:
            params.append({})
            params.append(position)
        return await self._request("aria2.addUri", params)

    async def add_torrent(
        self,
        torrent: bytes,
        uris: list[str] | None = None,
        options: dict[str, str] | None = None,
        position: int | None = None,
    ) -> str:
        """Add a download by torrent file."""
        b64 = base64.b64encode(torrent).decode("ascii")
        params = _build_torrent_params(b64, uris, options, position)
        return await self._request("aria2.addTorrent", params)

    async def add_metalink(
        self,
        metalink: bytes,
        options: dict[str, str] | None = None,
        position: int | None = None,
    ) -> list[str]:
        """Add a Metalink download.

        Returns a list of GIDs — one per file in the Metalink.
        """
        b64 = base64.b64encode(metalink).decode("ascii")
        params = _build_metalink_params(b64, options, position)
        return await self._request("aria2.addMetalink", params)

    # ── Control ─────────────────────────────────────────────

    async def remove(self, gid: str, force: bool = False) -> str:
        """Remove a download (active or waiting)."""
        method = "aria2.forceRemove" if force else "aria2.remove"
        return await self._request(method, [gid])

    async def pause(self, gid: str, force: bool = False) -> str:
        """Pause an active download."""
        method = "aria2.forcePause" if force else "aria2.pause"
        return await self._request(method, [gid])

    async def pause_all(self, force: bool = False) -> str:
        """Pause all active downloads."""
        method = "aria2.forcePauseAll" if force else "aria2.pauseAll"
        return await self._request(method)

    async def unpause(self, gid: str) -> str:
        """Resume a paused download."""
        return await self._request("aria2.unpause", [gid])

    async def unpause_all(self) -> str:
        """Resume all paused downloads."""
        return await self._request("aria2.unpauseAll")

    async def change_position(self, gid: str, pos: int, how: str = "POS_SET") -> int:
        """Change the position of a download in the queue."""
        result = await self._request("aria2.changePosition", [gid, pos, how])
        return int(result)
