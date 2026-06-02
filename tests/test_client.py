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


# ── DownloadManager edge cases ────────────────────────────


@pytest.mark.asyncio
async def test_add_uri_with_position_only(client: Any) -> None:
    """add_uri with position but no options — hits elif branch."""
    c, http, ws = client
    await c.connect()
    await c.downloads.add_uri(["http://x"], position=5)
    assert ws.sent[0] == ("aria2.addUri", [["http://x"], {}, 5])


@pytest.mark.asyncio
async def test_add_torrent_with_uris(client: Any) -> None:
    """add_torrent with web seed URIs."""
    c, http, ws = client
    await c.connect()
    await c.downloads.add_torrent(b"data", uris=["http://seed"])
    method, params = ws.sent[0]
    assert method == "aria2.addTorrent"
    assert params[1] == ["http://seed"]


@pytest.mark.asyncio
async def test_add_torrent_with_uris_options_position(client: Any) -> None:
    """add_torrent with all optional parameters."""
    c, http, ws = client
    await c.connect()
    await c.downloads.add_torrent(
        b"data", uris=["http://seed"], options={"dir": "/tmp"}, position=1,
    )
    method, params = ws.sent[0]
    assert method == "aria2.addTorrent"
    assert params[1] == ["http://seed"]
    assert params[2] == {"dir": "/tmp"}
    assert params[3] == 1


@pytest.mark.asyncio
async def test_add_torrent_with_uris_position(client: Any) -> None:
    """add_torrent with uris + position, no options."""
    c, http, ws = client
    await c.connect()
    await c.downloads.add_torrent(b"data", uris=["http://seed"], position=0)
    method, params = ws.sent[0]
    assert method == "aria2.addTorrent"
    # uris branch + elif position → params: [b64, uris, [], position]
    assert params[2] == []  # empty options placeholder
    assert params[3] == 0


@pytest.mark.asyncio
async def test_add_torrent_with_options_position(client: Any) -> None:
    """add_torrent with options + position, no uris."""
    c, http, ws = client
    await c.connect()
    await c.downloads.add_torrent(b"data", options={"dir": "/tmp"}, position=1)
    method, params = ws.sent[0]
    assert method == "aria2.addTorrent"
    assert params[1] == {"dir": "/tmp"}
    assert params[2] == 1


@pytest.mark.asyncio
async def test_add_torrent_with_position_only(client: Any) -> None:
    """add_torrent with position, no uris, no options."""
    c, http, ws = client
    await c.connect()
    await c.downloads.add_torrent(b"data", position=2)
    method, params = ws.sent[0]
    assert method == "aria2.addTorrent"
    assert params[1] == 2


@pytest.mark.asyncio
async def test_add_metalink_with_position_only(client: Any) -> None:
    """add_metalink with position but no options."""
    c, http, ws = client
    await c.connect()
    await c.downloads.add_metalink(b"metal", position=0)
    method, params = ws.sent[0]
    assert method == "aria2.addMetalink"
    assert params[1] == 0


@pytest.mark.asyncio
async def test_add_metalink_with_options_position(client: Any) -> None:
    """add_metalink with options + position."""
    c, http, ws = client
    await c.connect()
    await c.downloads.add_metalink(b"metal", options={"dir": "/tmp"}, position=1)
    method, params = ws.sent[0]
    assert method == "aria2.addMetalink"
    assert params[1] == {"dir": "/tmp"}
    assert params[2] == 1


# ── OptionsManager tests ──────────────────────────────────


@pytest.mark.asyncio
async def test_get_option(client: Any) -> None:
    c, http, ws = client
    ws._next_result = {"max-connection-per-server": "4"}
    await c.connect()
    result = await c.options.get_option("abc")
    assert result["max-connection-per-server"] == "4"
    assert ws.sent[0] == ("aria2.getOption", ["abc"])


@pytest.mark.asyncio
async def test_change_option(client: Any) -> None:
    c, http, ws = client
    await c.connect()
    await c.options.change_option("abc", {"max-connection-per-server": "8"})
    assert ws.sent[0] == ("aria2.changeOption", ["abc", {"max-connection-per-server": "8"}])


@pytest.mark.asyncio
async def test_get_global_option(client: Any) -> None:
    c, http, ws = client
    ws._next_result = {"max-concurrent-downloads": "5"}
    await c.connect()
    result = await c.options.get_global_option()
    assert result["max-concurrent-downloads"] == "5"
    assert ws.sent[0] == ("aria2.getGlobalOption", [])


@pytest.mark.asyncio
async def test_change_global_option(client: Any) -> None:
    c, http, ws = client
    await c.connect()
    await c.options.change_global_option({"max-concurrent-downloads": "3"})
    assert ws.sent[0] == ("aria2.changeGlobalOption", [{"max-concurrent-downloads": "3"}])


# ── StatusManager edge cases ──────────────────────────────


@pytest.mark.asyncio
async def test_tell_active_with_keys(client: Any) -> None:
    c, http, ws = client
    ws._next_result = []
    await c.connect()
    result = await c.status.tell_active(keys=["gid", "status"])
    assert ws.sent[0] == ("aria2.tellActive", [["gid", "status"]])
    assert result == []


@pytest.mark.asyncio
async def test_tell_waiting_with_keys(client: Any) -> None:
    c, http, ws = client
    ws._next_result = []
    await c.connect()
    result = await c.status.tell_waiting(5, 10, keys=["gid"])
    assert ws.sent[0] == ("aria2.tellWaiting", [5, 10, ["gid"]])
    assert result == []


@pytest.mark.asyncio
async def test_tell_stopped(client: Any) -> None:
    c, http, ws = client
    ws._next_result = []
    await c.connect()
    result = await c.status.tell_stopped(0, 50)
    assert ws.sent[0] == ("aria2.tellStopped", [0, 50])
    assert result == []


@pytest.mark.asyncio
async def test_tell_stopped_with_keys(client: Any) -> None:
    c, http, ws = client
    ws._next_result = []
    await c.connect()
    result = await c.status.tell_stopped(0, 50, keys=["gid"])
    assert ws.sent[0] == ("aria2.tellStopped", [0, 50, ["gid"]])
    assert result == []


@pytest.mark.asyncio
async def test_get_uris(client: Any) -> None:
    c, http, ws = client
    ws._next_result = [{"uri": "http://x", "status": "used"}]
    await c.connect()
    result = await c.status.get_uris("abc")
    assert result[0].uri == "http://x"
    assert ws.sent[0] == ("aria2.getUris", ["abc"])


@pytest.mark.asyncio
async def test_get_servers(client: Any) -> None:
    c, http, ws = client
    ws._next_result = [{"index": "1", "servers": []}]
    await c.connect()
    result = await c.status.get_servers("abc")
    assert len(result) == 1
    assert ws.sent[0] == ("aria2.getServers", ["abc"])


@pytest.mark.asyncio
async def test_get_peers(client: Any) -> None:
    c, http, ws = client
    ws._next_result = [{"peerId": "-ABC-", "ip": "1.2.3.4", "port": "6881"}]
    await c.connect()
    result = await c.status.get_peers("abc")
    assert result[0].ip == "1.2.3.4"
    assert ws.sent[0] == ("aria2.getPeers", ["abc"])


# ── DownloadManager control edge cases ────────────────────


@pytest.mark.asyncio
async def test_unpause(client: Any) -> None:
    c, http, ws = client
    await c.connect()
    await c.downloads.unpause("abc")
    assert ws.sent[0] == ("aria2.unpause", ["abc"])


@pytest.mark.asyncio
async def test_unpause_all(client: Any) -> None:
    c, http, ws = client
    await c.connect()
    await c.downloads.unpause_all()
    assert ws.sent[0] == ("aria2.unpauseAll", [])


# ── SystemManager edge cases ──────────────────────────────


@pytest.mark.asyncio
async def test_get_session_info(client: Any) -> None:
    c, http, ws = client
    ws._next_result = {"sessionId": "sess-001"}
    await c.connect()
    result = await c.system.get_session_info()
    assert result["sessionId"] == "sess-001"
    assert ws.sent[0] == ("aria2.getSessionInfo", [])


@pytest.mark.asyncio
async def test_list_notifications(client: Any) -> None:
    c, http, ws = client
    ws._next_result = ["aria2.onDownloadStart", "aria2.onDownloadComplete"]
    await c.connect()
    result = await c.system.list_notifications()
    # list_notifications strips the "aria2." prefix
    assert "onDownloadStart" in result
    assert "onDownloadComplete" in result
    assert ws.sent[0] == ("system.listNotifications", [])


@pytest.mark.asyncio
async def test_purge_download_result(client: Any) -> None:
    c, http, ws = client
    await c.connect()
    await c.system.purge_download_result()
    assert ws.sent[0] == ("aria2.purgeDownloadResult", [])


@pytest.mark.asyncio
async def test_remove_download_result(client: Any) -> None:
    c, http, ws = client
    await c.connect()
    await c.system.remove_download_result("abc")
    assert ws.sent[0] == ("aria2.removeDownloadResult", ["abc"])


# ── EventManager edge cases ───────────────────────────────


@pytest.mark.asyncio
async def test_event_callbacks_all_types(client: Any) -> None:
    c, http, ws = client
    events: list[str] = []

    c.events.on_download_pause(lambda gid=None: events.append("pause"))
    c.events.on_download_stop(lambda gid=None: events.append("stop"))
    c.events.on_bt_download_complete(lambda gid=None: events.append("bt_complete"))

    c._on_event("aria2.onDownloadPause", [])
    c._on_event("aria2.onDownloadStop", [])
    c._on_event("aria2.onBtDownloadComplete", [])

    assert events == ["pause", "stop", "bt_complete"]


@pytest.mark.asyncio
async def test_event_unknown_method_ignored(client: Any) -> None:
    """Unknown event methods are silently ignored."""
    c, http, ws = client
    events: list[str] = []
    c.events.on_download_start(lambda gid=None: events.append("start"))
    c._on_event("aria2.onUnknownEvent", [])
    assert events == []


# ── Base model properties ─────────────────────────────────


@pytest.mark.asyncio
async def test_progress_pct_zero_division(client: Any) -> None:
    """progress_pct returns 0 when total_length is 0."""
    c, http, ws = client
    ws._next_result = {
        "gid": "abc",
        "status": "active",
        "totalLength": "0",
        "completedLength": "0",
        "downloadSpeed": "0",
        "uploadSpeed": "0",
    }
    await c.connect()
    status = await c.status.tell_status("abc")
    assert status.progress_pct == 0.0
    assert status.speed_kbps == 0.0
    # ActiveStatus overrides is_active → True
    assert status.is_active is True
    assert status.is_complete is False
    assert status.is_error is False


# ── Client lifecycle edge cases ───────────────────────────


@pytest.mark.asyncio
async def test_context_manager(client: Any) -> None:
    """Async context manager connects and closes."""
    c, http, ws = client
    async with c:
        assert http.is_connected
        assert ws.is_connected
    assert not http.is_connected
    assert not ws.is_connected


@pytest.mark.asyncio
async def test_enable_ws_false() -> None:
    """Client with enable_ws=False has no WebSocket transport."""
    c = Aria2Client(secret=None, enable_ws=False, timeout=1.0)
    assert c._ws is None
    async with c:
        assert c._http.is_connected
    assert not c._http.is_connected


@pytest.mark.asyncio
async def test_ws_connect_degrades_gracefully() -> None:
    """When WS connection fails, client degrades to HTTP-only."""
    c = Aria2Client(host="127.0.0.99", port=18999, secret="x", enable_ws=True, timeout=1.0)
    await c.connect()
    assert c._http.is_connected
    await c.close()


# ── Model property edge cases ─────────────────────────────


@pytest.mark.asyncio
async def test_progress_pct_non_zero(client: Any) -> None:
    """progress_pct computes correctly when total_length > 0."""
    c, http, ws = client
    ws._next_result = {
        "gid": "abc",
        "status": "active",
        "totalLength": "200",
        "completedLength": "50",
        "downloadSpeed": "1024",
        "uploadSpeed": "512",
    }
    await c.connect()
    status = await c.status.tell_status("abc")
    assert status.progress_pct == 25.0
    assert status.speed_kbps == 1.0


@pytest.mark.asyncio
async def test_is_active_false_for_complete(client: Any) -> None:
    """is_active is False for completed downloads."""
    c, http, ws = client
    ws._next_result = {
        "gid": "abc",
        "status": "complete",
        "totalLength": "100",
        "completedLength": "100",
        "downloadSpeed": "0",
        "uploadSpeed": "0",
    }
    await c.connect()
    status = await c.status.tell_status("abc")
    assert status.is_complete is True
    assert status.is_active is False
    assert status.is_error is False


@pytest.mark.asyncio
async def test_status_coercion_enum_value(client: Any) -> None:
    """Status field is coerced from string to DownloadStatus enum."""
    c, http, ws = client
    ws._next_result = {
        "gid": "abc",
        "status": "paused",
        "totalLength": "0",
        "completedLength": "0",
        "downloadSpeed": "0",
        "uploadSpeed": "0",
    }
    await c.connect()
    status = await c.status.tell_status("abc")
    assert status.status.value == "paused"
