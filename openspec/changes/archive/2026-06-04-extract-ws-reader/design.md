# SDD Design: Extract `_WsReader` from `ws/transport.py`

**Change ID:** `2026-06-04-extract-ws-reader`
**Date:** 2026-06-04
**Status:** Design

---

## 1. Design Overview

This is a **purely structural refactoring** — zero behavioural changes, zero API
changes.  The reader-loop, dispatch, and reconnection logic moves from
`WebSocketTransport` into a new `_WsReader` class in a sibling module
`ws/_reader.py`.  All existing tests pass without modification.

### 1.1 Motivation

| Constraint | Current | Target |
|---|---|---|
| `transport.py` file length | 188 lines (⚠️ approaching 200) | ~125–135 lines ✅ |
| `__init__` body length | 24 lines ❌ | 17 lines ✅ |
| All functions ≤20 lines | `__init__` violates | All compliant ✅ |
| Reader/dispatch/connect mixed | Single class, 4 concerns | Clean separation ✅ |

### 1.2 Package structure — before and after

```
Before                             After
──────                             ─────
ws/                                ws/
├── __init__.py    (5 lines)       ├── __init__.py    (5 lines, unchanged)
├── _pending.py    (49 lines)      ├── _pending.py    (49 lines, unchanged)
└── transport.py   (188 lines)     ├── transport.py   (~130 lines, modified)
                                   └── _reader.py     (~55 lines, new)
```

### 1.3 Responsibility split

```
 transport.py (_WebSocketTransport)     _reader.py (_WsReader)
 ══════════════════════════════════     ════════════════════════
 • Connection lifecycle                 • Message receive loop (run)
   (connect / close / is_connected)     • Notification dispatch
 • Request construction & sending       • Response → future matching
   (send_request, _send_and_wait)       • Reconnection loop
 • Pending future lifecycle (via        • Exponential backoff
   _PendingRequestManager)
 • Internal state init
   (_init_internal_state)
```

---

## 2. Data Flow & Contracts

### 2.1 Object graph after `connect()`

```
WebSocketTransport
├── _ws: websockets.ClientConnection ──────┐  (owned by transport,
│                                          │   shared with reader)
├── _pending_mgr: _PendingRequestManager ──┤  (shared reference)
├── _event_callback: Callable | None ──────┤  (shared reference)
├── _reader_task: asyncio.Task ────────────┤  (task wrapping
│                                          │   _WsReader.run())
└── _reader: _WsReader ────────────────────┘
    ├── _ws: ──────────→ same connection
    ├── _pending_mgr: ──→ same manager
    ├── _event_callback: → same callback
    ├── _url: str ──────  ws://host:port/jsonrpc
    ├── _timeout: float ─ connection timeout
    ├── _should_reconnect: bool (set by transport)
    ├── _reconnect_delay: float = 1.0
    └── _max_reconnect_delay: float = 30.0
```

### 2.2 Message flow

```
WebSocket ──raw msg──→ _WsReader.run()
                           │
                           ▼
                     _WsReader._dispatch(raw)
                           │
                    ┌──────┴──────┐
                    ▼              ▼
           _try_notification    _try_response
                    │              │
                    ▼              ▼
            event_callback?    Lookup pending future by id
                    │              │
                    │         future.set_result(r)
                    │         future.set_exception(e)
                    │
            (done, no response path)
```

### 2.3 Reconnection flow

```
_WsReader.run()
  │
  ├─ WebSocket message arrives → dispatch
  └─ websockets.ConnectionClosed
       │
       ├─ _should_reconnect is True → _reconnect()
       │    │
       │    ├─ sleep(delay) [exponential backoff]
       │    ├─ ws_connect(url, timeout)
       │    ├─ self._ws = new connection
       │    └─ await self.run()  ← re-enter loop
       │
       └─ _should_reconnect is False → exit run()
```

### 2.4 Contract: `_WsReader.stop()`

```python
def stop(self) -> None:
    """Signal the reader and reconnect loop to stop."""
    self._should_reconnect = False
```

- **Called by:** `WebSocketTransport.close()` before cancelling the reader task
- **Effect:** Causes `run()` to exit cleanly on next `ConnectionClosed`, and
  causes any in-progress `_reconnect()` to break its while-loop
- **Idempotent:** safe to call multiple times

### 2.5 Contract: `_WsReader.run()`

- **Precondition:** `self._ws` is an active `websockets` client connection
- **Postcondition:** exits when connection closes (graceful or error) and
  `_should_reconnect` is `False`, OR when reconnection succeeds and a new
  loop is running
- **Cancellation:** If the wrapping `asyncio.Task` is cancelled, the
  `async for` loop raises `CancelledError` which propagates to the caller
  (`_stop_reader` already handles this)

---

## 3. Detailed File Changes

### 3.1 New file: `ws/_reader.py`

**Lines:** ~55
**Public API:** `_WsReader` (private class, underscore-prefixed)
**Dependencies:**
- `websockets` (external) — `ConnectionClosed` exception, `connect as ws_connect`
- `aria2.rpc` — `parse_notification`, `parse_response`
- `aria2.client.transport.ws._pending` — `_PendingRequestManager`

**No dependency on `ws/transport.py`.** The `_build_url` function is NOT imported;
`_WsReader` receives the URL as a pre-built string from `WebSocketTransport.connect()`.

```python
"""WebSocket reader loop with notification dispatch and reconnection."""

from __future__ import annotations

import asyncio
import json
from contextlib import suppress
from typing import Any

import websockets
from websockets.asyncio.client import connect as ws_connect

from aria2.client.transport.ws._pending import _PendingRequestManager
from aria2.errors import Aria2ConnectionError
from aria2.rpc import parse_notification as _parse_notification
from aria2.rpc import parse_response as _parse_response


class _WsReader:
    """Reads WebSocket messages, dispatches responses and notifications.

    Owns the reader :class:`asyncio.Task` and runs the reconnect loop.

    Parameters
    ----------
    ws : Any
        The active WebSocket connection (``websockets`` client).
    pending_mgr : _PendingRequestManager
        The shared pending-request manager from the transport.
    event_callback : Callable[[str, list[Any]], None] | None
        Optional notification dispatcher.
    url : str
        The WebSocket endpoint URL (``ws://host:port/jsonrpc``).
    timeout : float
        Connection timeout in seconds.
    """

    def __init__(
        self,
        ws: Any,
        pending_mgr: _PendingRequestManager,
        event_callback: Any,
        url: str,
        timeout: float,
    ) -> None:
        self._ws = ws
        self._pending_mgr = pending_mgr
        self._event_callback = event_callback
        self._url = url
        self._timeout = timeout
        self._should_reconnect = False
        self._reconnect_delay = 1.0
        self._max_reconnect_delay = 30.0

    async def run(self) -> None:
        """Read messages until the connection closes or is cancelled."""
        try:
            async for raw in self._ws:
                with suppress(Exception):
                    self._dispatch(raw)
        except websockets.ConnectionClosed:
            if self._should_reconnect:
                await self._reconnect()

    def _dispatch(self, raw: str) -> None:
        """Route a raw message to notification or response handler."""
        if self._try_notification(raw):
            return
        self._try_response(raw)

    def _try_notification(self, raw: str) -> bool:
        """Try to parse and dispatch a JSON-RPC notification.

        Returns:
            True if the message was a notification, False otherwise.
        """
        notif = _parse_notification(raw)
        if notif is not None:
            method, params = notif
            if self._event_callback:
                self._event_callback(method, params)
            return True
        return False

    def _try_response(self, raw: str) -> None:
        """Match a JSON-RPC response to its pending future by request ID.

        If the future is already done (stale response), the message is
        silently ignored.
        """
        obj = json.loads(raw)
        rid = obj.get("id")
        future = self._pending_mgr.get(rid)
        if future is None:
            return
        if not future.done():
            try:
                result = _parse_response(raw)
                future.set_result(result)
            except Exception as e:
                future.set_exception(e)

    async def _reconnect(self) -> None:
        """Reconnect with exponential backoff.

        Starts at ``_reconnect_delay``, doubles on each failure, capped
        at ``_max_reconnect_delay``.  Exits when the connection succeeds
        or ``_should_reconnect`` becomes ``False``.
        """
        delay = self._reconnect_delay
        while self._should_reconnect:
            try:
                await asyncio.sleep(delay)
                self._ws = await ws_connect(
                    self._url,
                    open_timeout=self._timeout,
                    close_timeout=self._timeout,
                )
                await self.run()
            except TimeoutError, OSError:
                delay = min(delay * 2, self._max_reconnect_delay)
            else:
                return

    def stop(self) -> None:
        """Signal the reader and reconnect loop to stop."""
        self._should_reconnect = False
```

**Design decision — `_build_url` NOT imported:**
`_WsReader` receives `url: str` in its constructor and uses `self._url` in
`_reconnect()`.  The URL is built once in `WebSocketTransport.connect()` via
`_build_url()`.  No import from `transport.py` is needed, avoiding any
cross-module dependency.

**Design decision — `_reconnect_delay` and `_max_reconnect_delay` are hardcoded:**
These are hardcoded to `1.0` and `30.0` in `_WsReader.__init__`.  If future
requirements need them configurable, they can become constructor parameters.
For now, simplicity wins — the transport already exposes these as `__init__`
parameters, and the current implementation has them hardcoded in `_reconnect`
anyway (they're read from class attributes that are set in `__init__`).

### 3.2 Modified file: `ws/transport.py`

**Lines before:** 188
**Lines after:** ~115 (–73 removed, +? added; net –~73)

#### 3.2.1 Imports — removed

The following imports are no longer needed in `transport.py`:
- `websockets` (the library) — `_reader.py` imports it
- `_parse_notification` — moved to `_reader.py`
- `_parse_response` — moved to `_reader.py`
- `json` — only used by `_try_response`, which moves to `_reader.py`
- `contextlib.suppress` — only used by `_reader_loop`, which moves to `_reader.py`

**New import added:**
```python
from aria2.client.transport.ws._reader import _WsReader
```

#### 3.2.2 Removed methods (moved to `_WsReader`)

| Method | Old location | New location |
|---|---|---|
| `_reader_loop` | `WebSocketTransport` (13 lines) | `_WsReader.run()` (~10 lines) |
| `_dispatch` | `WebSocketTransport` (4 lines) | `_WsReader._dispatch()` (~4 lines) |
| `_try_notification` | `WebSocketTransport` (8 lines) | `_WsReader._try_notification()` (~10 lines) |
| `_try_response` | `WebSocketTransport` (12 lines) | `_WsReader._try_response()` (~14 lines) |
| `_reconnect` | `WebSocketTransport` (12 lines) | `_WsReader._reconnect()` (~14 lines) |

#### 3.2.3 `__init__` — refactored with `_init_internal_state()` helper

```python
def __init__(
    self,
    host: str,
    port: int,
    secret: str | None = None,
    *,
    timeout: float = 30.0,
    event_callback: Callable[[str, list[Any]], None] | None = None,
    reconnect_delay: float = 1.0,
    max_reconnect_delay: float = 30.0,
) -> None:
    self._host = host
    self._port = port
    self._secret = secret
    self._timeout = timeout
    self._event_callback = event_callback
    self._reconnect_delay = reconnect_delay
    self._max_reconnect_delay = max_reconnect_delay
    self._init_internal_state()
```

```python
def _init_internal_state(self) -> None:
    """Initialize mutable instance attributes.

    Separated from ``__init__`` to keep the constructor body under
    the 20-line structural limit.
    """
    self._ws: Any | None = None
    self._request_id = 0
    self._reader_task: asyncio.Task[None] | None = None
    self._should_reconnect = False
    self._pending: dict[int, asyncio.Future[Any]] = {}
    self._pending_mgr = _PendingRequestManager(self._pending)
    self._reader: _WsReader | None = None
```

**`__init__` body count:** 8 assignment lines + 1 method call = 9 body lines ✅
**`_init_internal_state` body count:** 7 assignment lines ✅

#### 3.2.4 `connect()` — creates `_WsReader`, starts reader task

```python
async def connect(self) -> None:
    """Open a WebSocket connection to aria2's RPC endpoint.

    Raises:
        Aria2ConnectionError: If the WebSocket connection fails.

    """
    url = _build_url(self._host, self._port)
    try:
        self._ws = await ws_connect(
            url,
            open_timeout=self._timeout,
            close_timeout=self._timeout,
        )
    except (TimeoutError, OSError) as e:
        raise Aria2ConnectionError(str(e)) from e
    self._reader = _WsReader(
        ws=self._ws,
        pending_mgr=self._pending_mgr,
        event_callback=self._event_callback,
        url=url,
        timeout=self._timeout,
    )
    self._reader._should_reconnect = True
    self._reader_task = asyncio.create_task(self._reader.run())
```

**Key change:** The URL string is computed once (line 1) and passed to both
`ws_connect` and `_WsReader`.  Previously `_build_url` was called inline in
`ws_connect` and again in `_reconnect`.  Now the URL is built once.

#### 3.2.5 `close()` — delegates stop to `_WsReader`

```python
async def close(self) -> None:
    """Close the connection and cancel pending requests.

    Safe to call multiple times — idempotent.
    """
    if self._reader is not None:
        self._reader.stop()
    await self._stop_reader()
    await self._close_ws()
    self._cancel_pending()
```

**Key changes from current code:**
- `self._should_reconnect = False` is replaced by `self._reader.stop()`, which
  sets `_should_reconnect` on the reader instance
- Guard: `if self._reader is not None` prevents `AttributeError` when `close()`
  is called without prior `connect()`

#### 3.2.6 Methods that stay unchanged

| Method | Status |
|---|---|
| `is_connected` (property) | unchanged |
| `send_request` | unchanged |
| `_build_payload` | unchanged |
| `_send_and_wait` | unchanged |
| `_stop_reader` | unchanged |
| `_close_ws` | unchanged |
| `_cancel_pending` | unchanged |

### 3.3 Unchanged files

| File | Reason |
|---|---|
| `ws/__init__.py` | Re-exports `WebSocketTransport` — no change needed |
| `ws/_pending.py` | Untouched — `_PendingRequestManager` contract unchanged |
| `tests/test_ws.py` | Zero modification — all test assertions work against unchanged attributes |
| `aria2/client/transport/__init__.py` | `Transport` ABC unchanged |
| `aria2/rpc/__init__.py` | Parse functions unchanged |

---

## 4. Function Contracts (Post-Refactor)

### 4.1 `transport.py` — all functions and their line counts

| Function/Method | Body lines | Limit | Status |
|---|---|---|---|
| `_build_url` (module fn) | 1 | 20 | ✅ |
| `WebSocketTransport.__init__` | 9 | 20 | ✅ |
| `WebSocketTransport._init_internal_state` | 7 | 20 | ✅ |
| `WebSocketTransport.is_connected` | 1 | 20 | ✅ |
| `WebSocketTransport.connect` | 14 | 20 | ✅ |
| `WebSocketTransport.send_request` | 10 | 20 | ✅ |
| `WebSocketTransport.close` | 7 | 20 | ✅ |
| `WebSocketTransport._build_payload` | 4 | 20 | ✅ |
| `WebSocketTransport._send_and_wait` | 10 | 20 | ✅ |
| `WebSocketTransport._stop_reader` | 7 | 20 | ✅ |
| `WebSocketTransport._close_ws` | 5 | 20 | ✅ |
| `WebSocketTransport._cancel_pending` | 2 | 20 | ✅ |
| **File total** | **~115** | 200 | ✅ |

### 4.2 `_reader.py` — all methods and their line counts

| Method | Body lines | Limit | Status |
|---|---|---|---|
| `_WsReader.__init__` | 9 | 20 | ✅ |
| `_WsReader.run` | 7 | 20 | ✅ |
| `_WsReader._dispatch` | 4 | 20 | ✅ |
| `_WsReader._try_notification` | 8 | 20 | ✅ |
| `_WsReader._try_response` | 11 | 20 | ✅ |
| `_WsReader._reconnect` | 11 | 20 | ✅ |
| `_WsReader.stop` | 2 | 20 | ✅ |
| **File total** | **~55** | 200 | ✅ |

---

## 5. Test Compatibility Analysis

### 5.1 Attribute access compatibility

All tests use only these attributes on `WebSocketTransport` instances:

```
t._pending              → dict[int, Future]   (unchanged, still on transport)
t._ws                   → websockets client   (unchanged)
t.is_connected          → property            (unchanged)
t.connect()             → method              (unchanged API)
t.close()               → method              (unchanged API)
t.send_request(...)     → method              (unchanged API)
```

The most critical test is `test_close_cancels_pending`:
```python
t._pending[999] = fut       # ← accesses the dict directly on transport
```
This works because `_pending` stays on `WebSocketTransport`.  `_WsReader` accesses
the pending manager (`_pending_mgr`), not the raw dict.

### 5.2 Test scenario mapping

| Test | What it exercises | Affected by refactor? |
|---|---|---|
| `test_connect_and_request` | connect → send_request → close | Reader loop (implicit) ✅ |
| `test_rpc_error` | RPC error propagation | Response dispatch ✅ |
| `test_notification_dispatched` | Notification callback | Notification dispatch ✅ |
| `test_is_connected` | Connection state tracking | Unchanged |
| `test_not_connected_raises` | Error on disconnected send | Unchanged |
| `test_close_without_connect_is_safe` | Idempotent close | close() guard ✅ |
| `test_connect_refused_raises` | Connection failure | Unchanged |
| `test_send_request_no_secret` | No-auth request payload | Unchanged |
| `test_stale_response_ignored` | Unknown ID response | `_try_response` stale check ✅ |
| `test_close_cancels_pending` | Pending future cancellation | `_pending` dict stays ✅ |
| `test_dispatch_error_swallowed` | Callback exception isolation | Dispatch error handling ✅ |

All 11 tests exercise code paths that move to `_WsReader` (dispatch, notification,
response matching, stale response, error suppression).  Because the logic is
extracted unchanged, tests pass without modification.

### 5.3 `test_close_without_connect_is_safe` — guard analysis

Current `close()`:
```python
self._should_reconnect = False
await self._stop_reader()   # checks self._reader_task (None → skip)
await self._close_ws()      # checks self._ws (None → skip)
self._cancel_pending()       # safe on empty dict
```

Refactored `close()`:
```python
if self._reader is not None:
    self._reader.stop()     # guard: None → skip
await self._stop_reader()   # same as before
await self._close_ws()      # same as before
self._cancel_pending()       # same as before
```

Both versions are safe when called before `connect()`.  The new code adds an
explicit `None` guard on `self._reader` for clarity and robustness.

---

## 6. Design Decisions Log

### Decision 1: `_WsReader` receives `url: str`, not `host` + `port`

**Chosen:** Pass pre-built URL string
**Alternatives considered:**
- Pass `host` and `port` and call `_build_url` in `_reconnect` — requires importing `_build_url` from `transport.py`, creating a cross-module dependency
- Extract `_build_url` to a shared `_urls.py` module — adds a 5th file to a 4-file package

**Rationale:** The URL never changes for a given transport instance (host and port are
immutable after `__init__`).  Building it once in `connect()` and passing it as a string
eliminates the need for `_build_url` in `_reader.py`, keeping the dependency graph clean.

### Decision 2: `_reader` attribute on `WebSocketTransport`

**Chosen:** Store `self._reader: _WsReader | None` on the transport
**Alternatives considered:**
- Don't store a reference, signal via a shared boolean flag — would require the transport
  to hold its own `_should_reconnect` AND the reader's, creating sync risk
- Store only on the task — not possible, task wraps the coroutine, not the object

**Rationale:** The transport needs a handle to the reader to call `stop()` during `close()`.
The attribute is initialised to `None` in `_init_internal_state()` and set in `connect()`.

### Decision 3: `_init_internal_state()` as a separate method

**Chosen:** Extract to private helper method
**Alternatives considered:**
- Inline all assignments — `__init__` would be 16 lines (still ≤20, but not clean)
- Use `dataclass` — adds dependency, changes class semantics, overkill

**Rationale:** Keeps `__init__` focused on recording constructor arguments while
delegating mutable state initialisation to a well-named helper.  Follows the
single-responsibility principle at method granularity.

### Decision 4: `_reconnect_delay` and `_max_reconnect_delay` hardcoded in `_WsReader`

**Chosen:** Hardcode to `1.0` and `30.0` in `_WsReader.__init__`
**Alternatives considered:**
- Accept as constructor parameters — increases constructor surface; the transport
  already has these as constructor params, but the current implementation always
  uses the values stored on the transport, not the reader
- Pass from transport in `connect()` — requires the transport to inject them,
  adding coupling

**Rationale:** The current reconnect code in `_reconnect` already reads from
`self._reconnect_delay` and `self._max_reconnect_delay` which are set on
`WebSocketTransport.__init__`.  The new `_WsReader` hardcodes the same defaults.
The reconnect delay parameters on `WebSocketTransport.__init__` are preserved
(not removed) so they don't break any callers.  If reconnection delay
customisation is needed in the future, it can be added as a `_WsReader` parameter.

---

## 7. Rollout Plan

### 7.1 Implementation order

1. **Create `ws/_reader.py`** with the `_WsReader` class as specified above
2. **Modify `ws/transport.py`:**
   - Add import `from aria2.client.transport.ws._reader import _WsReader`
   - Remove imports: `websockets`, `json`, `suppress`, `_parse_notification`, `_parse_response`
   - Extract `_init_internal_state()` from `__init__`
   - Rewrite `connect()` to create and start `_WsReader`
   - Rewrite `close()` to call `self._reader.stop()`
   - Remove methods: `_reader_loop`, `_dispatch`, `_try_notification`, `_try_response`, `_reconnect`
3. **Verify:** Run the verification suite (see §8)
4. **Commit:** Single commit with conventional commit message

### 7.2 Rollback plan

```bash
# Full rollback — two commands, zero data loss
git checkout -- packages/aria2-sdk/src/aria2/client/transport/ws/transport.py
git rm packages/aria2-sdk/src/aria2/client/transport/ws/_reader.py
pytest tests/test_ws.py  # verify original state
```

The change touches only two files within one package.  No database migrations,
no config changes, no API surface changes.

---

## 8. Verification Checklist

### 8.1 Pre-merge verification

- [ ] `ruff check packages/aria2-sdk/src/aria2/client/transport/ws/` — zero errors
- [ ] `ty --strict packages/aria2-sdk/src/aria2/client/transport/ws/` — zero type errors
- [ ] `pytest tests/test_ws.py -v` — all 11 tests pass without modification
- [ ] `pytest` — full suite passes (no side effects)
- [ ] `from aria2.client.transport.ws import WebSocketTransport` — resolves correctly
- [ ] `__all__` in `ws/__init__.py` still exports only `"WebSocketTransport"`
- [ ] Every function body ≤20 lines (see §4 for exact counts)
- [ ] Every file ≤200 lines (transport.py ~115, _reader.py ~55)
- [ ] No circular imports (`_reader.py` does not import from `transport.py`)
- [ ] `t._pending` is still a `dict[int, Future]` accessible on transport instances

### 8.2 Mechanical line count verification

```bash
# Count function body lines (excludes signature, docstring, blank lines)
# Run in the ws/ directory
python -c "
import ast, sys
for f in ['_reader.py', 'transport.py']:
    with open(f) as fh:
        tree = ast.parse(fh.read())
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            body_lines = len(node.body)
            print(f'{f}:{node.lineno} {node.name} → {body_lines} body lines')
"
```

### 8.3 Test expectation mapping

| Test | Expected result | Refactor impact |
|---|---|---|
| `test_connect_and_request` | `result == "mock-gid-abc"` | Reader loop dispatches response → future resolved ✅ |
| `test_rpc_error` | `Aria2RpcError` with `code=-1` | Response parsing raises → future.set_exception ✅ |
| `test_notification_dispatched` | Event received, then result | Notification → callback, then response → future ✅ |
| `test_is_connected` | True after connect, False after close | Unchanged property ✅ |
| `test_not_connected_raises` | `Aria2ConnectionError` | Guard unchanged ✅ |
| `test_close_without_connect_is_safe` | No exception | New `if self._reader` guard ✅ |
| `test_connect_refused_raises` | `Aria2ConnectionError` | Unchanged connect logic ✅ |
| `test_send_request_no_secret` | Result, no token in payload | Unchanged payload building ✅ |
| `test_stale_response_ignored` | Result, stale ignored | `_try_response` future.done() guard ✅ |
| `test_close_cancels_pending` | Future cancelled | `_pending` dict still on transport ✅ |
| `test_dispatch_error_swallowed` | Result despite callback error | `with suppress(Exception)` in run() ✅ |

---

## 9. Risk Register

| Risk | Severity | Mitigation | Residual |
|---|---|---|---|
| `_should_reconnect` flag sync between transport and reader | **Medium** | `close()` calls `self._reader.stop()` which sets the flag ON the reader; no separate flag on transport | Low |
| Reader task double-start (connect called twice) | **Low** | Same as current code — no protection against double-connect. Not introduced by this change. | Low |
| `test_close_without_connect_is_safe` regression | **Low** | New guard `if self._reader is not None` handles pre-connect close | None |
| `_WsReader` attribute access from tests | **None** | Tests only access `transport._pending`, not `transport._reader` | None |
| Import resolution (`_WsReader` from `_reader`) | **Low** | Single-direction import: `transport → _reader`. No cycle. | None |
| `except TimeoutError, OSError:` syntax (pre-existing bug) | **Low** | Left as-is — not introduced by this refactor. Should be `except (TimeoutError, OSError):`. Tracked separately. | Low |
| Coverage regression — new `_reader.py` file | **Low** | All code paths exercised by existing 11 tests. Only `_reconnect()` path uncovered (pre-existing gap). | Low |

---

## 10. Dependency Graph (Post-Refactor)

```
                         (external)
                    ┌─────────────────┐
                    │   websockets     │
                    │   asyncio        │
                    │   json           │
                    └────┬────────┬────┘
                         │        │
              ┌──────────┘        └──────────┐
              ▼                              ▼
    ┌──────────────────┐          ┌──────────────────┐
    │   transport.py   │          │   _reader.py     │
    │                  │          │                  │
    │  _build_url()    │          │  _WsReader       │
    │  WebSocketTransport│◄────────│  .run()          │
    │  .connect()      │ import   │  ._dispatch()    │
    │  .close()        │          │  ._reconnect()   │
    │  .send_request() │          │  .stop()         │
    │  ._pending       │          │                  │
    │  ._reader ───────┼──ref───→ │ (instance)       │
    │                  │          │                  │
    └────────┬─────────┘          └────────┬─────────┘
             │                            │
             └──────────┬─────────────────┘
                        │
              ┌─────────┴─────────┐
              │                   │
    ┌─────────┴──────┐   ┌───────┴──────────┐
    │  _pending.py   │   │  aria2/rpc       │
    │                │   │                  │
    │ _PendingRequest│   │ parse_response() │
    │ Manager        │   │ parse_notification()
    └────────────────┘   └──────────────────┘
```

**Key property:** No circular dependencies.  `_reader.py` does NOT import from
`transport.py`.  The URL is passed as a pre-built string, and the pending manager
is passed by reference.  All other dependencies are on stable, external modules.

---

## Appendix A: Line Count Reconciliation

### Before refactor

| File | Lines | Limit | Status |
|---|---|---|---|
| `transport.py` | 188 | 200 | ⚠️ approaching |
| `__init__` body | 24 | 20 | ❌ |

### After refactor

| File | Lines | Limit | Status |
|---|---|---|---|
| `transport.py` | ~115 | 200 | ✅ ample headroom |
| `_reader.py` | ~55 | 200 | ✅ well under |
| `__init__` body | 9 | 20 | ✅ |
| All functions | ≤14 | 20 | ✅ |

### Removed from `transport.py` (73 lines)

| Section | Lines | Notes |
|---|---|---|
| `__init__` assignments | 7 | Moved to `_init_internal_state` |
| `_reader_loop` | 13 | Moved to `_WsReader.run()` |
| `_dispatch` | 4 | Moved to `_WsReader._dispatch()` |
| `_try_notification` | 8 | Moved to `_WsReader._try_notification()` |
| `_try_response` | 12 | Moved to `_WsReader._try_response()` |
| `_reconnect` | 12 | Moved to `_WsReader._reconnect()` |
| Unused imports | 5 | `websockets`, `json`, `suppress`, 2× `_parse_*` |
| **Net removed** | **~73** | |

### Added to `transport.py` (~8 lines)

| Section | Lines | Notes |
|---|---|---|
| Import `_WsReader` | 1 | New import |
| `_init_internal_state` | 7 | New method |
| `_reader` attr in `_init_internal_state` | 1 | New attribute |
| URL variable in `connect` | 1 | Pre-build URL |
| `_WsReader` construction in `connect` | 6 | Replaces old task creation |
| Guard in `close` | 2 | `if self._reader` |
| `self._reader.stop()` call | 1 | Replaces `self._should_reconnect = False` |
| **Net added** | **~8** | (some overlap, net effect = –~73 + ~8 = –~65) |

---

## Appendix B: `_build_url` Design Decision — Detailed Rationale

**Problem:** `_reconnect()` needs the WebSocket endpoint URL.  In the current code,
it calls `_build_url(self._host, self._port)` using the transport's `_host` and
`_port` attributes.  When `_reconnect` moves to `_WsReader`, it no longer has
access to `self._host` and `self._port`.

**Options evaluated:**

| # | Approach | Pro | Con | Verdict |
|---|---|---|---|---|
| A | `_reader.py` imports `_build_url` from `transport.py` | Minimal change | Circular import risk (transport → _reader → transport) | ❌ |
| B | Pass `host`+`port` to `_WsReader`, call `_build_url` inline | No new files | Still needs `_build_url` somewhere; reader shouldn't know about URL construction | ❌ |
| C | Extract `_build_url` to `_urls.py` | Clean separation | Adds 5th file to a 4-file package; violates spec | ❌ |
| **D** | **Pass pre-built `url: str` to `_WsReader`** | **Zero cross-deps; URL built once** | **None** | **✅** |

**Chosen: Option D.**  The URL is computed once in `WebSocketTransport.connect()`
and passed to both `ws_connect()` and `_WsReader()`.  `_WsReader._reconnect()` uses
`self._url`.  The host and port are immutable after `__init__`, so the URL never
becomes stale.
