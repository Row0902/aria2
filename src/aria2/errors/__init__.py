"""Error hierarchy for the aria2 SDK."""

from __future__ import annotations


class Aria2Error(Exception):
    """Base exception for all aria2 SDK errors."""


class Aria2ConnectionError(Aria2Error):
    """Raised when the client cannot connect to the aria2 RPC server."""


class Aria2AuthError(Aria2Error):
    """Raised when authentication with the aria2 RPC server fails."""


class Aria2RpcError(Aria2Error):
    """Raised when aria2 returns a JSON-RPC error response.

    Attributes:
        code: The JSON-RPC error code.
        message: The error message from the server.
        data: Optional additional error data.
    """

    def __init__(
        self,
        code: int,
        message: str,
        data: object = None,
    ) -> None:
        self.code = code
        self.message = message
        self.data = data
        super().__init__(f"[{code}] {message}")


class Aria2BinaryNotFoundError(Aria2Error):
    """Raised when the aria2c binary cannot be located."""


__all__ = [
    "Aria2AuthError",
    "Aria2BinaryNotFoundError",
    "Aria2ConnectionError",
    "Aria2Error",
    "Aria2RpcError",
]
