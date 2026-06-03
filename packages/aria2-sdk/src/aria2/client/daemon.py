"""DaemonManager — daemon lifecycle control (shutdown, session, cleanup).

Accessed via :attr:`Aria2Client.daemon`.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


class DaemonManager:
    """Control daemon lifecycle — shutdown, session persistence, result cleanup.

    Accessed via :attr:`Aria2Client.daemon`.
    """

    def __init__(self, request: Callable[..., Any], secret: str | None) -> None:
        self._request = request
        self._secret = secret

    async def shutdown(self, force: bool = False) -> str:
        """Shut down the aria2 daemon.

        Args:
            force: If True, uses ``aria2.forceShutdown`` (immediate).

        """
        method = "aria2.forceShutdown" if force else "aria2.shutdown"
        return await self._request(method)

    async def save_session(self) -> str:
        """Save current session to the configured session file."""
        return await self._request("aria2.saveSession")

    async def purge_download_result(self) -> str:
        """Remove all completed/error/removed download results."""
        return await self._request("aria2.purgeDownloadResult")

    async def remove_download_result(self, gid: str) -> str:
        """Remove a single completed/removed download result by GID."""
        return await self._request("aria2.removeDownloadResult", [gid])


__all__ = [
    "DaemonManager",
]
