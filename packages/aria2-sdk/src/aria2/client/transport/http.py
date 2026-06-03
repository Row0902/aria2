"""HTTP transport for aria2 JSON-RPC using httpx."""

from __future__ import annotations

from typing import Any

import httpx

from aria2.client.transport import Transport
from aria2.errors import Aria2ConnectionError, Aria2RpcError
from aria2.rpc import build_request as _build_noauth
from aria2.rpc import build_request_with_secret as _build
from aria2.rpc import parse_response as _parse


class HttpTransport(Transport):
    """JSON-RPC over HTTP via httpx.

    Connects to ``http://{host}:{port}/jsonrpc`` using a dedicated
    ``httpx.AsyncClient`` per transport instance.
    """

    def __init__(
        self,
        host: str,
        port: int,
        secret: str | None = None,
        *,
        timeout: float = 30.0,
    ) -> None:
        self._host = host
        self._port = port
        self._secret = secret
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None
        self._request_id = 0

    @property
    def _url(self) -> str:
        return f"http://{self._host}:{self._port}/jsonrpc"

    @property
    def is_connected(self) -> bool:
        """Return whether the HTTP client is active and not closed."""
        return self._client is not None and not self._client.is_closed

    async def connect(self) -> None:
        """Open an HTTP connection to the aria2 RPC endpoint.

        Creates a new ``httpx.AsyncClient`` if one is not already open.
        """
        if self._client is None or self._client.is_closed:
            timeout = httpx.Timeout(self._timeout)
            self._client = httpx.AsyncClient(timeout=timeout)

    async def send_request(self, method: str, params: list[Any], *, add_secret: bool = True) -> Any:
        """Send a JSON-RPC request over HTTP."""
        if not self.is_connected:
            raise Aria2ConnectionError("HTTP transport is not connected")
        self._request_id += 1
        payload = self._build_payload(method, params, add_secret)
        return await self._do_request(payload)

    def _build_payload(self, method: str, params: list[Any], add_secret: bool) -> str:
        if add_secret:
            return _build(method, self._secret, params, request_id=self._request_id)
        return _build_noauth(method, params, request_id=self._request_id)

    async def _do_request(self, payload: str) -> Any:
        """Post JSON-RPC payload and return parsed response."""
        try:
            resp = await self._client.post(  # type: ignore  # guarded by caller
                self._url, content=payload, headers={"Content-Type": "application/json"}
            )
            if resp.status_code != 200:
                raise Aria2ConnectionError(f"HTTP {resp.status_code}: {resp.text[:200]}")
            return _parse(resp.text)
        except Aria2RpcError:
            raise
        except httpx.HTTPError as e:
            raise Aria2ConnectionError(str(e)) from e
        except (TimeoutError, OSError) as e:
            raise Aria2ConnectionError(str(e)) from e

    async def close(self) -> None:
        """Close the HTTP connection and release resources.

        Safe to call multiple times.  Idempotent.
        """
        if self._client and not self._client.is_closed:
            await self._client.aclose()
