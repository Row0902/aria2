"""OptionsManager — get and change download and global options."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


class OptionsManager:
    """Manage per-download and global aria2 options.

    Accessed via :attr:`Aria2Client.options`.
    """

    def __init__(self, request: Callable[..., Any]) -> None:
        self._request = request

    async def get_option(self, gid: str) -> dict[str, str]:
        """Get current options for a specific download."""
        return await self._request("aria2.getOption", [gid])

    async def change_option(self, gid: str, options: dict[str, str]) -> str:
        """Change options for a specific download."""
        return await self._request("aria2.changeOption", [gid, options])

    async def get_global_option(self) -> dict[str, str]:
        """Get current global daemon options."""
        return await self._request("aria2.getGlobalOption")

    async def change_global_option(self, options: dict[str, str]) -> str:
        """Change global daemon options."""
        return await self._request("aria2.changeGlobalOption", [options])
