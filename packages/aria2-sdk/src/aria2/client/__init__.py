"""Aria2Client — async JSON-RPC client for the aria2 download daemon.

Connects to a running aria2c instance via its JSON-RPC interface.
Uses WebSocket as the primary transport with automatic HTTP fallback.

Usage::

    async with Aria2Client(secret="token") as client:
        gid = await client.downloads.add_uri(["https://example.com/file.zip"])
        status = await client.status.tell_status(gid)
        ver = await client.system.get_version()

Event callbacks (WebSocket only)::

    def on_start(gid: str) -> None:
        print(f"Download started: {gid}")


    client.events.on_download_start(on_start)

Sub-managers (each ≤ 10 public methods):

    - :attr:`downloads` — add, remove, pause, control downloads
    - :attr:`status` — query download status, files, peers
    - :attr:`options` — get/set per-download and global options
    - :attr:`system` — daemon version, session, shutdown
    - :attr:`events` — WebSocket event callback registration
"""

from __future__ import annotations

from contextlib import suppress
from typing import Any

from aria2.client.download import DownloadManager
from aria2.client.events import EventManager
from aria2.client.options import OptionsManager
from aria2.client.status import StatusManager
from aria2.client.system import SystemManager
from aria2.client.transport.http import HttpTransport
from aria2.client.transport.ws import WebSocketTransport
from aria2.errors import Aria2ConnectionError

# Event name to method name mapping (without "aria2." prefix)
_EVENT_MAP: dict[str, str] = {
    "onDownloadStart": "aria2.onDownloadStart",
    "onDownloadPause": "aria2.onDownloadPause",
    "onDownloadStop": "aria2.onDownloadStop",
    "onDownloadComplete": "aria2.onDownloadComplete",
    "onDownloadError": "aria2.onDownloadError",
    "onBtDownloadComplete": "aria2.onBtDownloadComplete",
}


class Aria2Client:
    """Async JSON-RPC client for the aria2 download daemon.

    The client is an async context manager.  All domain operations are
    delegated to sub-managers exposed as properties.

    Usage::

        async with Aria2Client(secret="token") as client:
            gid = await client.downloads.add_uri(["https://example.com/file.zip"])
            status = await client.status.tell_status(gid)
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6800,
        secret: str | None = None,
        *,
        enable_ws: bool = True,
        timeout: float = 30.0,
    ) -> None:
        self._host = host
        self._port = port
        self._secret = secret
        self._timeout = timeout

        self._http = HttpTransport(host, port, secret, timeout=timeout)
        self._ws = self._init_ws_transport(host, port, secret, timeout, enable_ws)

        self._callbacks = {name: [] for name in _EVENT_MAP}

        self._downloads = DownloadManager(self._request, self._secret)
        self._status = StatusManager(self._request)
        self._options = OptionsManager(self._request)
        self._system = SystemManager(self._request, self._secret)
        self._events = EventManager(self._callbacks)

    def _init_ws_transport(
        self, host: str, port: int, secret: str | None, timeout: float, enable: bool
    ) -> WebSocketTransport | None:
        if enable:
            return WebSocketTransport(
                host, port, secret, timeout=timeout, event_callback=self._on_event
            )
        return None

    # ── Sub-manager properties ──────────────────────────────

    @property
    def downloads(self) -> DownloadManager:
        """Add, remove, pause, and control downloads."""
        return self._downloads

    @property
    def status(self) -> StatusManager:
        """Query download status, files, peers, and server info."""
        return self._status

    @property
    def options(self) -> OptionsManager:
        """Get and change per-download and global options."""
        return self._options

    @property
    def system(self) -> SystemManager:
        """Query daemon version, session, and control lifecycle."""
        return self._system

    @property
    def events(self) -> EventManager:
        """Register WebSocket event callbacks."""
        return self._events

    # ── Lifecycle ────────────────────────────────────────────

    async def connect(self) -> None:
        """Open connections to the aria2 RPC server.

        HTTP always connects. WebSocket connects on best-effort basis;
        failure degrades silently to HTTP-only.
        """
        await self._http.connect()
        if self._ws is not None:
            with suppress(Aria2ConnectionError):
                await self._ws.connect()  # degrade to HTTP

    async def close(self) -> None:
        """Close all connections."""
        if self._ws is not None:
            await self._ws.close()
        await self._http.close()

    async def __aenter__(self) -> Aria2Client:
        await self.connect()
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.close()

    # ── Internal request dispatch ────────────────────────────

    async def _request(
        self,
        method: str,
        params: list[Any] | None = None,
        *,
        add_secret: bool = True,
    ) -> Any:
        """Send a JSON-RPC request via the best available transport.

        Prefers WebSocket if connected, falls back to HTTP.
        """
        if params is None:
            params = []

        if self._ws is not None and self._ws.is_connected:
            return await self._ws.send_request(method, params, add_secret=add_secret)
        return await self._http.send_request(method, params, add_secret=add_secret)

    def _on_event(self, method: str, params: list[Any]) -> None:
        """Dispatch incoming WebSocket notifications to registered callbacks."""
        for short_name, full_name in _EVENT_MAP.items():
            if method == full_name:
                for cb in self._callbacks[short_name]:
                    cb(*params)
                return
