"""Tests for HTTP transport using respx mock router."""

from __future__ import annotations

import json

import pytest
import respx

from aria2.client.transport.http import HttpTransport
from aria2.errors import Aria2ConnectionError, Aria2RpcError

HTTP_URL = "http://localhost:16800/jsonrpc"


@pytest.fixture
def transport() -> HttpTransport:
    return HttpTransport("localhost", 16800, "testsecret", timeout=5.0)


@pytest.mark.asyncio
async def test_send_request_success(transport: HttpTransport) -> None:
    """Successful request returns the RPC result."""
    with respx.mock:
        route = respx.post(HTTP_URL).respond(
            status_code=200,
            content_type="application/json",
            text=json.dumps({"jsonrpc": "2.0", "result": "mock-gid-123", "id": 1}),
        )
        await transport.connect()
        result = await transport.send_request("aria2.addUri", [["http://x"]])

    assert result == "mock-gid-123"
    assert route.called


@pytest.mark.asyncio
async def test_send_request_rpc_error(transport: HttpTransport) -> None:
    """RPC error response raises Aria2RpcError."""
    with respx.mock:
        respx.post(HTTP_URL).respond(
            status_code=200,
            content_type="application/json",
            text=json.dumps(
                {
                    "jsonrpc": "2.0",
                    "error": {"code": -1, "message": "Test RPC error"},
                    "id": 1,
                }
            ),
        )
        await transport.connect()
        with pytest.raises(Aria2RpcError) as exc:
            await transport.send_request("aria2.addUri", [["http://x"]])
    assert exc.value.code == -1


@pytest.mark.asyncio
async def test_send_request_http_error(transport: HttpTransport) -> None:
    """Non-200 HTTP response raises Aria2ConnectionError."""
    with respx.mock:
        respx.post(HTTP_URL).respond(status_code=500, text="Internal Error")
        await transport.connect()
        with pytest.raises(Aria2ConnectionError):
            await transport.send_request("aria2.addUri", [["http://x"]])


@pytest.mark.asyncio
async def test_not_connected_raises() -> None:
    """Sending without connect raises Aria2ConnectionError."""
    t = HttpTransport("localhost", 16800, timeout=1.0)
    with pytest.raises(Aria2ConnectionError):
        await t.send_request("aria2.addUri", [["http://x"]])


@pytest.mark.asyncio
async def test_is_connected(transport: HttpTransport) -> None:
    """is_connected reflects client state."""
    assert not transport.is_connected
    await transport.connect()
    assert transport.is_connected
    await transport.close()
    assert not transport.is_connected


@pytest.mark.asyncio
async def test_close(transport: HttpTransport) -> None:
    """Close properly cleans up the client."""
    await transport.connect()
    assert transport.is_connected
    await transport.close()
    assert not transport.is_connected
