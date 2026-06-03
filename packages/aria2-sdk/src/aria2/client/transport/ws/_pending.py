"""Pending request future manager for WebSocket transport."""

from __future__ import annotations

import asyncio
from typing import Any


class _PendingRequestManager:
    """Manages pending JSON-RPC request futures.

    Wraps operations on the ``dict[int, asyncio.Future[Any]]`` that
    maps request IDs to awaiting futures.  The dict is owned by
    ``WebSocketTransport`` as ``self._pending`` — this class receives
    a reference and provides helper methods.
    """

    def __init__(self, pending: dict[int, asyncio.Future[Any]]) -> None:
        """Wrap *pending*, a dict owned by the transport."""
        self._pending = pending

    def register(self, rid: int, future: asyncio.Future[Any]) -> None:
        """Register *future* under request ID *rid*."""
        self._pending[rid] = future

    def pop(self, rid: int) -> asyncio.Future[Any] | None:
        """Remove and return the future for *rid*.

        Returns ``None`` if *rid* is not in the map.
        """
        return self._pending.pop(rid, None)

    def get(self, rid: int) -> asyncio.Future[Any] | None:
        """Return the future for *rid* without removing it.

        Returns ``None`` if *rid* is not in the map.
        """
        return self._pending.get(rid)

    def cancel_all(self) -> None:
        """Cancel all incomplete futures and clear the map.

        Futures that have already completed (result or exception set)
        are left untouched.
        """
        for fut in self._pending.values():
            if not fut.done():
                fut.cancel()
        self._pending.clear()
