"""EventManager — WebSocket event callback registration."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

# Event short-name to full RPC method mapping.
# Single source of truth for all event-related code.
_EVENT_MAP: dict[str, str] = {
    "onDownloadStart": "aria2.onDownloadStart",
    "onDownloadPause": "aria2.onDownloadPause",
    "onDownloadStop": "aria2.onDownloadStop",
    "onDownloadComplete": "aria2.onDownloadComplete",
    "onDownloadError": "aria2.onDownloadError",
    "onBtDownloadComplete": "aria2.onBtDownloadComplete",
}


class EventManager:
    """Register WebSocket event callbacks for download notifications.

    Accessed via :attr:`Aria2Client.events`.

    Events are dispatched from the WebSocket transport's reader loop.
    Register callbacks with the ``on_*`` methods before starting
    downloads to receive push notifications.
    """

    def __init__(self, callbacks: dict[str, list[Callable[..., Any]]]) -> None:
        self._callbacks = callbacks

    def on_download_start(self, callback: Callable[..., Any]) -> None:
        """Register a callback to invoke when a download starts."""
        self._callbacks["onDownloadStart"].append(callback)

    def on_download_pause(self, callback: Callable[..., Any]) -> None:
        """Register a callback to invoke when a download is paused."""
        self._callbacks["onDownloadPause"].append(callback)

    def on_download_stop(self, callback: Callable[..., Any]) -> None:
        """Register a callback to invoke when a download stops."""
        self._callbacks["onDownloadStop"].append(callback)

    def on_download_complete(self, callback: Callable[..., Any]) -> None:
        """Register a callback to invoke when a download completes successfully."""
        self._callbacks["onDownloadComplete"].append(callback)

    def on_download_error(self, callback: Callable[..., Any]) -> None:
        """Register a callback to invoke when a download fails."""
        self._callbacks["onDownloadError"].append(callback)

    def on_bt_download_complete(self, callback: Callable[..., Any]) -> None:
        """Register a callback to invoke when a BitTorrent download completes."""
        self._callbacks["onBtDownloadComplete"].append(callback)
