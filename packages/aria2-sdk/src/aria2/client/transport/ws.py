"""WebSocket transport for aria2 JSON-RPC with event dispatch."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from contextlib import suppress
from typing import Any

import websockets
from websockets.asyncio.client import connect as ws_connect

from aria2.client.transport import Transport
from aria2.errors import Aria2ConnectionError
from aria2.rpc import build_request as _build_noauth
from aria2.rpc import build_request_with_secret as _build
from aria2.rpc import parse_notification as _parse_notification
from aria2.rpc import parse_response as _parse_response


class WebSocketTransport(Transport):
    """JSON-RPC over WebSocket via ``websockets`` library.

    Primary transport — sends requests and receives both responses
    and push notifications from the aria2 daemon.
    """

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
        self._reconnect_delay = reconnect_delay
        self._max_reconnect_delay = max_reconnect_delay

        self._ws: Any | None = None
        self._request_id = 0
        self._pending: dict[int, asyncio.Future[Any]] = {}
        self._reader_task: asyncio.Task[None] | None = None
        self._should_reconnect = False

    # ── Transport interface ──────────────────────────────────

    @property
    def is_connected(self) -> bool:
        """Return whether the WebSocket connection is open."""
        return self._ws is not None and not self._ws.close_code is not None

    async def connect(self) -> None:
        """Open a WebSocket connection to the aria2 RPC endpoint.

        Starts a background reader task to receive responses and
        push notifications from the daemon.

        Raises:
            Aria2ConnectionError: If the WebSocket connection fails.

        """
        url = f"ws://{self._host}:{self._port}/jsonrpc"
        try:
            self._ws = await ws_connect(
                url,
                open_timeout=self._timeout,
                close_timeout=self._timeout,
            )
        except (TimeoutError, OSError) as e:
            raise Aria2ConnectionError(str(e)) from e

        self._should_reconnect = True
        self._reader_task = asyncio.create_task(self._reader_loop())

    async def send_request(self, method: str, params: list[Any], *, add_secret: bool = True) -> Any:
        """Send a JSON-RPC request over WebSocket.

        Sends the request and waits for the matching response.
        Push notifications are handled separately by the reader loop
        and dispatched via the event callback.

        Args:
            method: JSON-RPC method name (e.g. ``"aria2.addUri"``).
            params: Parameters for the method.
            add_secret: If True, prepend ``token:{secret}`` to params.

        Returns:
            The parsed JSON-RPC result.

        Raises:
            Aria2ConnectionError: If not connected or the WebSocket fails.

        """
        if not self.is_connected:
            raise Aria2ConnectionError("WebSocket transport is not connected")

        self._request_id += 1
        rid = self._request_id
        if add_secret:
            payload = _build(method, self._secret, params, request_id=rid)
        else:
            payload = _build_noauth(method, params, request_id=rid)

        future: asyncio.Future[Any] = asyncio.get_event_loop().create_future()
        self._pending[rid] = future

        assert self._ws is not None  # checked above via is_connected
        try:
            await self._ws.send(payload)
            result = await asyncio.wait_for(future, timeout=self._timeout)
            return result
        finally:
            self._pending.pop(rid, None)

    async def close(self) -> None:
        """Close the WebSocket connection and cancel pending requests.

        Stops the reader task, closes the socket, and cancels any
        futures still waiting for responses.  Safe to call multiple
        times — idempotent.
        """
        self._should_reconnect = False
        if self._reader_task:
            self._reader_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._reader_task
            self._reader_task = None

        if self._ws:
            await self._ws.close()
            self._ws = None

        # Cancel any pending requests
        for fut in self._pending.values():
            if not fut.done():
                fut.cancel()
        self._pending.clear()

    # ── Internal reader loop ─────────────────────────────────

    async def _reader_loop(self) -> None:
        """Continuously read messages from the WebSocket.

        Responses are matched to pending futures by request ID.
        Notifications are dispatched to the event callback.
        """
        assert self._ws is not None  # validated before task creation

        try:
            async for raw in self._ws:
                with suppress(Exception):
                    self._dispatch(raw)  # swallow dispatch errors; keep reading
        except websockets.ConnectionClosed:
            if self._should_reconnect:
                await self._reconnect()

    def _dispatch(self, raw: str) -> None:
        """Route an incoming message to a pending future or event callback."""
        # Try notification first (most common in steady state)
        notif = _parse_notification(raw)
        if notif is not None:
            method, params = notif
            if self._event_callback:
                self._event_callback(method, params)
            return

        # Otherwise treat as response
        obj = json.loads(raw)
        rid = obj.get("id")
        future = self._pending.get(rid)
        if future is None:
            return  # stale/unknown response

        if not future.done():
            try:
                result = _parse_response(raw)
                future.set_result(result)
            except Exception as e:
                future.set_exception(e)

    async def _reconnect(self) -> None:
        """Exponential backoff reconnection."""
        delay = self._reconnect_delay
        while self._should_reconnect:
            try:
                await asyncio.sleep(delay)
                url = f"ws://{self._host}:{self._port}/jsonrpc"
                self._ws = await ws_connect(
                    url,
                    open_timeout=self._timeout,
                    close_timeout=self._timeout,
                )
                # Restart the reader loop
                await self._reader_loop()
            except TimeoutError, OSError:
                delay = min(delay * 2, self._max_reconnect_delay)
            else:
                return
