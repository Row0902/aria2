"""WebSocket transport for aria2 JSON-RPC with event dispatch."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from contextlib import suppress
from typing import Any

from websockets.asyncio.client import connect as ws_connect

from aria2.client.transport import Transport
from aria2.client.transport.ws._pending import _PendingRequestManager
from aria2.client.transport.ws._reader import _WsReader
from aria2.errors import Aria2ConnectionError
from aria2.rpc import build_request as _build_noauth
from aria2.rpc import build_request_with_secret as _build


def _build_url(host: str, port: int) -> str:
    """Build a WebSocket URL from host and port."""
    return f"ws://{host}:{port}/jsonrpc"


class WebSocketTransport(Transport):
    """JSON-RPC over WebSocket via ``websockets`` library."""

    def __init__(
        self,
        host: str,
        port: int,
        secret: str | None = None,
        *,
        timeout: float = 30.0,
        event_callback: Callable[[str, list[Any]], None] | None = None,
        reconnect_delay: float = 1.0,
        max_reconnect_delay: float = 30.0,
    ) -> None:
        self._host = host
        self._port = port
        self._secret = secret
        self._timeout = timeout
        self._event_callback = event_callback
        self._init_internal_state(reconnect_delay, max_reconnect_delay)

    def _init_internal_state(
        self, reconnect_delay: float, max_reconnect_delay: float
    ) -> None:
        """Initialise mutable transport state."""
        self._reconnect_delay = reconnect_delay
        self._max_reconnect_delay = max_reconnect_delay
        self._ws: Any | None = None
        self._request_id = 0
        self._reader_task: asyncio.Task[None] | None = None
        self._reader: _WsReader | None = None
        self._pending: dict[int, asyncio.Future[Any]] = {}
        self._pending_mgr = _PendingRequestManager(self._pending)

    @property
    def is_connected(self) -> bool:
        """Return whether the WebSocket connection is open."""
        return self._ws is not None and not self._ws.close_code is not None

    async def connect(self) -> None:
        """Open a WebSocket connection to aria2's RPC endpoint."""
        url = _build_url(self._host, self._port)
        try:
            self._ws = await ws_connect(
                url,
                open_timeout=self._timeout,
                close_timeout=self._timeout,
            )
        except (TimeoutError, OSError) as e:
            raise Aria2ConnectionError(str(e)) from e
        self._reader = _WsReader(
            self._ws, self._pending_mgr, self._event_callback, url, self._timeout
        )
        self._reader._should_reconnect = True
        self._reader_task = asyncio.create_task(self._reader.run())

    async def send_request(self, method: str, params: list[Any], *, add_secret: bool = True) -> Any:
        """Send a JSON-RPC request and wait for its response.

        Raises:
            Aria2ConnectionError: If not connected or the WebSocket fails.

        """
        if not self.is_connected:
            raise Aria2ConnectionError("WebSocket transport is not connected")
        self._request_id += 1
        payload = self._build_payload(method, params, add_secret=add_secret)
        return await self._send_and_wait(payload, self._request_id)

    async def close(self) -> None:
        """Close the connection and cancel pending requests.

        Safe to call multiple times — idempotent.
        """
        if self._reader is not None:
            self._reader.stop()
        await self._stop_reader()
        await self._close_ws()
        self._cancel_pending()

    def _build_payload(self, method: str, params: list[Any], *, add_secret: bool) -> str:
        if add_secret:
            return _build(method, self._secret, params, request_id=self._request_id)
        return _build_noauth(method, params, request_id=self._request_id)

    async def _send_and_wait(self, payload: str, rid: int) -> Any:
        future: asyncio.Future[Any] = asyncio.get_event_loop().create_future()
        self._pending_mgr.register(rid, future)
        assert self._ws is not None
        try:
            await self._ws.send(payload)
            return await asyncio.wait_for(future, timeout=self._timeout)
        finally:
            self._pending_mgr.pop(rid)

    async def _stop_reader(self) -> None:
        if self._reader_task:
            self._reader_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._reader_task
            self._reader_task = None

    async def _close_ws(self) -> None:
        if self._ws:
            await self._ws.close()
            self._ws = None

    def _cancel_pending(self) -> None:
        self._pending_mgr.cancel_all()
