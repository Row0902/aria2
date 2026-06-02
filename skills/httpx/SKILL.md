---
name: httpx
description: "Trigger: httpx, HTTP client, AsyncClient, HTTP request, timeout, connection pool, HTTP transport. Modern async HTTP client for Python — SDK's core transport layer."
license: Apache-2.0
metadata:
  author: gentleman-programming
  version: "1.0"
---

## When to Use

- Sending HTTP requests to the aria2 JSON-RPC endpoint
- Configuring `httpx.AsyncClient` with proper timeouts and connection pooling
- Handling HTTP errors, retries, and connection failures
- Managing client lifecycle (connect / close)
- Testing HTTP interactions with mock transports (respx)
- Streaming responses or large payloads

## Critical Patterns

### Client Lifecycle

Use `httpx.AsyncClient` as a context manager or explicit open/close:

```python
import httpx

# Context manager (preferred for short-lived)
async with httpx.AsyncClient(timeout=30.0) as client:
    resp = await client.post("http://localhost:6800/jsonrpc", json=body)
    resp.raise_for_status()

# Explicit lifecycle (preferred for long-lived SDK clients)
client = httpx.AsyncClient(timeout=httpx.Timeout(30.0))
await client.aclose()
```

**In an SDK**, the client lives as long as the transport. Create once in `connect()`, close once in `close()`:

```python
class HttpTransport(Transport):
    async def connect(self) -> None:
        timeout = httpx.Timeout(self._timeout)
        self._client = httpx.AsyncClient(timeout=timeout)

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
```

### Timeout Configuration

```python
# Single timeout for all phases
httpx.AsyncClient(timeout=30.0)

# Granular per-phase timeouts
httpx.AsyncClient(timeout=httpx.Timeout(
    connect=5.0,      # Connection establishment
    read=30.0,        # Reading response body
    write=10.0,       # Sending request body
    pool=5.0,         # Waiting for connection from pool
))

# Per-request override
client.post(url, json=body, timeout=httpx.Timeout(connect=2.0, read=10.0))
```

### Error Handling

```python
import httpx
from aria2.errors import Aria2ConnectionError, Aria2RpcError

try:
    resp = await self._client.post(url, json=body)
    resp.raise_for_status()
except httpx.ConnectError as e:
    raise Aria2ConnectionError(f"Cannot connect: {e}") from e
except httpx.TimeoutException as e:
    raise Aria2ConnectionError(f"Request timed out: {e}") from e
except httpx.HTTPStatusError as e:
    raise Aria2RpcError(code=resp.status_code, message=str(e)) from e
```

### Connection Pooling

`httpx.AsyncClient` uses a connection pool by default (up to 10 connections per host). Configure:

```python
limits = httpx.Limits(
    max_keepalive_connections=5,   # Idle connections to keep in pool
    max_connections=10,            # Total connections in pool
    keepalive_expiry=30.0,         # Idle timeout before closing
)

client = httpx.AsyncClient(limits=limits, timeout=30.0)
```

- Pool is per-client instance. Each `HttpTransport` gets its own pool.
- No need to adjust for most SDKs — defaults handle single-host JSON-RPC well.
- Connection reuse avoids TCP handshake overhead on every request.

### JSON-RPC Request Pattern

```python
async def send_request(self, method: str, params: list[Any]) -> Any:
    body = _build(method, params, secret=self._secret)
    url = f"http://{self._host}:{self._port}/jsonrpc"

    try:
        resp = await self._client.post(url, json=body)
        resp.raise_for_status()
        data = resp.json()
    except httpx.HTTPError as e:
        raise Aria2ConnectionError(str(e)) from e

    return _parse(data)
```

### Secret/Auth Token

aria2 uses a "token:" prefix in params for authentication. The httpx transport wraps params:

```python
def _build_params(method: str, params: list[Any], secret: str | None) -> list[Any]:
    if secret:
        return [f"token:{secret}", *params]
    return params
```

The secret itself should never appear in logs.

### Redirects and Follow-up

By default, httpx follows redirects. For JSON-RPC, disable:

```python
client = httpx.AsyncClient(follow_redirects=False)
```

### Base URL

If all requests go to the same origin, set `base_url`:

```python
self._client = httpx.AsyncClient(
    base_url=f"http://{host}:{port}",
    timeout=timeout,
)
# Then: client.post("/jsonrpc", json=body)
```

### Event Hooks

httpx supports request/response event hooks for logging or metrics:

```python
def log_request(request):
    print(f"→ {request.method} {request.url}")

def log_response(response):
    print(f"← {response.status_code}")

client = httpx.AsyncClient(
    event_hooks={
        "request": [log_request],
        "response": [log_response],
    }
)
```

Useful for debug logging in SDKs — but never log the request body if it contains the secret.

### Transport Customization

For testing or custom protocols, pass a custom transport:

```python
# Mock transport for testing
client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
```

The project uses **respx** for mocking instead (intercepts at a higher level).

## Best Practices for SDKs

### 1. One client per transport instance
Don't share `httpx.AsyncClient` across independent transports. Create per-instance.

### 2. Always close the client
```python
async def close(self) -> None:
    if self._client:
        await self._client.aclose()
        self._client = None
```

### 3. Wrap httpx exceptions in SDK exceptions
Never let `httpx.HTTPError` propagate to SDK users. Wrap in `Aria2ConnectionError`:

```python
except httpx.HTTPError as e:
    raise Aria2ConnectionError(str(e)) from e
```

### 4. Timeouts are not optional
Always set an explicit timeout. Default is 5 seconds — may be too short or too long. The SDK uses 30.0s.

### 5. Never log secrets
When logging requests, mask `token:` in params:
```python
safe_params = [p if not p.startswith("token:") else "token:***" for p in params]
```

### 6. Use `raise_for_status()` to catch HTTP-level errors
httpx doesn't raise on 4xx/5xx by default. Always call `raise_for_status()` or check `resp.is_error`.

### 7. Prefer `resp.json()` over `json.loads(resp.text)`
`resp.json()` handles encoding and content-type negotiation.

## Common Pitfalls

- **Client not closed**: Unclosed clients leak connections and file descriptors. Always `aclose()`.
- **Shared client across threads**: `httpx.AsyncClient` is not thread-safe. Use one per event loop.
- **Default timeout too short**: `httpx` default timeout is 5s. Long-running RPCs may need 30-60s.
- **Redirects enabled**: JSON-RPC doesn't redirect. Disable `follow_redirects`.
- **Exception hierarchy confusion**: `httpx.HTTPError` catches both `ConnectError`, `TimeoutException`, and `HTTPStatusError`. Catch specific types when you need different handling.

## Commands

```bash
uv run python -c "import httpx; print(httpx.__version__)"
uv run pytest -k "http"            # Run HTTP transport tests
```

## Resources

- Documentation: <https://www.python-httpx.org/>
- Async guide: <https://www.python-httpx.org/async/>
- Exceptions: <https://www.python-httpx.org/exceptions/>
- GitHub: <https://github.com/encode/httpx>
