"""Tests for the aria2 SDK."""

from __future__ import annotations

import json

import pytest

from aria2.errors import Aria2RpcError
from aria2.rpc import (
    build_request,
    build_request_with_secret,
    parse_notification,
    parse_response,
)
from aria2.types import GID, DownloadStatus, PositionHow


class TestTypes:
    def test_gid_newtype(self) -> None:
        gid = GID("abc1234567890123456789012345678901")
        assert isinstance(gid, str)
        assert gid == "abc1234567890123456789012345678901"

    def test_download_status_values(self) -> None:
        assert DownloadStatus.ACTIVE == "active"
        assert DownloadStatus.COMPLETE == "complete"
        assert DownloadStatus.ERROR == "error"

    def test_download_status_comparison(self) -> None:
        """StrEnum allows direct string comparison."""
        assert DownloadStatus("active") == DownloadStatus.ACTIVE
        assert DownloadStatus.ACTIVE == "active"

    def test_position_how_values(self) -> None:
        assert PositionHow.SET == "POS_SET"
        assert PositionHow.CUR == "POS_CUR"
        assert PositionHow.END == "POS_END"


class TestRpc:
    def test_build_request(self) -> None:
        raw = build_request("aria2.addUri", [["http://x"]], request_id=1)
        obj = json.loads(raw)
        assert obj["jsonrpc"] == "2.0"
        assert obj["method"] == "aria2.addUri"
        assert obj["params"] == [["http://x"]]
        assert obj["id"] == 1

    def test_build_request_with_secret(self) -> None:
        raw = build_request_with_secret("aria2.tellStatus", "mytoken", ["abc123"], request_id=5)
        obj = json.loads(raw)
        assert obj["params"][0] == "token:mytoken"
        assert obj["params"][1] == "abc123"

    def test_build_request_no_secret(self) -> None:
        raw = build_request_with_secret("aria2.addUri", None, [["http://x"]], request_id=2)
        obj = json.loads(raw)
        assert obj["params"] == [["http://x"]]

    def test_parse_response_success(self) -> None:
        resp = json.dumps(
            {
                "jsonrpc": "2.0",
                "result": "abc123",
                "id": 1,
            }
        )
        assert parse_response(resp) == "abc123"

    def test_parse_response_error(self) -> None:
        resp = json.dumps(
            {
                "jsonrpc": "2.0",
                "error": {"code": -1, "message": "Test error"},
                "id": 1,
            }
        )
        with pytest.raises(Aria2RpcError) as exc:
            parse_response(resp)
        assert exc.value.code == -1
        assert "Test error" in exc.value.message

    def test_parse_response_error_with_data(self) -> None:
        resp = json.dumps(
            {
                "jsonrpc": "2.0",
                "error": {"code": 1, "message": "Err", "data": {"key": "val"}},
                "id": 1,
            }
        )
        with pytest.raises(Aria2RpcError) as exc:
            parse_response(resp)
        assert exc.value.data == {"key": "val"}

    def test_parse_notification_returns_tuple(self) -> None:
        notif = json.dumps(
            {
                "jsonrpc": "2.0",
                "method": "aria2.onDownloadStart",
                "params": [{"gid": "abc"}],
            }
        )
        result = parse_notification(notif)
        assert result is not None
        method, params = result
        assert method == "aria2.onDownloadStart"
        assert params == [{"gid": "abc"}]

    def test_parse_notification_response_returns_none(self) -> None:
        resp = json.dumps(
            {
                "jsonrpc": "2.0",
                "result": "ok",
                "id": 1,
            }
        )
        assert parse_notification(resp) is None
