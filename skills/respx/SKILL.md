---
name: respx
description: "Trigger: respx, mock HTTP, HTTP mocking, httpx mock, mock transport, test HTTP, HTTP test. HTTP mocking library for httpx — mock HTTP requests in tests."
license: Apache-2.0
metadata:
  author: gentleman-programming
  version: "1.0"
---

## When to Use

- Mocking HTTP requests in tests that use httpx
- Simulating aria2 JSON-RPC responses without a live server
- Testing error scenarios (timeouts, 500 errors, connection refused)
- Validating request content (headers, body, URL)
- Replacing real HTTP calls in integration tests

## Critical Patterns

### Basic Usage

```python
import respx
from httpx import Response

# Context manager (isolated mock — preferred)
with respx.mock:
    route = respx.post("http://localhost:6800/jsonrpc").respond(
        json={"jsonrpc": "2.0", "result": "ok", "id": 1}
    )

    result = await transport.send_request("aria2.addUri", [["https://x"]])
    assert result == "ok"
    assert route.called
```

### How It Works

respx intercepts httpx requests at the transport layer. When `respx.mock` is active, httpx calls are routed through respx instead of making real HTTP connections. No server needed.

### Mock Router Patterns

```python
import respx
from httpx import Response

# Match by method + URL
respx.post("http://localhost:6800/jsonrpc").respond(json={"result": "ok"})
respx.get("http://example.com/data").respond(text="hello")

# Match by regex URL
respx.post(url__regex=r"http://localhost:\d+/jsonrpc").respond(...)

# Respond with various content
respx.post(url).respond(
    json={"key": "value"},           # JSON body
    status_code=200,                 # HTTP status
    headers={"X-Custom": "val"},     # Custom headers
)
respx.post(url).respond(text="plain text")
respx.post(url).respond(content=b"bytes")
respx.post(url).respond(status_code=204)  # No content
```

### Simulating Errors

```python
# HTTP error
respx.post(url).respond(status_code=500, text="Internal Server Error")

# Connection timeout
respx.post(url).side_effect = httpx.TimeoutException("Request timed out")

# Connection refused
respx.post(url).side_effect = httpx.ConnectError("Connection refused")

# Multiple responses (first succeeds, second fails)
route = respx.post(url)
route.respond(json={"result": "ok"})
route.side_effect = httpx.ConnectError("Disconnected")
```

### Verifying Requests

```python
with respx.mock:
    route = respx.post("http://localhost:6800/jsonrpc").respond(json={"result": "ok"})

    await transport.send_request("aria2.addUri", [["https://x"]])

    # Check call count
    assert route.called
    assert route.call_count == 1

    # Inspect request
    request = route.calls.last.request
    assert request.method == "POST"
    assert "jsonrpc" in request.url.path
    body = request.content  # bytes
    assert b"aria2.addUri" in body

    # All calls
    for call in route.calls:
        print(call.request.url, call.response.status_code)
```

### Multiple Routes

```python
with respx.mock:
    # Route for version check
    respx.post("http://localhost:6800/jsonrpc").respond(
        json={"jsonrpc": "2.0", "result": {"version": "1.37.0"}, "id": 1}
    )

    # Route for add URI
    respx.post("http://localhost:6800/jsonrpc").respond(
        json={"jsonrpc": "2.0", "result": "abc123", "id": 2}
    )

    # Both are matched in order
```

### Async Mock with Custom Handler

```python
async def request_handler(request):
    """Inspect request and return dynamic response."""
    body = json.loads(request.content)
    method = body.get("method", "")

    if method == "aria2.getVersion":
        return Response(200, json={"result": {"version": "1.37.0"}})
    elif method == "aria2.addUri":
        return Response(200, json={"result": "new-gid"})
    else:
        return Response(400, json={"error": {"code": -32601}})

with respx.mock:
    respx.post("http://localhost:6800/jsonrpc").mock(side_effect=request_handler)
```

### Per-Test Fixture Pattern

```python
import respx
import pytest

@pytest.fixture
def mock_rpc():
    """Fixture that mocks aria2 JSON-RPC endpoints."""
    with respx.mock:
        yield respx

async def test_add_uri(mock_rpc):
    mock_rpc.post("http://localhost:6800/jsonrpc").respond(
        json={"result": "abc123", "id": 1}
    )
    transport = HttpTransport("localhost", 6800)
    await transport.connect()
    result = await transport.send_request("aria2.addUri", [["https://x"]])
    assert result == "abc123"

async def test_rpc_error(mock_rpc):
    mock_rpc.post("http://localhost:6800/jsonrpc").respond(
        json={"error": {"code": -32601, "message": "Method not found"}, "id": 1}
    )
    transport = HttpTransport("localhost", 6800)
    await transport.connect()
    with pytest.raises(Aria2RpcError):
        await transport.send_request("aria2.unknownMethod", [])
```

### Using in `conftest.py`

```python
# tests/conftest.py
import respx
import pytest

@pytest.fixture
def mock_rpc():
    """Shared mock fixture available to all tests."""
    with respx.mock(assert_all_called=False) as respx_mock:
        yield respx_mock
```

### Assert All Mocked Routes Were Called

```python
with respx.mock(assert_all_called=True) as mock:
    mock.post("http://localhost:6800/jsonrpc").respond(json={"result": "ok"})
    # Fails if the route was never hit
```

### Using with pytest-asyncio

```python
@pytest.mark.asyncio
async def test_with_respx():
    async with respx.mock:
        respx.post("http://localhost:6800/jsonrpc").respond(json={"result": "ok"})
        assert await make_rpc_call() == "ok"
```

Or use pytest-asyncio's `asyncio_mode = "auto"` (already configured in this project).

### Partial Mocking

respx can mock specific URLs while letting others pass through:

```python
with respx.mock:
    # Only mock this specific URL
    respx.post("http://localhost:6800/jsonrpc").respond(json={"result": "ok"})
    # All other httpx requests will... either fail or pass through
```

To pass through unmocked requests:

```python
with respx.mock(using="passthrough"):
    # Or use BaseURL for prefix matching
    respx.mock(base_url="http://localhost:6800").using("passthrough")
```

### Current Project Usage

```python
"""Tests for HTTP transport using respx mock router."""
import respx

HTTP_URL = "http://localhost:6800/jsonrpc"

def test_send_request_success():
    with respx.mock:
        route = respx.post(HTTP_URL).respond(
            json={"jsonrpc": "2.0", "result": "ok", "id": 1}
        )
        result = asyncio.run(make_request())
        assert result == "ok"
        assert route.called
```

## Best Practices

### 1. Use context manager
`s with respx.mock: ` ensures cleanup even on test failure.

### 2. Verify calls
Assert `route.called` or `route.call_count` to ensure the mock was hit.

### 3. Test error paths
Mock timeouts, connection errors, and HTTP 500s — don't just test the happy path.

### 4. Use `side_effect` for dynamic responses
When the same endpoint returns different results, use a handler function.

### 5. Keep mocks close to tests
Define mock routes inside each test or in a focused fixture — not in a global conftest.

### 6. Validate request content
Check that your code sends the correct JSON-RPC body, headers, and URL.

## Common Pitfalls

- **Mock not active**: Forgetting `with respx.mock:` — requests pass through to real network.
- **Route not matched**: URL mismatch (trailing slash, port, scheme). Use `url__regex` for flexible matching.
- **Async context**: Use `async with respx.mock` inside `async def` tests, or `with respx.mock` inside sync tests calling async.
- **Side effect vs respond**: `respond()` sets the response; `side_effect` is for exceptions or handler functions.
- **Shared mock state**: Don't share `respx.mock` across tests. Each test gets its own `with` block.

## Commands

```bash
uv run pytest -k "http"            # Run HTTP transport tests
uv run pytest --co                 # Show config
```

## Resources

- Documentation: <https://lundberg.github.io/respx/>
- GitHub: <https://github.com/lundberg/respx>
- PyPI: <https://pypi.org/project/respx/>
