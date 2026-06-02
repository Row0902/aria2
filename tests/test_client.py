"""Tests for Aria2Client — mock transport layer."""

from __future__ import annotations

from typing import Any

import pytest

from aria2 import Aria2Client


class _MockTransport:
    """Simulates the Transport ABC for testing client logic."""

    def __init__(self) -> None:
        self._connected = False
        self.sent: list[tuple[str, list[Any]]] = []
        self._next_result: Any = "ok"
        self._next_error: Exception | None = None

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def connect(self) -> None:
        self._connected = True

    async def send_request(self, method: str, params: list[Any], *, add_secret: bool = True) -> Any:
        self.sent.append((method, params))
        if self._next_error:
            raise self._next_error
        return self._next_result

    async def close(self) -> None:
        self._connected = False


@pytest.fixture
def client() -> Any:
    """Create an Aria2Client with mock transports."""
    c = Aria2Client(secret="testsecret", enable_ws=True)
    mock_http = _MockTransport()
    mock_ws = _MockTransport()
    c._http = mock_http  # ty: ignore = invalid-assignment
    c._ws = mock_ws  # ty: ignore = invalid-assignment
    return c, mock_http, mock_ws


@pytest.mark.asyncio
async def test_connect_connects_both(client: Any) -> None:
    c, http, ws = client
    await c.connect()
    assert http.is_connected
    assert ws.is_connected


@pytest.mark.asyncio
async def test_close_closes_both(client: Any) -> None:
    c, http, ws = client
    await c.connect()
    await c.close()
    assert not http.is_connected
    assert not ws.is_connected


@pytest.mark.asyncio
async def test_add_uri(client: Any) -> None:
    c, http, ws = client
    ws._next_result = "gid-abc"
    await c.connect()
    result = await c.downloads.add_uri(["http://example.com/file.zip", "http://mirror/file.zip"])
    assert result == "gid-abc"
    assert ws.sent[0] == (
        "aria2.addUri",
        [["http://example.com/file.zip", "http://mirror/file.zip"]],
    )


@pytest.mark.asyncio
async def test_add_uri_with_options(client: Any) -> None:
    c, http, ws = client
    await c.connect()
    await c.downloads.add_uri(
        ["http://x"],
        options={"dir": "/tmp", "out": "file.zip"},
        position=1,
    )
    assert ws.sent[0] == (
        "aria2.addUri",
        [["http://x"], {"dir": "/tmp", "out": "file.zip"}, 1],
    )


@pytest.mark.asyncio
async def test_tell_status(client: Any) -> None:
    c, http, ws = client
    ws._next_result = {
        "gid": "abc",
        "status": "active",
        "totalLength": "1048576",
        "completedLength": "524288",
        "downloadSpeed": "102400",
        "dir": "/downloads",
    }
    await c.connect()
    result = await c.status.tell_status("abc")
    assert result.gid == "abc"
    assert result.status == "active"
    assert result.total_length == "1048576"
    assert result.completed_length == "524288"
    assert result.download_speed == "102400"


@pytest.mark.asyncio
async def test_tell_status_with_keys(client: Any) -> None:
    c, http, ws = client
    ws._next_result = {
        "gid": "abc",
        "status": "active",
        "totalLength": "1000",
        "completedLength": "500",
        "downloadSpeed": "100",
    }
    await c.connect()
    result = await c.status.tell_status("abc", keys=["gid", "status"])
    assert ws.sent[0] == ("aria2.tellStatus", ["abc", ["gid", "status"]])
    assert result.gid == "abc"


@pytest.mark.asyncio
async def test_tell_active(client: Any) -> None:
    c, http, ws = client
    ws._next_result = [{"gid": "a"}, {"gid": "b"}]
    await c.connect()
    result = await c.status.tell_active()
    assert len(result) == 2


@pytest.mark.asyncio
async def test_tell_waiting(client: Any) -> None:
    c, http, ws = client
    ws._next_result = [{"gid": "a"}]
    await c.connect()
    result = await c.status.tell_waiting(offset=5, num=10)
    assert ws.sent[0] == ("aria2.tellWaiting", [5, 10])
    assert len(result) == 1


@pytest.mark.asyncio
async def test_remove(client: Any) -> None:
    c, http, ws = client
    await c.connect()
    await c.downloads.remove("abc")
    assert ws.sent[0] == ("aria2.remove", ["abc"])


@pytest.mark.asyncio
async def test_remove_force(client: Any) -> None:
    c, http, ws = client
    await c.connect()
    await c.downloads.remove("abc", force=True)
    assert ws.sent[0] == ("aria2.forceRemove", ["abc"])


@pytest.mark.asyncio
async def test_pause(client: Any) -> None:
    c, http, ws = client
    await c.connect()
    await c.downloads.pause("abc")
    assert ws.sent[0] == ("aria2.pause", ["abc"])


@pytest.mark.asyncio
async def test_pause_all(client: Any) -> None:
    c, http, ws = client
    await c.connect()
    await c.downloads.pause_all()
    assert ws.sent[0] == ("aria2.pauseAll", [])


@pytest.mark.asyncio
async def test_change_position(client: Any) -> None:
    c, http, ws = client
    ws._next_result = "3"
    await c.connect()
    result = await c.downloads.change_position("abc", 0, how="POS_CUR")
    assert result == 3


@pytest.mark.asyncio
async def test_get_version(client: Any) -> None:
    c, http, ws = client
    ws._next_result = {
        "version": "1.37.0",
        "enabledFeatures": ["Async DNS", "BitTorrent"],
    }
    await c.connect()
    result = await c.system.get_version()
    assert result.version == "1.37.0"
    assert result.enabled_features == ["Async DNS", "BitTorrent"]


@pytest.mark.asyncio
async def test_shutdown(client: Any) -> None:
    c, http, ws = client
    await c.connect()
    await c.system.shutdown()
    assert ws.sent[0] == ("aria2.shutdown", [])


@pytest.mark.asyncio
async def test_shutdown_force(client: Any) -> None:
    c, http, ws = client
    await c.connect()
    await c.system.shutdown(force=True)
    assert ws.sent[0] == ("aria2.forceShutdown", [])


@pytest.mark.asyncio
async def test_get_global_stat(client: Any) -> None:
    c, http, ws = client
    ws._next_result = {
        "downloadSpeed": "500000",
        "uploadSpeed": "10000",
        "numActive": "3",
    }
    await c.connect()
    result = await c.status.get_global_stat()
    assert result.download_speed == "500000"
    assert result.num_active == "3"


@pytest.mark.asyncio
async def test_list_methods(client: Any) -> None:
    c, http, ws = client
    ws._next_result = ["aria2.addUri", "aria2.tellStatus", "system.listMethods"]
    await c.connect()
    result = await c.system.list_methods()
    assert "addUri" in result
    assert "tellStatus" in result
    assert "system.listMethods" in result


@pytest.mark.asyncio
async def test_multicall(client: Any) -> None:
    c, http, ws = client
    calls = [{"methodName": "aria2.getVersion", "params": []}]
    await c.connect()
    await c.system.multicall(calls)
    expected_calls = [
        {"methodName": "aria2.getVersion", "params": ["token:testsecret"]},
    ]
    assert ws.sent[0] == ("system.multicall", [expected_calls])


@pytest.mark.asyncio
async def test_event_callbacks(client: Any) -> None:
    c, http, ws = client
    events: list[str] = []

    c.events.on_download_start(lambda gid=None: events.append("start"))
    c.events.on_download_complete(lambda gid=None: events.append("complete"))
    c.events.on_download_error(lambda gid=None: events.append("error"))

    c._on_event("aria2.onDownloadStart", [{"gid": "abc"}])
    c._on_event("aria2.onDownloadComplete", [{"gid": "abc"}])
    c._on_event("aria2.onDownloadError", [{"gid": "abc"}])

    assert events == ["start", "complete", "error"]


@pytest.mark.asyncio
async def test_add_torrent(client: Any) -> None:
    c, http, ws = client
    await c.connect()
    await c.downloads.add_torrent(b"\x00\x01torrent data")
    method, params = ws.sent[0]
    assert method == "aria2.addTorrent"
    assert params[0] == "AAF0b3JyZW50IGRhdGE="


@pytest.mark.asyncio
async def test_add_metalink(client: Any) -> None:
    c, http, ws = client
    await c.connect()
    await c.downloads.add_metalink(b"metalink data")
    method, params = ws.sent[0]
    assert method == "aria2.addMetalink"
    assert params[0] == "bWV0YWxpbmsgZGF0YQ=="


@pytest.mark.asyncio
async def test_get_files(client: Any) -> None:
    c, http, ws = client
    ws._next_result = [
        {
            "index": "1",
            "path": "/tmp/file.zip",
            "length": "1000",
            "completedLength": "1000",
            "selected": "true",
        },
    ]
    await c.connect()
    result = await c.status.get_files("abc")
    assert result[0].path == "/tmp/file.zip"


@pytest.mark.asyncio
async def test_save_session(client: Any) -> None:
    c, http, ws = client
    await c.connect()
    await c.system.save_session()
    assert ws.sent[0] == ("aria2.saveSession", [])


@pytest.mark.asyncio
async def test_http_fallback(client: Any) -> None:
    """When WS is not connected, client uses HTTP."""
    c, http, ws = client
    # Keep ws disconnected by overriding the connect method
    orig_ws_connect = ws.connect

    async def _noop() -> None:
        pass

    ws.connect = _noop  # ty: ignore = invalid-assignment
    ws._connected = False
    http._next_result = "http-result"
    await c.connect()
    result = await c.downloads.add_uri(["http://x"])
    assert result == "http-result"
    assert len(http.sent) == 1
    assert http.sent[0][0] == "aria2.addUri"
    ws.connect = orig_ws_connect
