"""Tests for WebSocket transport using a live websockets server."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest
import pytest_asyncio

from aria2.client.transport.ws import WebSocketTransport
from aria2.errors import Aria2ConnectionError, Aria2RpcError

pytest.importorskip("websockets")


@pytest_asyncio.fixture
async def ws_server(unused_tcp_port_factory: Any) -> Any:
    """Start a WebSocket server that mimics aria2 JSON-RPC."""
    import websockets

    port = unused_tcp_port_factory()
    state: dict[str, Any] = {
        "port": port,
        "next_result": "mock-gid-abc",
        "next_error": None,
        "received": [],
        "notifications": [],
        "close_on_connect": False,
    }

    async def handler(ws: Any) -> None:
        if state["close_on_connect"]:
            return
        try:
            async for raw in ws:
                state["received"].append(raw)
                msg = json.loads(raw)
                rid = msg.get("id")

                # Check if it's a notification to send back
                if state["notifications"]:
                    notif = state["notifications"].pop(0)
                    await ws.send(json.dumps(notif))

                # Send response
                if state["next_error"]:
                    err = state["next_error"]
                    state["next_error"] = None
                    resp = {"jsonrpc": "2.0", "error": err, "id": rid}
                else:
                    resp = {
                        "jsonrpc": "2.0",
                        "result": state["next_result"],
                        "id": rid,
                    }
                await ws.send(json.dumps(resp))
        except websockets.ConnectionClosed:
            pass

    async with websockets.serve(handler, "localhost", port):
        yield state


@pytest.mark.asyncio
async def test_connect_and_request(ws_server: dict[str, Any]) -> None:
    t = WebSocketTransport("localhost", ws_server["port"], timeout=5.0)
    await t.connect()
    try:
        result = await t.send_request("aria2.addUri", [["http://x"]])
        assert result == "mock-gid-abc"
    finally:
        await t.close()


@pytest.mark.asyncio
async def test_rpc_error(ws_server: dict[str, Any]) -> None:
    ws_server["next_error"] = {"code": -1, "message": "Test WS error"}
    t = WebSocketTransport("localhost", ws_server["port"], timeout=5.0)
    await t.connect()
    try:
        with pytest.raises(Aria2RpcError) as exc:
            await t.send_request("aria2.addUri", [["http://x"]])
        assert exc.value.code == -1
    finally:
        await t.close()


@pytest.mark.asyncio
async def test_notification_dispatched(ws_server: dict[str, Any]) -> None:
    """A single notification received before the response is dispatched."""
    received_events: list[tuple[str, list[Any]]] = []

    def on_event(method: str, params: list[Any]) -> None:
        received_events.append((method, params))

    ws_server["notifications"] = [
        {
            "jsonrpc": "2.0",
            "method": "aria2.onDownloadStart",
            "params": [{"gid": "abc"}],
        },
    ]

    t = WebSocketTransport(
        "localhost",
        ws_server["port"],
        timeout=5.0,
        event_callback=on_event,
    )
    await t.connect()
    try:
        result = await t.send_request("aria2.addUri", [["http://x"]])
        assert result == "mock-gid-abc"
        await asyncio.sleep(0.1)
        assert len(received_events) >= 1
        assert received_events[0][0] == "aria2.onDownloadStart"
    finally:
        await t.close()


@pytest.mark.asyncio
async def test_is_connected(ws_server: dict[str, Any]) -> None:
    t = WebSocketTransport("localhost", ws_server["port"], timeout=5.0)
    assert not t.is_connected
    await t.connect()
    assert t.is_connected
    await t.close()
    assert not t.is_connected


@pytest.mark.asyncio
async def test_not_connected_raises() -> None:
    t = WebSocketTransport("localhost", 18999, timeout=1.0)
    with pytest.raises(Aria2ConnectionError):
        await t.send_request("aria2.addUri", [["http://x"]])


@pytest.mark.asyncio
async def test_close_without_connect_is_safe() -> None:
    """Closing an unconnected transport does not raise."""
    t = WebSocketTransport("localhost", 18999, timeout=1.0)
    await t.close()  # should be a no-op


@pytest.mark.asyncio
async def test_connect_refused_raises() -> None:
    """Connecting to nothing raises Aria2ConnectionError."""
    t = WebSocketTransport("localhost", 18998, timeout=1.0)
    with pytest.raises(Aria2ConnectionError):
        await t.connect()


@pytest.mark.asyncio
async def test_send_request_no_secret(ws_server: dict[str, Any]) -> None:
    """Request without secret works (no token injected)."""
    t = WebSocketTransport("localhost", ws_server["port"], secret="tok", timeout=5.0)
    await t.connect()
    try:
        result = await t.send_request("aria2.addUri", [["http://x"]], add_secret=False)
        assert result == "mock-gid-abc"
        # Verify payload does not contain "token:tok"
        sent = ws_server["received"][0]
        assert "token:tok" not in sent
    finally:
        await t.close()


@pytest.mark.asyncio
async def test_stale_response_ignored(ws_server: dict[str, Any]) -> None:
    """A response with an unknown ID is silently ignored."""

    received_events: list[tuple[str, list[Any]]] = []

    def on_event(method: str, params: list[Any]) -> None:
        received_events.append((method, params))

    t = WebSocketTransport(
        "localhost",
        ws_server["port"],
        timeout=5.0,
        event_callback=on_event,
    )
    await t.connect()
    try:
        # Send a fake response with unknown ID via the server
        ws_server["notifications"].append(
            {"jsonrpc": "2.0", "result": "stale", "id": 999}
        )
        result = await t.send_request("aria2.addUri", [["http://x"]])
        assert result == "mock-gid-abc"
    finally:
        await t.close()


@pytest.mark.asyncio
async def test_close_cancels_pending(ws_server: dict[str, Any]) -> None:
    """Close() cancels pending requests."""
    t = WebSocketTransport("localhost", ws_server["port"], timeout=5.0)
    await t.connect()
    # Manually inject a pending future (simulating a request in flight)
    fut: asyncio.Future[Any] = asyncio.get_event_loop().create_future()
    t._pending[999] = fut
    await t.close()
    assert fut.done()
    assert fut.cancelled()


@pytest.mark.asyncio
async def test_dispatch_error_swallowed(ws_server: dict[str, Any]) -> None:
    """A callback that raises does not crash the reader loop."""

    def on_event(method: str, params: list[Any]) -> None:
        raise RuntimeError("callback error")

    ws_server["notifications"] = [
        {
            "jsonrpc": "2.0",
            "method": "aria2.onDownloadStart",
            "params": [{"gid": "abc"}],
        },
    ]

    t = WebSocketTransport(
        "localhost",
        ws_server["port"],
        timeout=5.0,
        event_callback=on_event,
    )
    await t.connect()
    try:
        result = await t.send_request("aria2.addUri", [["http://x"]])
        assert result == "mock-gid-abc"
    finally:
        await t.close()
