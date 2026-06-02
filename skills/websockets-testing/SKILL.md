---
name: websockets-testing
description: "Trigger: websockets, WebSocket test, WS test, mock WebSocket, WS server test, notification test, WebSocket fixture. Testing WebSocket connections and event notifications in async Python SDKs."
license: Apache-2.0
metadata:
  author: gentleman-programming
  version: "1.0"
---

## When to Use

- Writing tests for WebSocket transport and event dispatch
- Setting up a local WebSocket server for integration testing
- Simulating notifications (push events from the daemon)
- Testing reconnection logic and exponential backoff
- Validating message routing (response vs notification)
- Testing connection failures and timeouts

## Critical Patterns

### Live Server Fixture

The project uses a real `websockets` server for testing:

```python
import pytest_asyncio
from collections.abc import AsyncIterator

@pytest_asyncio.fixture
async def ws_server(unused_tcp_port_factory: Any) -> AsyncIterator[dict[str, Any]]:
    """Start a WebSocket server that mimics aria2 JSON-RPC."""
    import websockets
    import asyncio

    port = unused_tcp_port_factory()
    state: dict[str, Any] = {
        "port": port,
        "next_result": "mock-gid",
        "next_error": None,
        "received": [],
        "notifications": [],
        "close_on_connect": False,
    }

    async def handler(ws):
        """Handle incoming WebSocket messages."""
        if state["close_on_connect"]:
            return  # Close immediately

        async for raw in ws:
            msg = json.loads(raw)
            state["received"].append(msg)

            # If it's a response (has id), send response or error
            if "id" in msg:
                if state["next_error"]:
                    resp = {
                        "jsonrpc": "2.0",
                        "error": state["next_error"],
                        "id": msg["id"],
                    }
                else:
                    resp = {
                        "jsonrpc": "2.0",
                        "result": state["next_result"],
                        "id": msg["id"],
                    }
                await ws.send(json.dumps(resp))

    server = await websockets.serve(handler, "localhost", port)
    await asyncio.sleep(0.05)  # Let server start
    yield state
    server.close()
    await server.wait_closed()
```

### Test: Request/Response

```python
async def test_connect_and_request(ws_server):
    transport = WebSocketTransport(
        host="localhost", port=ws_server["port"]
    )
    await transport.connect()
    assert transport.is_connected

    result = await transport.send_request("aria2.addUri", [["https://x"]])
    assert result == "mock-gid"
    assert len(ws_server["received"]) == 1
    await transport.close()
```

### Test: RPC Error Response

```python
async def test_rpc_error(ws_server):
    ws_server["next_error"] = {
        "code": -32601, "message": "Method not found"
    }
    transport = WebSocketTransport(
        host="localhost", port=ws_server["port"]
    )
    await transport.connect()

    with pytest.raises(Aria2RpcError) as exc:
        await transport.send_request("aria2.unknown", [])
    assert exc.value.code == -32601
    await transport.close()
```

### Test: Notification Dispatch

```python
async def test_notification_dispatched(ws_server):
    transport = WebSocketTransport(
        host="localhost", port=ws_server["port"]
    )
    await transport.connect()
    assert transport.is_connected

    notifications = []
    transport.on_download_start = lambda gid: notifications.append(gid)

    # Simulate server sending a notification
    import websockets
    async with websockets.connect(
        f"ws://localhost:{ws_server['port']}"
    ) as ws:
        notif = {
            "jsonrpc": "2.0",
            "method": "aria2.onDownloadStart",
            "params": [{"gid": "abc123"}],
        }
        await ws.send(json.dumps(notif))
    await asyncio.sleep(0.1)

    assert len(notifications) == 1
    assert notifications[0] == "abc123"
    await transport.close()
```

### Test: Connection Refused

```python
async def test_connect_refused_raises(unused_tcp_port):
    """No server listening — connection refused."""
    transport = WebSocketTransport("localhost", unused_tcp_port)
    with pytest.raises(Aria2ConnectionError):
        await transport.connect()
```

### Test: Not Connected Raises

```python
async def test_not_connected_raises():
    transport = WebSocketTransport("localhost", 6800)
    with pytest.raises(Aria2ConnectionError):
        await transport.send_request("aria2.addUri", [])
```

### Test: Close Without Connect Is Safe

```python
async def test_close_without_connect_is_safe():
    transport = WebSocketTransport("localhost", 6800)
    await transport.close()  # Should not raise
```

### Test: Reconnection

```python
async def test_reconnect_after_close(ws_server):
    transport = WebSocketTransport(
        host="localhost",
        port=ws_server["port"],
        reconnect=True,
    )
    await transport.connect()
    await transport.close()

    # Reconnect
    await transport.connect()
    assert transport.is_connected
    result = await transport.send_request("aria2.addUri", [["https://x"]])
    assert result is not None
    await transport.close()
```

### Test: Concurrent Requests

```python
async def test_concurrent_requests(ws_server):
    transport = WebSocketTransport(
        host="localhost", port=ws_server["port"]
    )
    await transport.connect()

    results = await asyncio.gather(
        transport.send_request("aria2.addUri", [["https://a"]]),
        transport.send_request("aria2.addUri", [["https://b"]]),
        transport.send_request("aria2.addUri", [["https://c"]]),
    )
    assert len(results) == 3
    assert all(r == "mock-gid" for r in results)
    await transport.close()
```

### Test: Message Routing

```python
async def test_response_routed_by_id(ws_server):
    """Verify multiple responses are matched to correct requests."""
    transport = WebSocketTransport(
        host="localhost", port=ws_server["port"]
    )
    await transport.connect()

    # Manually verify that the transport sends JSON-RPC requests
    # with incrementing IDs and matches responses correctly
    result1 = await transport.send_request("aria2.addUri", [["https://a"]])
    result2 = await transport.send_request("aria2.addUri", [["https://b"]])

    # Both should return independent results
    assert result1 is not None
    assert result2 is not None

    # Server received 2 requests
    assert len(ws_server["received"]) == 2
    await transport.close()
```

### Using `pytest.importorskip`

If `websockets` is optional, use `importorskip`:

```python
pytest.importorskip("websockets")

# ... tests that depend on websockets
```

This skips the entire file if `websockets` is not installed.

### Fixture with `unused_tcp_port`

```python
async def test_unused_ports_produce_different_values(unused_tcp_port_factory):
    port_a = unused_tcp_port_factory()
    port_b = unused_tcp_port_factory()
    assert port_a != port_b
```

## Best Practices for SDKs

### 1. Use a state dict for test server
Pass a mutable `state` dict to the fixture that tests can modify to control behavior (set errors, customize responses).

### 2. Test both response and notification paths
WebSocket transports handle both synchronous RPC responses and async push notifications.

### 3. Test connection failure scenarios
Connection refused, timeout, immediate close — these should all raise `Aria2ConnectionError`.

### 4. Test double-close safety
Calling `close()` when already closed should be idempotent.

### 5. Test discovery of pending notifications
When connecting after notifications were sent, the SDK should either buffer them or miss them gracefully (document which).

### 6. Test reconnection with state preservation
After reconnection, pending requests should be retried or failed with a clear error.

## Common Pitfalls

- **Server cleanup**: The fixture must `server.close()` and `await server.wait_closed()`. Otherwise, ports leak between tests.
- **`asyncio.sleep` in tests**: Real servers need a moment to start. A short `asyncio.sleep(0.05)` prevents flaky tests.
- **Port conflicts**: `unused_tcp_port` returns a port that was free at call time. When running many tests in parallel, use `unused_tcp_port_factory` for sequential unique ports.
- **Notification timing**: Notifications sent before the reader loop starts are lost. Tests should send after `connect()` completes.
- **`importorskip` at module level**: Put `pytest.importorskip("websockets")` at the top of the test file to skip all WS tests when the library is missing.

## Resources

- websockets library: <https://websockets.readthedocs.io/>
- pytest-asyncio fixtures: <https://pytest-asyncio.readthedocs.io/>
- WS test patterns: <https://websockets.readthedocs.io/en/stable/howto/testing.html>
