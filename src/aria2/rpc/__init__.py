"""JSON-RPC 2.0 protocol helpers."""

from __future__ import annotations

import json
from typing import Any

from aria2.errors import Aria2RpcError

JSON_RPC_VERSION = "2.0"


def build_request(
    method: str,
    params: list[Any],
    *,
    request_id: int = 0,
) -> str:
    """Build a JSON-RPC 2.0 request string.

    If the client has configured a secret, the params are prefixed
    with ``["token:{secret}", ...]`` before serialization.
    """
    payload: dict[str, Any] = {
        "jsonrpc": JSON_RPC_VERSION,
        "method": method,
        "params": params,
        "id": request_id,
    }
    return json.dumps(payload, ensure_ascii=False)


def build_request_with_secret(
    method: str,
    secret: str | None,
    params: list[Any],
    *,
    request_id: int = 0,
) -> str:
    """Build a JSON-RPC request with optional token-based auth.

    aria2 uses the convention of prepending ``"token:{secret}"`` as the
    first element of the params array.
    """
    if secret:
        effective_params: list[Any] = [f"token:{secret}", *params]
    else:
        effective_params = params
    return build_request(method, effective_params, request_id=request_id)


def parse_response(data: str) -> Any:
    """Parse a JSON-RPC 2.0 response string.

    Returns the ``result`` field on success.

    Raises:
        Aria2RpcError: if the response contains an ``error`` field.
        json.JSONDecodeError: if the response is not valid JSON.
    """
    obj: dict[str, Any] = json.loads(data)
    if "error" in obj:
        err = obj["error"]
        raise Aria2RpcError(
            code=err.get("code", -1),
            message=err.get("message", "Unknown RPC error"),
            data=err.get("data"),
        )
    return obj.get("result")


def parse_notification(data: str) -> tuple[str, list[Any]] | None:
    """Parse a JSON-RPC 2.0 notification (no ``id`` field).

    Returns ``(method, params)`` or ``None`` if this is a response (has id).

    Raises:
        json.JSONDecodeError: if the response is not valid JSON.
    """
    obj: dict[str, Any] = json.loads(data)
    # Notifications have no "id" field
    if "id" in obj:
        return None
    return (obj["method"], obj.get("params", []))


__all__ = [
    "build_request",
    "build_request_with_secret",
    "parse_notification",
    "parse_response",
]
