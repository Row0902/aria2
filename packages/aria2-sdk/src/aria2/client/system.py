"""SystemManager — daemon system operations and introspection."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from aria2.client._key_utils import snake_keys
from aria2.models import Aria2Version


class SystemManager:
    """Query daemon version, session info, and available RPC methods.

    Accessed via :attr:`Aria2Client.system`.

    For daemon lifecycle control (shutdown, session save, result cleanup)
    see :class:`DaemonManager` at :attr:`Aria2Client.daemon`.
    """

    def __init__(self, request: Callable[..., Any]) -> None:
        self._request = request

    async def get_version(self) -> Aria2Version:
        """Get aria2 daemon version and enabled features."""
        result = await self._request("aria2.getVersion")
        return Aria2Version.model_validate(snake_keys(result))

    async def get_session_info(self) -> dict[str, str]:
        """Get current session ID."""
        return await self._request("aria2.getSessionInfo")

    async def list_methods(self) -> list[str]:
        """List all available RPC methods."""
        result = await self._request("system.listMethods")
        return [m.replace("aria2.", "", 1) if m.startswith("aria2.") else m for m in result]

    async def list_notifications(self) -> list[str]:
        """List all available RPC notifications."""
        result = await self._request("system.listNotifications")
        return [n.replace("aria2.", "", 1) if n.startswith("aria2.") else n for n in result]
