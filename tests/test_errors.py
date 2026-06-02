"""Tests for the aria2 error hierarchy."""

from __future__ import annotations

from aria2.errors import (
    Aria2AuthError,
    Aria2BinaryNotFoundError,
    Aria2ConnectionError,
    Aria2Error,
    Aria2RpcError,
)


def test_base_error() -> None:
    assert issubclass(Aria2ConnectionError, Aria2Error)
    assert issubclass(Aria2RpcError, Aria2Error)
    assert issubclass(Aria2AuthError, Aria2Error)
    assert issubclass(Aria2BinaryNotFoundError, Aria2Error)


def test_rpc_error_attributes() -> None:
    err = Aria2RpcError(code=-1, message="Something went wrong", data={"key": "val"})
    assert err.code == -1
    assert "Something went wrong" in err.message
    assert err.data == {"key": "val"}
    assert "[-1]" in str(err)


def test_rpc_error_no_data() -> None:
    err = Aria2RpcError(code=1, message="Error")
    assert err.data is None
    assert "[1] Error" == str(err)


def test_connection_error() -> None:
    err = Aria2ConnectionError("Connection refused")
    assert "Connection refused" in str(err)


def test_auth_error() -> None:
    err = Aria2AuthError("Invalid token")
    assert "Invalid token" in str(err)


def test_binary_not_found() -> None:
    err = Aria2BinaryNotFoundError("aria2c not in PATH")
    assert "aria2c not in PATH" in str(err)
