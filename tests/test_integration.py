"""Integration tests against a real aria2c daemon.

These tests start a local aria2c instance via the ``integration_client``
fixture and exercise real RPC calls.  They are automatically skipped when
no aria2c binary is available (e.g. CI without bundled binary).

Torrent and Metalink test data are generated inline — no external files.
"""

from __future__ import annotations

import pytest

from aria2 import Aria2Client, DownloadStatus

pytestmark = pytest.mark.asyncio


# ── Helpers — test data generators ─────────────────────────────


def _minimal_torrent() -> bytes:
    """Build a minimal but structurally valid .torrent bytestring.

    The torrent has a single 1024-byte file and a fake info-hash.
    aria2c will accept it via addTorrent but the download will stall
    (no real trackers/pieces).
    """
    # Bencode: d 8:announce 25:http://fake-tracker.example.com 4:info d ... e e
    info_dict = (
        b"d"
        b"6:lengthi1024e"
        b"4:name4:test"
        b"12:piece lengthi16384e"
        b"6:pieces20:"
        + b"\x00" * 20  # fake SHA-1 hashes
        + b"e"
    )
    return b"d8:announce25:http://fake-tracker.example.com4:info" + info_dict + b"e"


def _minimal_metalink() -> bytes:
    """Build a minimal valid Metalink v4 XML bytestring."""
    return (
        b'<?xml version="1.0" encoding="UTF-8"?>\n'
        b'<metalink xmlns="urn:ietf:params:xml:ns:metalink">\n'
        b'  <file name="test.txt">\n'
        b"    <size>4</size>\n"
        b"    <url>https://example.com/test.txt</url>\n"
        b"  </file>\n"
        b"</metalink>\n"
    )


# ── Tests ──────────────────────────────────────────────────────


async def test_get_version(integration_client: Aria2Client) -> None:
    """Verify basic connectivity: system.getVersion returns daemon info."""
    version = await integration_client.system.get_version()
    assert version.version != ""
    assert len(version.enabled_features) > 0


async def test_add_uri_and_tell_status(integration_client: Aria2Client) -> None:
    """Add a download by URI and query its status."""
    gid = await integration_client.downloads.add_uri(
        ["http://127.0.0.1:1/nonexistent"],
        options={"max-connection-per-server": "1"},
    )
    assert gid != ""
    assert len(gid) == 32  # aria2 GIDs are 32 hex chars

    status = await integration_client.status.tell_status(gid)
    assert status.gid == gid
    assert status.status in (DownloadStatus.ACTIVE, DownloadStatus.ERROR)


async def test_add_uri_with_position(integration_client: Aria2Client) -> None:
    """Add a download at a specific queue position."""
    gid = await integration_client.downloads.add_uri(
        ["http://127.0.0.1:1/nonexistent"],
        position=0,
    )
    assert gid != ""


async def test_add_torrent(integration_client: Aria2Client) -> None:
    """Add a download from a torrent bytestring."""
    torrent_data = _minimal_torrent()
    gid = await integration_client.downloads.add_torrent(torrent_data)
    assert gid != ""
    assert len(gid) == 32


async def test_add_torrent_with_web_seeds(integration_client: Aria2Client) -> None:
    """Add a torrent with web seed URIs for alternative download sources."""
    torrent_data = _minimal_torrent()
    web_seeds = ["https://example.com/test.txt"]
    gid = await integration_client.downloads.add_torrent(
        torrent_data,
        uris=web_seeds,
    )
    assert gid != ""
    assert len(gid) == 32


async def test_add_torrent_with_options(integration_client: Aria2Client) -> None:
    """Add a torrent with per-download options."""
    torrent_data = _minimal_torrent()
    gid = await integration_client.downloads.add_torrent(
        torrent_data,
        options={"max-connection-per-server": "2"},
    )
    assert gid != ""
    assert len(gid) == 32


async def test_add_metalink(integration_client: Aria2Client) -> None:
    """Add a download from a Metalink v4 XML bytestring.

    Returns a list of GIDs (one per file in the metalink).
    """
    metalink_data = _minimal_metalink()
    gids = await integration_client.downloads.add_metalink(metalink_data)
    assert len(gids) >= 1
    for gid in gids:
        assert len(gid) == 32


async def test_pause_unpause_remove_flow(integration_client: Aria2Client) -> None:
    """Full lifecycle: add → pause → unpause → remove."""
    # Add
    gid = await integration_client.downloads.add_uri(
        ["http://127.0.0.1:1/slow-download"],
    )
    assert gid != ""

    # Pause
    result = await integration_client.downloads.pause(gid)
    assert result == gid

    status = await integration_client.status.tell_status(gid)
    assert status.status == DownloadStatus.PAUSED

    # Unpause
    result = await integration_client.downloads.unpause(gid)
    assert result == gid

    # Remove
    result = await integration_client.downloads.remove(gid, force=True)
    assert result == gid

    status = await integration_client.status.tell_status(gid)
    assert status.status == DownloadStatus.REMOVED


async def test_pause_all_unpause_all(integration_client: Aria2Client) -> None:
    """Pause and resume all downloads."""
    gid1 = await integration_client.downloads.add_uri(
        ["http://127.0.0.1:1/a"],
    )
    gid2 = await integration_client.downloads.add_uri(
        ["http://127.0.0.1:1/b"],
    )

    await integration_client.downloads.pause_all()
    s1 = await integration_client.status.tell_status(gid1)
    s2 = await integration_client.status.tell_status(gid2)
    assert s1.status == DownloadStatus.PAUSED
    assert s2.status == DownloadStatus.PAUSED

    await integration_client.downloads.unpause_all()
    s1 = await integration_client.status.tell_status(gid1)
    s2 = await integration_client.status.tell_status(gid2)
    assert s1.status == DownloadStatus.ACTIVE
    assert s2.status == DownloadStatus.ACTIVE

    # Cleanup
    await integration_client.downloads.remove(gid1, force=True)
    await integration_client.downloads.remove(gid2, force=True)


async def test_change_position(integration_client: Aria2Client) -> None:
    """Reorder downloads in the queue."""
    gid1 = await integration_client.downloads.add_uri(
        ["http://127.0.0.1:1/first"],
    )
    gid2 = await integration_client.downloads.add_uri(
        ["http://127.0.0.1:1/second"],
    )

    # Move gid2 to position 0 (first in queue)
    new_pos = await integration_client.downloads.change_position(
        gid2,
        0,
        how="POS_SET",
    )
    assert isinstance(new_pos, int)

    await integration_client.downloads.remove(gid1, force=True)
    await integration_client.downloads.remove(gid2, force=True)


async def test_get_global_stat(integration_client: Aria2Client) -> None:
    """Query global statistics from the daemon."""
    stat = await integration_client.status.get_global_stat()
    assert stat.num_active == "0" or int(stat.num_active) >= 0
    assert stat.download_speed is not None


async def test_list_methods(integration_client: Aria2Client) -> None:
    """List available RPC methods from the daemon."""
    methods = await integration_client.system.list_methods()
    assert isinstance(methods, list)
    assert "aria2.addUri" in methods
    assert "aria2.tellStatus" in methods


async def test_list_notifications(integration_client: Aria2Client) -> None:
    """List available RPC notifications from the daemon."""
    notifications = await integration_client.system.list_notifications()
    assert isinstance(notifications, list)
    assert "aria2.onDownloadStart" in notifications


async def test_get_session_info(integration_client: Aria2Client) -> None:
    """Query session information."""
    info = await integration_client.system.get_session_info()
    assert "sessionId" in info


async def test_multicall(integration_client: Aria2Client) -> None:
    """Batch multiple RPC calls into a single request."""
    results = await integration_client.multicall(
        [
            {"methodName": "aria2.getVersion", "params": []},
            {"methodName": "aria2.listMethods", "params": []},
        ]
    )
    assert len(results) == 2
    assert isinstance(results[0], dict)
    assert "version" in results[0]
    assert isinstance(results[1], list)


async def test_tell_active(integration_client: Aria2Client) -> None:
    """List currently active downloads."""
    active = await integration_client.status.tell_active()
    assert isinstance(active, list)


async def test_get_option(integration_client: Aria2Client) -> None:
    """Query per-download options (after adding a download)."""
    gid = await integration_client.downloads.add_uri(
        ["http://127.0.0.1:1/opts-test"],
    )
    opts = await integration_client.options.get_option(gid)
    assert isinstance(opts, dict)
    assert "max-connection-per-server" in opts

    await integration_client.downloads.remove(gid, force=True)
