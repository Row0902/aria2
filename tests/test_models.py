"""Tests for Pydantic model edge cases and parsing."""

from __future__ import annotations

from aria2.client._helpers import snake_keys, to_snake_case
from aria2.models.download_response import _parse_status
from aria2.models.file import FileInfo
from aria2.models.global_stat import GlobalStat
from aria2.models.peer import PeerInfo
from aria2.models.status_complete import CompleteStatus
from aria2.models.status_error import ErrorStatus
from aria2.models.status_paused import PausedStatus
from aria2.models.status_removed import RemovedStatus
from aria2.types import DownloadStatus

# ── _helpers ────────────────────────────────────────────────


class TestHelpers:
    def test_to_snake_case_simple(self) -> None:
        assert to_snake_case("totalLength") == "total_length"
        assert to_snake_case("downloadSpeed") == "download_speed"
        assert to_snake_case("numPieces") == "num_pieces"

    def test_to_snake_case_already_snake(self) -> None:
        assert to_snake_case("gid") == "gid"
        assert to_snake_case("dir") == "dir"

    def test_snake_keys_nested_dict(self) -> None:
        data = {"nestedDict": {"innerKey": "val"}}
        result = snake_keys(data)
        assert result == {"nested_dict": {"inner_key": "val"}}

    def test_snake_keys_list_of_dicts(self) -> None:
        data = {"items": [{"itemName": "a"}, {"itemName": "b"}]}
        result = snake_keys(data)
        assert result == {"items": [{"item_name": "a"}, {"item_name": "b"}]}

    def test_snake_keys_non_dict_passthrough(self) -> None:
        assert snake_keys("string") == "string"  # type: ignore


# ── Discriminated union parsing ────────────────────────────


class TestStatusParsing:
    """Test _parse_status with each status variant."""

    def test_parse_paused_status(self) -> None:
        result = _parse_status({"gid": "abc", "status": "paused", "total_length": "1000"})
        assert isinstance(result, PausedStatus)
        assert result.status == DownloadStatus.PAUSED

    def test_parse_error_status(self) -> None:
        result = _parse_status(
            {
                "gid": "abc",
                "status": "error",
                "total_length": "0",
                "error_code": "1",
                "error_message": "test error",
            }
        )
        assert isinstance(result, ErrorStatus)
        assert result.error_code == "1"
        assert result.error_message == "test error"

    def test_parse_complete_status(self) -> None:
        result = _parse_status({"gid": "abc", "status": "complete", "total_length": "100"})
        assert isinstance(result, CompleteStatus)
        assert result.status == DownloadStatus.COMPLETE

    def test_parse_removed_status(self) -> None:
        result = _parse_status({"gid": "abc", "status": "removed", "total_length": "50"})
        assert isinstance(result, RemovedStatus)
        assert result.status == DownloadStatus.REMOVED


# ── FileInfo ────────────────────────────────────────────────


class TestFileInfo:
    def test_file_info_with_index(self) -> None:
        f = FileInfo.model_validate(
            {
                "index": "1",
                "path": "/tmp/f.txt",
                "length": "100",
                "completed_length": "50",
                "selected": "true",
            }
        )
        assert f.index == "1"
        assert f.length_bytes == 100
        assert f.completed_bytes == 50
        assert f.is_selected is True

    def test_file_info_path(self) -> None:
        f = FileInfo.model_validate(
            {
                "index": "1",
                "path": "/tmp/f.txt",
                "length": "100",
                "completed_length": "100",
                "selected": "false",
            }
        )
        assert f.path.endswith(".txt")
        assert f.is_selected is False

    def test_file_info_length(self) -> None:
        f = FileInfo.model_validate(
            {
                "index": "1",
                "path": "/tmp/f.txt",
                "length": "2048",
                "completed_length": "1024",
                "selected": "true",
            }
        )
        assert f.length == "2048"
        assert f.completed_length == "1024"


# ── GlobalStat ──────────────────────────────────────────────


class TestGlobalStat:
    def test_global_stat_fields(self) -> None:
        s = GlobalStat.model_validate(
            {
                "download_speed": "5000",
                "upload_speed": "1000",
                "num_active": "2",
                "num_waiting": "3",
                "num_stopped": "1",
            }
        )
        assert s.download_speed == "5000"
        assert s.upload_speed == "1000"
        assert s.num_active == "2"

    def test_global_stat_speed_kbps(self) -> None:
        s = GlobalStat.model_validate(
            {
                "download_speed": "102400",
                "upload_speed": "51200",
                "num_active": "1",
                "num_waiting": "0",
                "num_stopped": "0",
            }
        )
        assert s.download_speed_kbps == 100.0
        assert s.upload_speed_kbps == 50.0


# ── PeerInfo ────────────────────────────────────────────────


class TestPeerInfo:
    def test_peer_info_fields(self) -> None:
        p = PeerInfo.model_validate(
            {
                "peer_id": "-UT2220-abc123",
                "ip": "10.0.0.1",
                "port": "6881",
                "bitfield": "ffff",
                "am_choking": "false",
                "peer_choking": "true",
                "download_speed": "50000",
                "upload_speed": "10000",
                "seeder": "false",
            }
        )
        assert p.ip == "10.0.0.1"
        assert p.port == "6881"


# ── Status variant fields ──────────────────────────────────


class TestStatusVariantFields:
    def test_error_status_specific_fields(self) -> None:
        e = ErrorStatus.model_validate(
            {
                "gid": "abc",
                "status": "error",
                "total_length": "0",
                "error_code": "-1",
                "error_message": "timeout",
            }
        )
        assert e.error_code == "-1"
        assert e.error_message == "timeout"

    def test_paused_status_fields(self) -> None:
        p = PausedStatus.model_validate({"gid": "abc", "status": "paused", "total_length": "100"})
        assert p.status == DownloadStatus.PAUSED

    def test_removed_status_fields(self) -> None:
        r = RemovedStatus.model_validate({"gid": "abc", "status": "removed", "total_length": "0"})
        assert r.status == DownloadStatus.REMOVED


# ── __main__ entry point ───────────────────────────────────


class TestMainEntryPoint:
    def test_cli_import(self) -> None:
        """Verify the CLI entry point can be imported."""
        from cli import main

        assert main is not None

    def test_cli_module(self) -> None:
        """Verify __main__ module exists."""
        import importlib

        mod = importlib.import_module("cli.__main__")
        assert mod is not None
