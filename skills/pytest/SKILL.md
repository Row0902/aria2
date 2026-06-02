---
name: pytest
description: "Trigger: pytest, test, testing, fixtures, conftest, parametrize, coverage, pytest-cov, test configuration. Python testing framework — fixtures, parametrization, markers, and coverage."
license: Apache-2.0
metadata:
  author: gentleman-programming
  version: "1.0"
---

## When to Use

- Writing and organizing tests for Python code
- Configuring pytest in `pyproject.toml` or `pytest.ini`
- Using fixtures for test setup/teardown and resource management
- Parametrizing tests to cover multiple inputs
- Running tests with coverage reporting
- Marking tests for selective execution (slow, integration, etc.)
- Generating test reports for CI

## Critical Patterns

### Configuration

All pytest config in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
markers = [
    "slow: marks tests as slow (deselect with '-m \"not slow\"')",
    "integration: requires a running aria2 daemon",
    "network: makes external network calls",
]
filterwarnings = ["error"]
log_cli = true
log_cli_level = "INFO"

[tool.coverage.run]
source = ["src"]
omit = ["src/aria2/bin/*"]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "raise NotImplementedError",
    "if TYPE_CHECKING:",
]
```

> **Config actual del proyecto**: `pyproject.toml` actual tiene `asyncio_mode = "auto"` y `testpaths = ["tests"]`. Los markers, filterwarnings, log_cli y coverage son recomendados pero aún no están en el archivo. Agregalos cuando los necesites.

### Fixtures: The Backbone of Test Setup

```python
import pytest

# Simple fixture
@pytest.fixture
def api_client():
    """Create a client for testing."""
    client = Aria2Client(secret="test")
    yield client
    # cleanup after test

# Async fixture
@pytest_asyncio.fixture
async def connected_client(api_client):
    """Client with established connection."""
    await api_client.connect()
    yield api_client
    await api_client.close()

# Fixture with params
@pytest.fixture(params=[True, False])
def ws_enabled(request):
    return request.param

# Autouse fixture (runs for every test)
@pytest.fixture(autouse=True)
def mock_env(monkeypatch):
    monkeypatch.setenv("ARIA2C_PATH", "/dev/null")
```

### Fixture Scopes

| Scope | Livespan | Best for |
|---|---|---|
| `function` (default) | One test function | Per-test state isolation |
| `class` | One test class | Shared class-level resources |
| `module` | One test module | Expensive setup (DB, server) |
| `package` | One package | Package-level resources |
| `session` | Entire test run | Very expensive (global config) |

```python
@pytest.fixture(scope="session")
def event_loop_policy():
    """Reuse event loop policy across all tests."""
    import uvloop
    return uvloop.EventLoopPolicy()

@pytest.fixture(scope="module")
def schema():
    """Load JSON-RPC schema once per module."""
    return json.loads(SCHEMA_JSON)
```

### Parametrize

```python
import pytest

@pytest.mark.parametrize("uri,expected", [
    ("https://example.com/file.iso", True),
    ("magnet:?xt=urn:btih:abc", True),
    ("invalid", False),
])
async def test_add_uri(uri, expected, client):
    result = await client.add_uri([uri])
    assert isinstance(result, str) == expected

# Parametrize with multiple arguments
@pytest.mark.parametrize("method,params,expected", [
    ("aria2.addUri", [["http://x"]], "ok"),
    ("aria2.remove", ["abc123"], "ok"),
])
async def test_rpc_methods(method, params, expected, mock_transport):
    ...
```

### Fixture Composition

Fixtures can depend on other fixtures — pytest resolves the DAG:

```python
@pytest.fixture
def config():
    return {"host": "localhost", "port": 6800}

@pytest.fixture
def http_transport(config):
    return HttpTransport(config["host"], config["port"])

@pytest_asyncio.fixture
async def connected_http(http_transport):
    await http_transport.connect()
    yield http_transport
    await http_transport.close()

async def test_request(connected_http):  # <- composes all three
    result = await connected_http.send_request("aria2.getVersion", [])
    assert result is not None
```

### Fixture Teardown

Fixtures clean up via `yield` or `return` + `addfinalizer`:

```python
@pytest_asyncio.fixture
async def server(unused_tcp_port):
    proc = await start_server(port=unused_tcp_port)
    yield proc
    proc.terminate()     # ← runs after test, even if test fails

# Or with addfinalizer
@pytest.fixture
def temp_dir(tmp_path):
    d = tmp_path / "data"
    d.mkdir()
    yield d
    # cleanup happens here
```

### Mocking

```python
from unittest.mock import AsyncMock, MagicMock, patch

@pytest.fixture
def mock_transport():
    transport = MagicMock()
    transport.is_connected = True
    transport.send_request = AsyncMock(return_value="ok")
    return transport

async def test_client_with_mock(mock_transport):
    client = Aria2Client(secret="test")
    client._http = mock_transport
    result = await client.add_uri(["http://x"])
    assert result == "ok"
```

### Built-in Fixtures

| Fixture | Description |
|---|---|
| `tmp_path` | Temporary directory (`Path`) unique per test |
| `tmpdir` | Temporary directory (legacy `py.path.local`) |
| `capsys` | Capture stdout/stderr |
| `monkeypatch` | Temporarily modify objects/environment |
| `pytestconfig` | Access to pytest configuration |
| `recwarn` | Record warnings |
| `request` | Access test context (markers, params, fixture info) |
| `unused_tcp_port` | Free TCP port (from pytest-asyncio) |

### Markers

```python
@pytest.mark.slow
async def test_full_integration():
    ...

@pytest.mark.skip(reason="Requires aria2 daemon")
async def test_live_server():
    ...

@pytest.mark.skipif(sys.platform == "win32", reason="Not supported on Windows")
async def test_posix_only():
    ...

@pytest.mark.xfail(strict=True, raises=Aria2RpcError)
async def test_known_bug():
    ...
```

Run with markers:

```bash
uv run pytest -m "not slow"          # Skip slow tests
uv run pytest -m "integration"        # Only integration tests
uv run pytest -m "slow or integration"
```

### Coverage

```toml
[tool.coverage.run]
source = ["src"]
omit = ["src/aria2/bin/*"]

[tool.coverage.report]
exclude_lines = ["pragma: no cover", "def __repr__", "raise NotImplementedError"]
```

```bash
uv run pytest --cov=src/aria2 --cov-report=term-missing
uv run pytest --cov=src/aria2 --cov-report=xml:coverage.xml  # For CI
uv run pytest --cov=src/aria2 --cov-report=html:coverage_html  # HTML report
```

### Test Organization

```
tests/
├── conftest.py              # Shared fixtures (scope: session/module)
├── test_rpc.py              # Test RPC builder/parser
├── test_http.py             # Test HTTP transport
├── test_ws.py               # Test WebSocket transport
├── test_client.py           # Test Aria2Client integration
└── test_errors.py           # Test error hierarchy
```

- `conftest.py` at root makes fixtures available to all tests.
- Name files `test_*.py` (pytest discovery).
- One test file per module or concern.

### Running Tests

```bash
uv run pytest                               # All tests
uv run pytest -v                            # Verbose
uv run pytest -x                            # Stop on first failure
uv run pytest --tb=short                    # Shorter tracebacks
uv run pytest -k "client"                   # Run tests matching "client"
uv run pytest -k "not slow"                 # Exclude slow tests
uv run pytest --lf                          # Run last failures only
uv run pytest --ff                          # Run failures first
uv run pytest --co                          # Show config
uv run pytest --fixtures                    # List all fixtures
uv run pytest --markers                     # List all markers
uv run pytest -p no:asyncio                 # Disable a plugin
```

### Common Pitfalls

- **Async test not detected**: If `asyncio_mode = "auto"` is missing, `async def test_*` fails. Add to `pyproject.toml`.
- **Fixture scope too broad**: `session`-scoped fixtures can leak state between tests. Use `function` unless you need broader.
- **Mutable fixture state**: Fixtures returning mutable objects (lists, dicts) are shared within their scope. Use `yield` + cleanup or return a factory function.
- **`monkeypatch.setattr` for async functions**: Use `AsyncMock` for async mocks, not regular `MagicMock`.
- **`tmp_path` vs `tmpdir`**: Prefer `tmp_path` (Path API) over `tmpdir` (legacy py.path).

## Commands

```bash
uv run pytest -v                          # Verbose run
uv run pytest -x --tb=short               # Debug mode
uv run pytest -k "client" --collect-only  # List matching tests
uv run pytest --co                        # Show config
uv run pytest --fixtures                  # Show fixtures
uv run pytest --cov=src/aria2             # With coverage
uv run pytest --cov-report=html           # HTML coverage report
```

## Resources

- Documentation: <https://docs.pytest.org/>
- Fixtures: <https://docs.pytest.org/en/stable/fixture.html>
- Parametrize: <https://docs.pytest.org/en/stable/parametrize.html>
- Coverage: <https://coverage.readthedocs.io/>
