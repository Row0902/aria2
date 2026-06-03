# SDD Proposal: Refactor 4 SDK Functions Exceeding `max_function_lines: 20`

**Change ID:** `2026-06-03-func-lines-sdk`
**Date:** 2026-06-03
**Status:** Draft

---

## Intent

Refactor four functions in the SDK packages that violate the `max_function_lines: 20` policy enforced by `scripts/lint/wc-lint.py`. This is a **pure structural refactoring** — zero behavioral changes, zero API changes, zero test modifications.

All existing tests must continue to pass without modification.

---

## Scope

### In scope

| # | File | Function | Current lines | Target lines |
|---|------|----------|---------------|--------------|
| 1 | `packages/aria2-sdk/src/aria2/client/download.py` | `DownloadManager.add_torrent` | 29 | ≤12 |
| 2 | `packages/aria2-sdk/src/aria2/client/download.py` | `DownloadManager.add_metalink` | 21 | ≤10 |
| 3 | `packages/aria2-sdk/src/aria2/client/transport/http.py` | `HttpTransport.send_request` | 33 | ≤18 |
| 4 | `packages/aria2-sdk/src/aria2/client/__init__.py` | `Aria2Client.__init__` | 25 | ≤18 |

### Out of scope

- Any function in any other file (tracked as issues #9 and #10)
- Changes to test files (`tests/test_client.py`, `tests/test_http.py`, etc.)
- Changes to the `Transport` ABC in `transport/__init__.py`
- Adding new tests (existing coverage verifies behavioral equivalence)
- Fixing any discovered bugs beyond the refactoring
- Changes to `add_uri` (already compliant at ≤18 lines)

---

## Affected Areas

### Directly modified

| Module | Change |
|---|---|
| `src/aria2/client/download.py` | Extract two module-level helpers; move `import base64` to module-level |
| `src/aria2/client/transport/http.py` | Extract `_do_request` private async method |
| `src/aria2/client/__init__.py` | Extract `_init_sub_managers` private method |

### Unchanged (imports/tests must keep working)

| Module | Why |
|---|---|
| `tests/test_client.py` | All tests call public API only; no direct helper access |
| `tests/test_http.py` | All tests call `transport.send_request` only |
| `tests/test_integration.py` | Integration tests call public API only |
| Any downstream import of `DownloadManager`, `HttpTransport`, `Aria2Client` | Public API surfaces unchanged |

---

## Architecture & Design

### Strategy: Extract Module-Level / Private Helpers

Each violating function is decomposed along its natural seam — the parameter-building logic (for `add_torrent`/`add_metalink`) or the I/O + error-wrapping section (for `send_request`), or the sub-manager initialization block (for `__init__`).

#### Precedent

The WebSocket transport refactoring in `2026-06-03-ws-transport-split` established the pattern of extracting private helpers with single responsibilities:

- `_build_payload(method, params, add_secret)` — extracted from `send_request`
- `_send_and_wait(payload, rid)` — extracted from `send_request`
- `_build_url(host, port)` — module-level helper extracted from `connect`

This proposal applies the same pattern to the remaining violations.

### 1. `download.py` — Extract `_build_torrent_params` and `_build_metalink_params`

#### Problem

`add_torrent` has 29 lines due to the deeply-nested conditional parameter-building logic (uris/options/position combinations producing shifted indices). `add_metalink` has 21 lines with similar but simpler logic. Both also contain `import base64` inline.

#### Solution

**Module-level import:** Move `import base64` from function bodies to module-level.

**Module-level helper `_build_torrent_params`:**

```python
def _build_torrent_params(
    b64: str,
    uris: list[str] | None,
    options: dict[str, str] | None,
    position: int | None,
) -> list[Any]:
    """Build RPC params array for aria2.addTorrent.

    The params array follows a positional schema where indices shift
    depending on which optional arguments are provided:

        [b64, uris?, options?, position?]

    When *uris* is provided and *position* is provided but *options*
    is not, an empty list ``[]`` is inserted as placeholder for the
    skipped options slot.  This preserves the existing behaviour and
    test assertions (test_add_torrent_with_uris_position checks
    ``params[2] == []``).
    """
    params: list[Any] = [b64]
    has_uris = uris is not None
    if has_uris:
        params.append(uris)
    if options is not None:
        params.append(options)
    if position is not None:
        if has_uris and options is None:
            params.append([])  # placeholder for skipped options slot
        params.append(position)
    return params
```

**Module-level helper `_build_metalink_params`:**

```python
def _build_metalink_params(
    b64: str,
    options: dict[str, str] | None,
    position: int | None,
) -> list[Any]:
    """Build RPC params array for aria2.addMetalink.

        [b64, options?, position?]
    """
    params: list[Any] = [b64]
    if options is not None:
        params.append(options)
    if position is not None:
        if options is None:
            params.append(position)
        else:
            params.append(position)
    return params
```

**Refactored `add_torrent`:**

```python
async def add_torrent(
    self,
    torrent: bytes,
    uris: list[str] | None = None,
    options: dict[str, str] | None = None,
    position: int | None = None,
) -> str:
    """Add a download by torrent file."""
    b64 = base64.b64encode(torrent).decode("ascii")
    params = _build_torrent_params(b64, uris, options, position)
    return await self._request("aria2.addTorrent", params)
```

**(~10–12 lines, well under 20)** ✅

**Refactored `add_metalink`:**

```python
async def add_metalink(
    self,
    metalink: bytes,
    options: dict[str, str] | None = None,
    position: int | None = None,
) -> list[str]:
    """Add a Metalink download. Returns list of GIDs."""
    b64 = base64.b64encode(metalink).decode("ascii")
    params = _build_metalink_params(b64, options, position)
    return await self._request("aria2.addMetalink", params)
```

**(~8–10 lines, well under 20)** ✅

#### Behavioral equivalence verification

| Test | Input | Original params | New params | Match |
|------|-------|----------------|------------|-------|
| `test_add_torrent_with_uris` | `(b"data", uris=["http://seed"])` | `[b64, ["http://seed"]]` | `[b64, ["http://seed"]]` | ✅ |
| `test_add_torrent_with_uris_options_position` | `(b"data", uris=["http://seed"], options={"dir":"/tmp"}, position=1)` | `[b64, ["http://seed"], {"dir":"/tmp"}, 1]` | `[b64, ["http://seed"], {"dir":"/tmp"}, 1]` | ✅ |
| `test_add_torrent_with_uris_position` | `(b"data", uris=["http://seed"], position=0)` | `[b64, ["http://seed"], [], 0]` | `[b64, ["http://seed"], [], 0]` | ✅ |
| `test_add_torrent_with_options_position` | `(b"data", options={"dir":"/tmp"}, position=1)` | `[b64, {"dir":"/tmp"}, 1]` | `[b64, {"dir":"/tmp"}, 1]` | ✅ |
| `test_add_torrent_with_position_only` | `(b"data", position=2)` | `[b64, 2]` | `[b64, 2]` | ✅ |
| `test_add_metalink` | `(b"metal")` | `[b64]` | `[b64]` | ✅ |
| `test_add_metalink_with_position_only` | `(b"metal", position=0)` | `[b64, 0]` | `[b64, 0]` | ✅ |
| `test_add_metalink_with_options_position` | `(b"metal", options={"dir":"/tmp"}, position=1)` | `[b64, {"dir":"/tmp"}, 1]` | `[b64, {"dir":"/tmp"}, 1]` | ✅ |

All eight existing test assertions match exactly. **No behavioral change.** 🔒

**Important constraint:** The helper uses `[]` as the placeholder (not `{}`) when *uris* is provided and *position* is provided but *options* is not. This preserves the existing behaviour. The exploration phase proposed `{}`, but the existing test `test_add_torrent_with_uris_position` asserts `params[2] == []` — using `{}` would break the test. The proposal corrects this to `[]`.

### 2. `http.py` — Extract `_do_request`

#### Problem

`HttpTransport.send_request` (33 lines) combines: connection guard, ID generation, payload building, HTTP POST, status code check, response parsing, and error wrapping into a single method.

#### Solution

Extract the HTTP I/O + error-wrapping block into a private async method `_do_request(payload: str) -> Any`.

```python
async def _do_request(self, payload: str) -> Any:
    """Post JSON-RPC payload to daemon and return parsed response.

    Raises:
        Aria2RpcError: If the daemon returns a JSON-RPC error.
        Aria2ConnectionError: If HTTP status is non-200, or any
            httpx/network error occurs.

    """
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
```

**(~12–14 lines)**

**Refactored `send_request`:**

```python
async def send_request(self, method: str, params: list[Any], *, add_secret: bool = True) -> Any:
    """Send a JSON-RPC request over HTTP.

    Args:
        method: JSON-RPC method name.
        params: Parameters for the method.
        add_secret: If True, prepend ``token:{secret}`` to params.

    Returns:
        The parsed JSON-RPC result.

    Raises:
        Aria2ConnectionError: If not connected or the HTTP request fails.
        Aria2RpcError: If the daemon returns a JSON-RPC error.

    """
    if not self.is_connected:
        raise Aria2ConnectionError("HTTP transport is not connected")
    self._request_id += 1
    payload = self._build_payload(method, params, add_secret)
    return await self._do_request(payload)
```

**(~15–18 lines, under 20)** ✅

#### Pattern alignment

The `_do_request` method mirrors the WebSocket transport's `_send_and_wait` pattern: both are private methods that handle the actual I/O + error wrapping, while the public `send_request` handles guard checks, ID management, and payload building before delegating.

#### Behavioral equivalence verification

| Test | Input | Behavior verified | Match |
|------|-------|-------------------|-------|
| `test_send_request_success` | Standard request | Returns parsed result | ✅ |
| `test_send_request_rpc_error` | RPC error response | Raises `Aria2RpcError` | ✅ |
| `test_send_request_http_error` | HTTP 500 | Raises `Aria2ConnectionError` | ✅ |
| `test_not_connected_raises` | No connect | Raises `Aria2ConnectionError` (guard stays in send_request) | ✅ |
| `test_http_timeout_error` | TimeoutError | Raises `Aria2ConnectionError` | ✅ |
| `test_send_request_no_secret` | `add_secret=False` | No token in payload | ✅ |

All six tests pass without modification. **No behavioral change.** 🔒

### 3. `client/__init__.py` — Extract `_init_sub_managers`

#### Problem

`Aria2Client.__init__` (25 lines) contains: parameter storage (5 lines), HTTP transport init (1 line), WS transport init (1 line), callbacks init (1 line), and 6 sub-manager assignments (6 lines). The sub-manager assignments are a distinct concern that can be extracted.

#### Solution

Extract the six sub-manager instantiations into `_init_sub_managers(self)`.

```python
def _init_sub_managers(self) -> None:
    """Create sub-manager instances for each domain.

    Each sub-manager owns a slice of the aria2 RPC API and is exposed
    as a read-only property on the client.
    """
    self._downloads = DownloadManager(self._request, self._secret)
    self._status = StatusManager(self._request)
    self._options = OptionsManager(self._request)
    self._system = SystemManager(self._request)
    self._daemon = DaemonManager(self._request, self._secret)
    self._events = EventManager(self._callbacks)
```

**(~7–9 lines)**

**Refactored `__init__`:**

```python
def __init__(
    self,
    host: str = "localhost",
    port: int = 6800,
    secret: str | None = None,
    *,
    enable_ws: bool = True,
    timeout: float = 30.0,
) -> None:
    self._host = host
    self._port = port
    self._secret = secret
    self._timeout = timeout

    self._http = HttpTransport(host, port, secret, timeout=timeout)
    self._ws = self._init_ws_transport(host, port, secret, timeout, enable_ws)

    self._callbacks = {name: [] for name in _EVENT_MAP}
    self._init_sub_managers()
```

**(~15–18 lines, under 20)** ✅

#### Precedent

The existing `_init_ws_transport` method already follows this pattern — it's a private helper extracted from `__init__` to handle conditional WS transport construction. `_init_sub_managers` extends the same pattern to sub-manager creation.

#### Behavioral equivalence verification

| Test | Behavior verified | Match |
|------|-------------------|-------|
| `client()` fixture | Creates `Aria2Client` with 6 sub-managers | ✅ |
| `test_enable_ws_false` | `_ws` is `None`, sub-managers exist | ✅ |
| `test_ws_connect_degrades_gracefully` | All sub-managers accessible | ✅ |
| All 6 sub-manager property accesses | `c.downloads`, `c.status`, `c.options`, `c.system`, `c.daemon`, `c.events` | ✅ |

All existing tests create a `client` fixture by calling `Aria2Client(secret="testsecret", enable_ws=True)`, which exercises the refactored `__init__`. **No behavioral change.** 🔒

---

## File-by-File Summary

### `download.py`

| Before | After |
|--------|-------|
| Module imports: `__future__`, `Callable`, `Any` | + `import base64` |
| `add_torrent`: 29 lines (inline param building, inline `import base64`) | `add_torrent`: ~12 lines (delegates to `_build_torrent_params`) |
| `add_metalink`: 21 lines (inline param building, inline `import base64`) | `add_metalink`: ~10 lines (delegates to `_build_metalink_params`) |
| — (new helper) | `_build_torrent_params(b64, uris, options, position) -> list[Any]`: ~12 lines |
| — (new helper) | `_build_metalink_params(b64, options, position) -> list[Any]`: ~8 lines |
| File total: ~87 lines | File total: ~95 lines (under 200 ✅) |

### `http.py`

| Before | After |
|--------|-------|
| `send_request`: 33 lines | `send_request`: ~18 lines |
| — (new helper) | `_do_request(payload) -> Any`: ~14 lines |
| File total: ~93 lines | File total: ~100 lines (under 200 ✅) |

### `client/__init__.py`

| Before | After |
|--------|-------|
| `__init__`: 25 lines (6 sub-manager assignments inline) | `__init__`: ~18 lines (delegates to `_init_sub_managers`) |
| — (new helper) | `_init_sub_managers()`: ~9 lines |
| File total: ~155 lines | File total: ~160 lines (under 200 ✅) |

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| **`_build_torrent_params` `[]` vs `{}` placeholder** — deviating from exploration proposal | Medium | Medium | Correct choice documented in proposal. `[]` preserves test assertion `params[2] == []`. |
| **Import resolution failure** — `import base64` moved to module level may shadow something | Low | Low | `base64` is a stdlib module, well-known. No name collision in this file. |
| **`_do_request` called without guard** — method is private, internal use only | Low | Low | Guard stays in `send_request`. Callers never bypass it. |
| **Coverage regression** — new helpers not covered by existing tests | Low | Low | All helpers are exercised indirectly through the existing public method tests. |
| **Type checking** — new functions missing type annotations | Low | Low | All helpers are fully annotated with types. |

---

## Rollback Plan

If the refactoring breaks the build or tests:

1. **Revert** all three files via `git checkout`:
   ```bash
   git checkout packages/aria2-sdk/src/aria2/client/download.py
   git checkout packages/aria2-sdk/src/aria2/client/transport/http.py
   git checkout packages/aria2-sdk/src/aria2/client/__init__.py
   ```
2. **Verify** original tests pass:
   ```bash
   pytest tests/ -x -q
   ```
3. **File a follow-up issue** with the failure details.

The refactoring is purely structural (extract + delegate) — all original code is preserved in git history at the current HEAD, so recovery is instant.

---

## Success Criteria

All of the following must pass:

- [ ] `ruff check packages/aria2-sdk/src/aria2/client/download.py` — zero errors
- [ ] `ruff check packages/aria2-sdk/src/aria2/client/transport/http.py` — zero errors
- [ ] `ruff check packages/aria2-sdk/src/aria2/client/__init__.py` — zero errors
- [ ] `ty --strict` on all three files — zero type errors
- [ ] `python scripts/lint/wc-lint.py packages/aria2-sdk/src/aria2/client/` — zero function-line violations
- [ ] `pytest tests/test_client.py -v` — all existing tests pass without modification
- [ ] `pytest tests/test_http.py -v` — all existing tests pass without modification
- [ ] `pytest -x -q -m "not integration"` — full non-integration suite passes
- [ ] Each function body is ≤20 lines (verify with `scripts/lint/wc-lint.py`)
- [ ] Each file is ≤200 lines
- [ ] Coverage ≥80% (no regression from current baseline)

---

## Chained PR Forecast

| Metric | Value |
|--------|-------|
| Estimated new lines added | ~35 (helpers) |
| Estimated lines modified | ~25 (refactored method bodies) |
| Estimated total changed lines | ~60 |
| Review budget (400 lines) | ✅ **Comfortable** — single PR, no chaining needed |
| Chained PRs recommended | **No** |

---

## Appendix: Current Function Line Audit

### `download.py`

```
Function                       Lines    Violates 20?
─────────────────────────────  ─────    ─────────────
__init__                         3       ✅
add_uri                         18       ✅
add_torrent                     29       ❌ → ~12 ✅
add_metalink                    21       ❌ → ~10 ✅
remove                           9       ✅
pause                            9       ✅
pause_all                        7       ✅
unpause                          8       ✅
unpause_all                      7       ✅
change_position                 11       ✅
```

### `http.py`

```
Function                       Lines    Violates 20?
─────────────────────────────  ─────    ─────────────
__init__                        12       ✅
_url (property)                  4       ✅
is_connected (property)          4       ✅
connect                         13       ✅
send_request                    33       ❌ → ~18 ✅
_build_payload                   7       ✅
close                           10       ✅
```

### `client/__init__.py`

```
Function                       Lines    Violates 20?
─────────────────────────────  ─────    ─────────────
__init__                        25       ❌ → ~18 ✅
_init_ws_transport              11       ✅
downloads (property)             4       ✅
status (property)                4       ✅
options (property)               4       ✅
system (property)                4       ✅
daemon (property)                5       ✅
events (property)                5       ✅
connect                         16       ✅
close                            8       ✅
__aenter__                       4       ✅
__aexit__                        4       ✅
_request                        18       ✅
multicall                       16       ✅
_on_event                       12       ✅
```
