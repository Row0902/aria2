"""SystemManager — daemon system operations and introspection."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from aria2.client._helpers import snake_keys
from aria2.models import Aria2Version


class SystemManager:
    """Query daemon version, session info, and control daemon lifecycle.

    Accessed via :attr:`Aria2Client.system`.
    """

    def __init__(self, request: Callable[..., Any], secret: str | None) -> None:
        self._request = request
        self._secret = secret

    async def get_version(self) -> Aria2Version:
        """Get aria2 daemon version and enabled features."""
        result = await self._request("aria2.getVersion")
        return Aria2Version.model_validate(snake_keys(result))

    async def get_session_info(self) -> dict[str, str]:
        """Get current session ID."""
        return await self._request("aria2.getSessionInfo")

    async def shutdown(self, force: bool = False) -> str:
        """Shut down the aria2 daemon."""
        method = "aria2.forceShutdown" if force else "aria2.shutdown"
        return await self._request(method)

    async def save_session(self) -> str:
        """Save current session to the configured session file."""
        return await self._request("aria2.saveSession")

    async def purge_download_result(self) -> str:
        """Remove all completed/error/removed download results."""
        return await self._request("aria2.purgeDownloadResult")

    async def remove_download_result(self, gid: str) -> str:
        """Remove a single completed/removed download result."""
        return await self._request("aria2.removeDownloadResult", [gid])

    async def list_methods(self) -> list[str]:
        """List all available RPC methods."""
        result = await self._request("system.listMethods")
        return [m.replace("aria2.", "", 1) if m.startswith("aria2.") else m for m in result]

    async def list_notifications(self) -> list[str]:
        """List all available RPC notifications."""
        result = await self._request("system.listNotifications")
        return [n.replace("aria2.", "", 1) if n.startswith("aria2.") else n for n in result]

    async def multicall(self, calls: list[dict[str, Any]]) -> list[Any]:
        """Execute multiple RPC calls in a single request.

        ``system.multicall`` requires the secret token to be embedded
        inside *each* sub-call's ``params`` array, not at the top-level
        request params.
        """
        if self._secret:
            calls = [
                {
                    "methodName": call["methodName"],
                    "params": [f"token:{self._secret}", *call.get("params", [])],
                }
                for call in calls
            ]
        return await self._request("system.multicall", [calls], add_secret=False)
