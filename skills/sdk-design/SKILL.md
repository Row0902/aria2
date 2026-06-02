---
name: sdk-design
description: "Trigger: SDK design, client pattern, transport abstraction, error wrapping, event dispatch, callback, API client. Patterns for designing robust async Python SDKs — client lifecycle, abstraction layers, error handling."
license: Apache-2.0
metadata:
  author: gentleman-programming
  version: "1.0"
---

## When to Use

- Designing the public API of an SDK client class
- Structuring transport abstraction (pluggable HTTP/WS backends)
- Managing client lifecycle (connect, use, close)
- Implementing event/callback systems for push notifications
- Wrapping external errors into SDK-specific exceptions
- Handling authentication (secrets, tokens)
- Graceful degradation (fallback from WS to HTTP)

## Critical Patterns

### Client Lifecycle (Async Context Manager)

Every SDK client should support both explicit and context-manager usage:

```python
class Aria2Client:
    """Async JSON-RPC client for aria2."""

    async def connect(self) -> None:
        """Establish connections to the daemon."""
        await self._http.connect()
        if self._ws:
            try:
                await self._ws.connect()
            except Exception:
                pass  # Degrade to HTTP-only gracefully

    async def close(self) -> None:
        """Release all resources."""
        if self._ws:
            await self._ws.close()
        await self._http.close()

    async def __aenter__(self) -> Aria2Client:
        await self.connect()
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.close()
```

Usage:

```python
# Context manager (preferred)
async with Aria2Client(secret="token") as client:
    gid = await client.add_uri(["https://example.com/file"])

# Explicit lifecycle
client = Aria2Client(secret="token")
await client.connect()
try:
    gid = await client.add_uri(["https://example.com/file"])
finally:
    await client.close()
```

### Transport Abstraction

Define an abstract interface, then implement per-protocol:

```python
class Transport(ABC):
    @abstractmethod
    async def connect(self) -> None: ...
    @abstractmethod
    async def send_request(self, method: str, params: list[Any]) -> Any: ...
    @abstractmethod
    async def close(self) -> None: ...
    @property
    @abstractmethod
    def is_connected(self) -> bool: ...

class HttpTransport(Transport):   # httpx-based
class WebSocketTransport(Transport):  # websockets-based
```

Benefits:
- New protocols can be added without changing the client
- Testing: mock the transport, test the client in isolation
- Each transport manages its own connection lifecycle

### Transport Routing (Primary/Fallback)

Route requests through available transports:

```python
async def _request(self, method: str, params: list[Any]) -> Any:
    """Send RPC via WebSocket if connected, fall back to HTTP."""
    if self._ws and self._ws.is_connected:
        return await self._ws.send_request(method, params)
    return await self._http.send_request(method, params)
```

### Event Dispatch (WebSocket Notifications)

```python
class Aria2Client:
    _callbacks: dict[str, list[Callable]] = defaultdict(list)

    def _emit(self, event: str, *args: Any) -> None:
        for cb in self._callbacks.get(event, []):
            try:
                cb(*args)
            except Exception:
                pass  # Isolate callback errors

    # Public registration methods
    def on_download_start(self, cb: Callable[[GID], Any]) -> None:
        self._callbacks["aria2.onDownloadStart"].append(cb)

    def on_download_complete(self, cb: Callable[[GID], Any]) -> None:
        self._callbacks["aria2.onDownloadComplete"].append(cb)
```

### Error Hierarchy (Wrapping External Errors)

```python
class Aria2Error(Exception):
    """Base for all SDK errors."""

class Aria2ConnectionError(Aria2Error):
    """Connection failed or lost."""

class Aria2AuthError(Aria2Error):
    """Authentication with token failed."""

class Aria2RpcError(Aria2Error):
    """JSON-RPC error from daemon."""
    def __init__(self, code: int, message: str, data: object = None):
        self.code = code
        self.message = message
        self.data = data
        super().__init__(f"[{code}] {message}")

class Aria2BinaryNotFoundError(Aria2Error):
    """aria2c binary not found on system."""
```

Never let third-party exceptions (httpx, websockets, json) propagate to SDK users. Wrap them:

```python
try:
    resp = await self._client.post(url, json=body)
except httpx.ConnectError as e:
    raise Aria2ConnectionError(f"Cannot connect: {e}") from e
except httpx.TimeoutException as e:
    raise Aria2ConnectionError(f"Request timed out: {e}") from e
```

### Authentication (Secret/Token)

```python
def __init__(self, host: str = "localhost", port: int = 6800, secret: str | None = None):
    self._secret = secret

def _build_params(self, params: list[Any]) -> list[Any]:
    """Prepend token: to params if secret is set."""
    if self._secret:
        return [f"token:{self._secret}", *params]
    return params
```

### Graceful Degradation

SDK degrades gracefully when WebSocket is unavailable:

```python
async def connect(self) -> None:
    await self._http.connect()
    if self._ws:
        try:
            await self._ws.connect()
        except Exception:
            self._ws = None  # Fall back to HTTP-only

async def _request(self, method, params):
    if self._ws:
        try:
            return await self._ws.send_request(method, params)
        except Aria2ConnectionError:
            self._ws = None  # Disable WS on failure
    return await self._http.send_request(method, params)
```

### Snake Case Conversion

aria2 returns camelCase keys. Convert to snake_case for Pythonic APIs:

```python
@staticmethod
def _to_snake_case(name: str) -> str:
    """Convert camelCase to snake_case."""
    import re
    return re.sub(r"(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", "_", name).lower()

def _snake_keys(self, data: dict) -> dict:
    """Recursively convert dict keys to snake_case."""
    if isinstance(data, dict):
        return {self._to_snake_case(k): self._snake_keys(v) for k, v in data.items()}
    return data
```

### RPC Method Mapping

```python
async def tell_status(self, gid: str, keys: list[str] | None = None) -> DownloadStatusResponse:
    """Return the current status of a download."""
    params: list[Any] = [gid]
    if keys is not None:
        params.append(keys)
    data = await self._request("aria2.tellStatus", params)
    return _parse_status(data)
```

### Version and Session Info

```python
async def get_version(self) -> Aria2Version:
    """Return version information about the daemon."""
    return await self._request("aria2.getVersion", [])

async def get_session_info(self) -> SessionInfo:
    """Return session information."""
    return await self._request("aria2.getSessionInfo", [])
```

### Multicall (Batch)

```python
async def multicall(self, calls: list[dict]) -> list[Any]:
    """Execute multiple RPC calls in a single HTTP request."""
    return await self._request("system.multicall", [calls])
```

## Best Practices for SDKs

### 1. Prefer async context managers
Always support `async with`. It prevents resource leaks.

### 2. Isolate third-party dependencies
Wrap httpx, websockets, and other libraries behind the `Transport` ABC.

### 3. Never leak third-party exceptions
Wrap all external errors in your SDK's error hierarchy.

### 4. Degrade gracefully
If a secondary transport fails, fall back silently. Don't crash `connect()`.

### 5. Keep callbacks isolated
Never let a user callback exception break your internal event loop.

### 6. Document threading model
SDK is asyncio-only. Document that callbacks run in the event loop and shouldn't block.

### 7. Make `__init__` cheap
Do I/O in `connect()`, not the constructor.

### 8. Provide a `close()` that's safe to call multiple times
Idempotent close prevents double-close errors.

## Common Pitfalls

- **Expensive `__init__`**: Don't connect or allocate I/O resources in the constructor.
- **Leaking exceptions**: Always wrap httpx/websocket exceptions in SDK exceptions.
- **Missing `__aexit__`**: Without context manager support, users are more likely to leak connections.
- **Callback exceptions crashing the loop**: Any unhandled exception in a callback kills the event loop.
- **Shared mutable state**: Don't share client instances across tasks without locks.
- **No `__all__`**: In `__init__.py`, always define `__all__` to control the public API surface.

## Resources

- Google API design guide: <https://cloud.google.com/apis/design>
- Microsoft REST API guidelines: <https://github.com/microsoft/api-guidelines>
- Python SDK patterns (Stripe): <https://github.com/stripe/stripe-python>
