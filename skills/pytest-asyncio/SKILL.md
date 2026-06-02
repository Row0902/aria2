---
name: pytest-asyncio
description: "Trigger: pytest-asyncio, async tests, asyncio, event loop, asynchronous tests, pytest async. Library for testing asyncio code with pytest — async fixtures, async test functions, event loop management."
license: Apache-2.0
metadata:
  author: gentleman-programming
  version: "1.0"
---

## When to Use

- Writing async test functions (`async def test_*`)
- Creating async fixtures (`async def` fixtures with `@pytest_asyncio.fixture`)
- Testing asyncio-based code (clients, servers, transports, streams)
- Managing event loop scope and lifecycle in tests
- Using async context managers and async generators in tests
- Controlling fixture loop scope for performance optimization

## Critical Patterns

### Installation

```bash
uv add --dev pytest-asyncio
```

pytest-asyncio >= 0.21 requires Python >= 3.7. This project uses pytest-asyncio 1.4.0 with Python 3.14.

### Basic Setup

Configure in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

Or in `pytest.ini`:

```ini
[pytest]
asyncio_mode = auto
testpaths = tests
```

### `asyncio_mode` Modes

| Mode | Behavior |
|---|---|
| `auto` | All `async def test_*` functions are automatically treated as asyncio tests — no `@pytest.mark.asyncio` needed |
| `strict` | Only tests with `@pytest.mark.asyncio` are run with asyncio (useful when mixing async frameworks) |

In `auto` mode:

```python
# No marker needed — auto-detected
async def test_fetch_data():
    result = await my_async_function()
    assert result == expected

# Sync tests still work as normal
def test_sync_thing():
    assert 1 + 1 == 2
```

In `strict` mode:

```python
import pytest

@pytest.mark.asyncio
async def test_fetch_data():
    result = await my_async_function()
    assert result == expected
```

### Async Fixtures

```python
import pytest_asyncio

@pytest_asyncio.fixture
async def db_connection():
    conn = await create_connection()
    yield conn
    await conn.close()

async def test_query(db_connection):          # ← async fixture injected
    result = await db_connection.query("...")
    assert result is not None
```

### Fixture Loop Scope

Control which event loop an async fixture uses. The fixture can declare its own loop scope, independent of the test loop scope:

```python
@pytest_asyncio.fixture(loop_scope="session")
async def database():
    """Event loop lives for the entire session."""
    async with async_database() as db:
        yield db

@pytest_asyncio.fixture(loop_scope="module")
async def api_client():
    """Event loop lives for one module."""
    client = ApiClient()
    await client.start()
    yield client
    await client.stop()

@pytest_asyncio.fixture(loop_scope="class")
async def shared_state():
    """Event loop lives for one test class."""
    state = State()
    yield state

@pytest_asyncio.fixture(loop_scope="function")
async def temp_file():
    """New event loop for each test (default)."""
    f = await create_temp_file()
    try:
        yield f
    finally:
        await f.delete()
```

**Performance tip**: Use `loop_scope="module"` or `"session"` for fixtures that set up heavy resources (databases, HTTP servers, etc.) to avoid re-creating the event loop for every test.

### Default Loop Scope Configuration

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "function"   # default for all fixtures
asyncio_default_test_loop_scope = "function"       # default for all tests
```

Available scopes: `function`, `class`, `module`, `package`, `session`

### Built-in Fixtures

| Fixture | Scope | Description |
|---|---|---|
| `event_loop_policy` | session | Return the asyncio event loop policy |
| `unused_tcp_port` | function | Return an unused TCP port number |
| `unused_udp_port` | function | Return an unused UDP port number |
| `unused_tcp_port_factory` | session | Factory function returning unique unused TCP ports |
| `unused_udp_port_factory` | session | Factory function returning unique unused UDP ports |

```python
async def test_server(unused_tcp_port_factory):
    port1 = unused_tcp_port_factory()
    port2 = unused_tcp_port_factory()
    assert port1 != port2
```

### Full Example: WebSocket Transport Test

From this project's test suite (simplified):

```python
import pytest
import pytest_asyncio

@pytest_asyncio.fixture
async def ws_server(unused_tcp_port_factory):
    """Start a WebSocket server that mimics aria2 JSON-RPC."""
    import websockets
    port = unused_tcp_port_factory()
    # ... start server
    yield {"port": port}
    # ... cleanup

@pytest.mark.asyncio                     # ← Not needed in auto mode!
async def test_connect_and_request(ws_server):
    transport = WebSocketTransport(
        host="localhost",
        port=ws_server["port"],
    )
    await transport.connect()
    assert transport.is_connected
    await transport.close()
```

### Event Loop Configuration

```toml
[tool.pytest.ini_options]
asyncio_debug = true                      # Enable asyncio debug mode
asyncio_default_fixture_loop_scope = "function"
```

```bash
# CLI equivalent
pytest --asyncio-mode=auto --asyncio-debug
```

### The `event_loop_policy` Fixture

Override the event loop policy for all tests:

```python
import asyncio
import pytest_asyncio

@pytest_asyncio.fixture(scope="session")
def event_loop_policy():
    """Use uvloop for all tests."""
    import uvloop
    return uvloop.EventLoopPolicy()
```

### pytest.mark.asyncio Options

```python
@pytest.mark.asyncio(loop_scope="module")   # Override loop scope for this test
async def test_something():
    ...
```

### Async Generator Fixtures

```python
@pytest_asyncio.fixture
async def stream():
    """Use async generator for setup/teardown."""
    s = await open_stream()
    try:
        yield s
    finally:
        await s.close()
```

### Common Pitfalls

- **`@pytest.mark.asyncio` required in strict mode**: Forgetting it causes `RuntimeError: no running event loop`. In `auto` mode, this is handled automatically.
- **Fixture loop scope vs test loop scope**: Fixtures can have a different loop scope than tests. A `session`-scoped fixture uses one event loop; each test in that fixture's scope uses its own.
- **`event_loop_policy` must be `session`-scoped**: The event loop policy is set once per session.
- **`unused_tcp_port` doesn't reserve the port**: It returns a port number that was unused at the time of the call. Another process could grab it between the call and usage.
- **`@pytest.mark.asyncio` on class methods**: When using `auto` mode, class-based tests need the marker on the method. Auto mode only applies to module-level functions.
- **pytest-asyncio >= 0.23 changed fixture loop scope defaults**: Always be explicit about `loop_scope` if you depend on specific behavior.

## Code Examples

### Minimal config
```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

### Async test with mock
```python
import pytest
from unittest.mock import AsyncMock

async def test_client_request():
    mock_transport = AsyncMock()
    mock_transport.send_request.return_value = {"result": "ok"}

    client = Aria2Client()
    client._http = mock_transport

    result = await client.add_uri(["https://example.com/file"])
    assert result == "ok"
```

### Full project test setup
```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "function"
asyncio_debug = false
testpaths = ["tests"]
markers = [
    "slow: marks tests as slow (deselect with '-m \"not slow\"')",
]
```

### Test with server fixture
```python
import pytest_asyncio

@pytest_asyncio.fixture(scope="module")
async def http_server(unused_tcp_port_factory):
    """Start a mock JSON-RPC server once per module."""
    from respx import MockRouter

    port = unused_tcp_port_factory()
    async with MockRouter() as respx_mock:
        respx_mock.post(f"http://localhost:{port}/jsonrpc").respond(
            json={"jsonrpc": "2.0", "result": "ok", "id": 1}
        )
        yield port

async def test_http_request(http_server):
    transport = HttpTransport("localhost", http_server)
    await transport.connect()
    result = await transport.send_request("aria2.addUri", [["https://x"]])
    assert result == "ok"
```

### CI configuration
```yaml
steps:
  - uses: actions/checkout@v4
  - uses: astral-sh/setup-uv@v5
  - run: uv sync --locked
  - run: uv run pytest -v -q --asyncio-mode=auto
```

## Commands

```bash
# ── Run tests ─────────────────────────────────────────
uv run pytest                          # Default (reads pyproject.toml config)
uv run pytest -v                       # Verbose
uv run pytest -x                       # Stop on first failure
uv run pytest -k "test_name"           # Run matching tests
uv run pytest -m "not slow"            # Filter by marker

# ── Asyncio-specific ──────────────────────────────────
uv run pytest --asyncio-mode=auto      # Auto-detect async tests
uv run pytest --asyncio-mode=strict    # Require @pytest.mark.asyncio
uv run pytest --asyncio-debug          # Enable asyncio debug logging
uv run pytest -p no:asyncio            # Disable asyncio plugin

# ── Configuration ─────────────────────────────────────
uv run pytest --co                     # List config options
uv run pytest --fixtures               # List available fixtures
uv run pytest --markers                # List registered markers
uv run pytest --help                   # See all options
```

## Resources

- Documentation: <https://pytest-asyncio.readthedocs.io/>
- GitHub: <https://github.com/pytest-dev/pytest-asyncio>
- PyPI: <https://pypi.org/project/pytest-asyncio/>
- pytest docs: <https://docs.pytest.org/>
