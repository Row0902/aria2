---
name: logging-sdk
description: "Trigger: logging, SDK logging, debug logging, log levels, structured logging, secrets masking, log configuration. Python logging best practices for SDKs — levels, context, secrets, debugging."
license: Apache-2.0
metadata:
  author: gentleman-programming
  version: "1.0"
---

## When to Use

- Adding logging to SDK internals for debugging
- Configuring log levels for different environments
- Masking secrets (tokens, passwords) in logs
- Tracing requests and responses at debug level
- Providing user control over SDK logging verbosity
- Diagnosing connection issues without source code access

## Critical Patterns

### Namespaced Logger

Every SDK module gets its own logger:

```python
import logging

logger = logging.getLogger(__name__)  # e.g., "aria2.client.transport.http"
```

This allows users to control log levels per-package:

```python
import logging

logging.basicConfig(level=logging.WARNING)       # Default: warnings only
logging.getLogger("aria2").setLevel(logging.DEBUG)  # SDK debug tracing
logging.getLogger("aria2.client.transport.http").setLevel(logging.DEBUG)  # HTTP only
```

### Log Levels for SDKs

| Level | Usage |
|---|---|
| `DEBUG` | Request/response bodies, connection details, internal state |
| `INFO` | Lifecycle events: connected, disconnected, reconnected |
| `WARNING` | Degraded behavior (WS fallback to HTTP), retries |
| `ERROR` | Failed requests, connection errors (recoverable) |
| `CRITICAL` | Unrecoverable errors (never used in normal operation) |

### Request/Response Tracing

```python
async def send_request(self, method: str, params: list[Any]) -> Any:
    logger.debug("→ %s(%s)", method, _mask_secrets(params))

    try:
        resp = await self._client.post(url, json=body)
        data = resp.json()
        logger.debug("← %s → %s", method, data.get("result"))
        return _parse(data)
    except httpx.HTTPError as e:
        logger.error("✗ %s failed: %s", method, e)
        raise Aria2ConnectionError(str(e)) from e
```

### Mask Secrets

Never log token/secrets:

```python
def _mask_secrets(params: list[Any]) -> list[Any]:
    """Replace token:xxx with token:*** for safe logging."""
    return [
    p if not (isinstance(p, str) and p.startswith("token:")) else "token:***"
        for p in params
    ]
```

### Lifecycle Logging

```python
async def connect(self) -> None:
    logger.info("Connecting to %s:%d", self._host, self._port)
    try:
        timeout = httpx.Timeout(self._timeout)
        self._client = httpx.AsyncClient(timeout=timeout)
        logger.debug("HTTP client created (timeout=%s)", self._timeout)
    except Exception as e:
        logger.critical("Failed to create HTTP client: %s", e)
        raise

async def close(self) -> None:
    logger.info("Closing transport to %s:%d", self._host, self._port)
    if self._client:
        await self._client.aclose()
        logger.debug("HTTP client closed")
```

### Degradation Logging

```python
async def connect(self) -> None:
    await self._http.connect()
    if self._ws:
        try:
            await self._ws.connect()
            logger.info("WebSocket connected — using WS as primary transport")
        except Exception:
            logger.warning("WebSocket unavailable — degrading to HTTP-only")
            self._ws = None
```

### User-Configurable Logging

Document that users can enable debug logging:

```python
import logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
```

Or via environment variable:

```python
import os
if os.getenv("ARIA2_DEBUG"):
    logging.getLogger("aria2").setLevel(logging.DEBUG)
```

### Structured Logging (for advanced users)

```python
logger.debug(
    "RPC call",
    extra={"method": method, "params": _mask_secrets(params), "request_id": req_id},
)
```

### Connection Status Logging

```python
async def _reader_loop(self) -> None:
    logger.debug("Reader loop started")
    try:
        async for raw in self._ws:
            self._dispatch(raw)
    except websockets.ConnectionClosed as e:
        logger.info("WebSocket connection closed: %s", e)
    except Exception:
        logger.exception("Reader loop crashed")
```

Use `logger.exception()` inside except blocks to capture full tracebacks.

### Reconnection Logging

```python
async def _reconnect(self) -> None:
    backoff = 1
    while self._should_reconnect:
        try:
            logger.info("Reconnecting in %ds...", backoff)
            await asyncio.sleep(backoff)
            await self._ws.connect()
            logger.info("Reconnected successfully")
            return
        except Exception:
            backoff = min(backoff * 2, 30)
            logger.warning("Reconnect failed, retrying in %ds", backoff)
    logger.info("Reconnection cancelled")
```

## Best Practices for SDKs

### 1. Lazy string formatting
Use `%s` formatting with logger, not f-strings:
```python
logger.debug("Params: %s", params)    # ✅
logger.debug(f"Params: {params}")     # ❌ (always evaluated)
```

### 2. Never leak secrets
Create a `_mask_secrets()` helper and use it for all log calls that may contain auth tokens.

### 3. Trace at DEBUG, report at INFO/WARNING
Request/response bodies are DEBUG. Lifecycle events are INFO. Failures are WARNING or ERROR.

### 4. Use `logger.exception()` in except blocks
```python
except Exception:
    logger.exception("Failed to send RPC")  # Includes traceback
```

### 5. Don't log in hot paths
If a function is called thousands of times, don't log DEBUG on every call. Use counters or sampling.

### 6. Name loggers after modules
`logger = logging.getLogger(__name__)` — consistent, hierarchical, user-controllable.

### 7. Provide a `__str__` or `__repr__` for models
```python
class Aria2Error(Exception):
    def __str__(self) -> str:
        return f"[{self.code}] {self.message}"
```

## Common Pitfalls

- **Secrets in logs**: Always mask `token:` before logging params.
- **F-strings in log calls**: Python evaluates arguments even if the log level is not enabled. Use `%s` formatting.
- **Over-logging in hot paths**: Request parsing, event dispatch — log at DEBUG and let users opt-in.
- **Missing `__name__`**: Using a hardcoded string instead of `__name__` breaks logger hierarchy.
- **User can't control levels**: If the SDK sets `logging.basicConfig`, it overrides user settings. Let the user configure.

## Resources

- Python logging docs: <https://docs.python.org/3/library/logging.html>
- Logging HOWTO: <https://docs.python.org/3/howto/logging.html>
- Logging cookbook: <https://docs.python.org/3/howto/logging-cookbook.html>
