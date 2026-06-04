"""WebSocket reader loop with notification dispatch and reconnection."""

from __future__ import annotations

import asyncio
import json
from contextlib import suppress
from typing import Any

import websockets
from websockets.asyncio.client import connect as ws_connect

from aria2.client.transport.ws._pending import _PendingRequestManager
from aria2.rpc import parse_notification as _parse_notification
from aria2.rpc import parse_response as _parse_response


class _WsReader:
    """Reads WebSocket messages, dispatches responses and notifications.

    Owns the reader :class:`asyncio.Task` and runs the reconnect loop.
    """

    def __init__(
        self,
        ws: Any,
        pending_mgr: _PendingRequestManager,
        event_callback: Any,
        url: str,
        timeout: float,
    ) -> None:
        self._ws = ws
        self._pending_mgr = pending_mgr
        self._event_callback = event_callback
        self._url = url
        self._timeout = timeout
        self._should_reconnect = False
        self._reconnect_delay = 1.0
        self._max_reconnect_delay = 30.0

    async def run(self) -> None:
        """Read messages until the connection closes or is cancelled."""
        try:
            async for raw in self._ws:
                if isinstance(raw, bytes):
                    raw = raw.decode("utf-8")
                with suppress(Exception):
                    self._dispatch(raw)
        except websockets.ConnectionClosed:
            if self._should_reconnect:
                await self._reconnect()

    def _dispatch(self, raw: str) -> None:
        if self._try_notification(raw):
            return
        self._try_response(raw)

    def _try_notification(self, raw: str) -> bool:
        notif = _parse_notification(raw)
        if notif is not None:
            method, params = notif
            if self._event_callback:
                self._event_callback(method, params)
            return True
        return False

    def _try_response(self, raw: str) -> None:
        obj = json.loads(raw)
        rid = obj.get("id")
        future = self._pending_mgr.get(rid)
        if future is None:
            return
        if not future.done():
            try:
                result = _parse_response(raw)
                future.set_result(result)
            except Exception as e:
                future.set_exception(e)

    async def _reconnect(self) -> None:
        delay = self._reconnect_delay
        while self._should_reconnect:
            try:
                await asyncio.sleep(delay)
                self._ws = await ws_connect(
                    self._url,
                    open_timeout=self._timeout,
                    close_timeout=self._timeout,
                )
                await self.run()
            except TimeoutError, OSError:
                delay = min(delay * 2, self._max_reconnect_delay)
            else:
                return

    def stop(self) -> None:
        """Signal the reader and reconnect loop to stop."""
        self._should_reconnect = False
