# SDD Design: WebSocketTransport Refactoring — Extract into `ws/` Package

**Change ID:** `2026-06-03-ws-transport-split`
**Date:** 2026-06-03
**Status:** Draft
**Strategy:** A — package extraction with `_pending` as plain dict, `_PendingRequestManager` as operator

---

## 1. Architecture

### 1.1 File Structure

```
transport/
├── __init__.py              # Transport ABC (unchanged)
├── http.py                  # HttpTransport (unchanged)
└── ws/                      # ← NEW package
    ├── __init__.py          # Re-export WebSocketTransport from .transport
    ├── transport.py         # WebSocketTransport class + _build_url helper
    └── _pending.py          # _PendingRequestManager helper
```

**Before (to be deleted):**
```
transport/
└── ws.py                    # ← DELETED (207 lines, multiple violations)
```

### 1.2 Ownership Boundaries

```
┌─────────────────────────────────────────────────────┐
│ transport/ws/__init__.py (8 lines)                  │
│                                                     │
│   Owns: public re-export of WebSocketTransport      │
│   Imports: .transport.WebSocketTransport             │
│   Exposes: WebSocketTransport                       │
└──────────────────┬──────────────────────────────────┘
                   │ from aria2.client.transport.ws import WebSocketTransport
                   ▼
┌─────────────────────────────────────────────────────┐
│ transport/ws/transport.py (~160 lines)              │
│                                                     │
│   Owns: WebSocketTransport class                    │
│   Owns: _build_url(host, port) module helper        │
│   Imports: ._pending._PendingRequestManager         │
│   Depends on: Transport ABC, rpc helpers, errors    │
│                                                     │
│   Internal state:                                   │
│   ┌─────────────────────────────────────────────┐   │
│   │ self._host, self._port, self._secret        │   │
│   │ self._timeout                                │   │
│   │ self._event_callback                        │   │
│   │ self._reconnect_delay, self._max_...        │   │
│   │ self._ws: WebSocket | None  (connection)    │   │
│   │ self._request_id: int        (monotonic)    │   │
│   │ self._pending: dict[int, Future]  ← owned   │   │
│   │ self._pending_mgr: _PendingRequestManager   │   │
│   │ self._reader_task: Task | None               │   │
│   │ self._should_reconnect: bool                 │   │
│   └─────────────────────────────────────────────┘   │
│                                                     │
│   self._pending is a plain dict[int, Future].       │
│   _PendingRequestManager receives it by reference   │
│   and operates on it.  Tests accessing t._pending   │
│   see a plain dict — zero API change.               │
└──────────────────┬──────────────────────────────────┘
                   │ receives self._pending by reference
                   ▼
┌─────────────────────────────────────────────────────┐
│ transport/ws/_pending.py (~35 lines)                │
│                                                     │
│   Owns: _PendingRequestManager class                │
│   Does NOT own the dict — operates on caller's ref  │
│                                                     │
│   Methods:                                          │
│     register(rid, future) → None                    │
│     pop(rid) → Future | None                        │
│     get(rid) → Future | None                        │
│     cancel_all() → None                             │
└─────────────────────────────────────────────────────┘
```

### 1.3 Import Graph

```
transport/__init__.py          ← Transport ABC (no change)
        │
        │ subclass
        ▼
transport/ws/__init__.py       ← re-export
        │
        │ from .transport import WebSocketTransport
        ▼
transport/ws/transport.py      ← WebSocketTransport
        │
        ├── from ._pending import _PendingRequestManager
        ├── from aria2.client.transport import Transport
        ├── from aria2.rpc import build_request, build_request_with_secret,
        │       parse_notification, parse_response
        └── from aria2.errors import Aria2ConnectionError
                │
                │ receives dict ref
                ▼
transport/ws/_pending.py       ← _PendingRequestManager
        │
        └── (stdlib only: asyncio, typing)
```

**External consumers (unchanged import paths):**

| Consumer | Import | Resolves via |
|---|---|---|
| `aria2/client/__init__.py` | `from aria2.client.transport.ws import WebSocketTransport` | `ws/__init__.py` re-export |
| `tests/test_ws.py` | `from aria2.client.transport.ws import WebSocketTransport` | `ws/__init__.py` re-export |

---

## 2. File Specs

### 2.1 `transport/ws/__init__.py`

**Purpose:** Canonical re-export point.  Preserves the existing import path
`from aria2.client.transport.ws import WebSocketTransport` so zero consumer
changes are required.

**Source:**

```python
"""WebSocket transport package for aria2 JSON-RPC."""
from aria2.client.transport.ws.transport import WebSocketTransport

__all__ = ["WebSocketTransport"]
```

**Line count:** ~5 (3 non-blank).

### 2.2 `transport/ws/transport.py`

**Purpose:** Core `WebSocketTransport` implementation.  Owns connection
lifecycle, request/response dispatching, reader loop, and reconnection.
Delegates pending-future operations to `_PendingRequestManager` and URL
construction to the module-level `_build_url` helper.

**Source:**

```python
"""WebSocket transport for aria2 JSON-RPC with event dispatch."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from contextlib import suppress
from typing import Any

import websockets
from websockets.asyncio.client import connect as ws_connect

from aria2.client.transport import Transport
from aria2.client.transport.ws._pending import _PendingRequestManager
from aria2.errors import Aria2ConnectionError
from aria2.rpc import build_request as _build_noauth
from aria2.rpc import build_request_with_secret as _build
from aria2.rpc import parse_notification as _parse_notification
from aria2.rpc import parse_response as _parse_response


# ── Module-level helpers ──────────────────────────────────


def _build_url(host: str, port: int) -> str:
    """Build the WebSocket URL for the aria2 JSON-RPC endpoint."""
    return f"ws://{host}:{port}/jsonrpc"


# ── Transport implementation ──────────────────────────────


class WebSocketTransport(Transport):
    """JSON-RPC over WebSocket via ``websockets`` library.

    Primary transport — sends requests and receives both responses
    and push notifications from the aria2 daemon.
    """

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

        self._ws: Any | None = None
        self._request_id = 0
        self._pending: dict[int, asyncio.Future[Any]] = {}
        self._pending_mgr = _PendingRequestManager(self._pending)
        self._reader_task: asyncio.Task[None] | None = None
        self._should_reconnect = False

    # ── Transport interface ──────────────────────────────

    @property
    def is_connected(self) -> bool:
        """Return whether the WebSocket connection is open."""
        return self._ws is not None and not self._ws.close_code is not None

    async def connect(self) -> None:
        """Open a WebSocket connection to the aria2 RPC endpoint.

        Starts a background reader task to receive responses and
        push notifications from the daemon.

        Raises:
            Aria2ConnectionError: If the WebSocket connection fails.

        """
        try:
            self._ws = await ws_connect(
                _build_url(self._host, self._port),
                open_timeout=self._timeout,
                close_timeout=self._timeout,
            )
        except (TimeoutError, OSError) as e:
            raise Aria2ConnectionError(str(e)) from e
        self._should_reconnect = True
        self._reader_task = asyncio.create_task(self._reader_loop())

    async def send_request(
        self, method: str, params: list[Any], *, add_secret: bool = True
    ) -> Any:
        """Send a JSON-RPC request over WebSocket.

        Sends the request and waits for the matching response.
        Push notifications are handled separately by the reader loop
        and dispatched via the event callback.

        Args:
            method: JSON-RPC method name (e.g. ``"aria2.addUri"``).
            params: Parameters for the method.
            add_secret: If True, prepend ``token:{secret}`` to params.

        Returns:
            The parsed JSON-RPC result.

        Raises:
            Aria2ConnectionError: If not connected or the WebSocket fails.

        """
        if not self.is_connected:
            raise Aria2ConnectionError("WebSocket transport is not connected")
        self._request_id += 1
        payload = self._build_payload(method, params, add_secret=add_secret)
        return await self._send_and_wait(payload, self._request_id)

    async def close(self) -> None:
        """Close the WebSocket connection and cancel pending requests.

        Stops the reader task, closes the socket, and cancels any
        futures still waiting for responses.  Safe to call multiple
        times — idempotent.
        """
        self._should_reconnect = False
        await self._stop_reader()
        await self._close_ws()
        self._cancel_pending()

    # ── Private helpers: request building ─────────────────

    def _build_payload(
        self, method: str, params: list[Any], *, add_secret: bool
    ) -> str:
        """Build a JSON-RPC request payload string."""
        if add_secret:
            return _build(method, self._secret, params, request_id=self._request_id)
        return _build_noauth(method, params, request_id=self._request_id)

    async def _send_and_wait(self, payload: str, rid: int) -> Any:
        """Send *payload* over the WebSocket and await the response."""
        future: asyncio.Future[Any] = asyncio.get_event_loop().create_future()
        self._pending_mgr.register(rid, future)
        assert self._ws is not None
        try:
            await self._ws.send(payload)
            return await asyncio.wait_for(future, timeout=self._timeout)
        finally:
            self._pending_mgr.pop(rid)

    # ── Private helpers: connection teardown ──────────────

    async def _stop_reader(self) -> None:
        """Cancel the background reader task if it is running."""
        if self._reader_task:
            self._reader_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._reader_task
            self._reader_task = None

    async def _close_ws(self) -> None:
        """Close the WebSocket connection if it is open."""
        if self._ws:
            await self._ws.close()
            self._ws = None

    def _cancel_pending(self) -> None:
        """Cancel all pending request futures."""
        self._pending_mgr.cancel_all()

    # ── Internal reader loop ─────────────────────────────

    async def _reader_loop(self) -> None:
        """Continuously read messages from the WebSocket.

        Responses are matched to pending futures by request ID.
        Notifications are dispatched to the event callback.
        """
        assert self._ws is not None
        try:
            async for raw in self._ws:
                with suppress(Exception):
                    self._dispatch(raw)
        except websockets.ConnectionClosed:
            if self._should_reconnect:
                await self._reconnect()

    def _dispatch(self, raw: str) -> None:
        """Route an incoming message to a pending future or event callback."""
        if self._try_notification(raw):
            return
        self._try_response(raw)

    def _try_notification(self, raw: str) -> bool:
        """Try to handle *raw* as a JSON-RPC notification.

        Returns:
            True if it was a notification (even if no callback is set),
            False if it looks like a response.

        """
        notif = _parse_notification(raw)
        if notif is not None:
            method, params = notif
            if self._event_callback:
                self._event_callback(method, params)
            return True
        return False

    def _try_response(self, raw: str) -> None:
        """Try to handle *raw* as a JSON-RPC response.

        Matches the response to a pending future by request ID.
        Silently ignores responses with unknown IDs.
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

    # ── Reconnection ─────────────────────────────────────

    async def _reconnect(self) -> None:
        """Exponential backoff reconnection.

        On connection loss, repeatedly attempts to reconnect with
        exponentially increasing delay, capped at
        ``max_reconnect_delay``.
        """
        delay = self._reconnect_delay
        while self._should_reconnect:
            try:
                await asyncio.sleep(delay)
                self._ws = await ws_connect(
                    _build_url(self._host, self._port),
                    open_timeout=self._timeout,
                    close_timeout=self._timeout,
                )
                await self._reader_loop()
            except (TimeoutError, OSError):
                delay = min(delay * 2, self._max_reconnect_delay)
            else:
                return
```

**Method line counts (body only):**

| Method | Lines | Status |
|---|---|---|
| `__init__` | 14 | ✅ |
| `is_connected` | 2 | ✅ |
| `connect` | 9 | ✅ |
| `send_request` | 5 | ✅ |
| `close` | 5 | ✅ |
| `_build_payload` | 3 | ✅ |
| `_send_and_wait` | 8 | ✅ |
| `_stop_reader` | 6 | ✅ |
| `_close_ws` | 4 | ✅ |
| `_cancel_pending` | 2 | ✅ |
| `_reader_loop` | 8 | ✅ |
| `_dispatch` | 4 | ✅ |
| `_try_notification` | 7 | ✅ |
| `_try_response` | 9 | ✅ |
| `_reconnect` | 11 | ✅ |

All methods ≤20 lines ✅. Total file ≈160 lines ≤200 ✅.

### 2.3 `transport/ws/_pending.py`

**Purpose:** Encapsulates operations on the pending-request dictionary.
Does **not** own the dictionary; receives it by reference from
`WebSocketTransport` so `t._pending` remains a plain `dict[int, Future]`
for test compatibility.

**Source:**

```python
"""Pending request future manager for WebSocket transport."""

from __future__ import annotations

import asyncio
from typing import Any


class _PendingRequestManager:
    """Manages pending JSON-RPC request futures.

    Wraps operations on the ``dict[int, asyncio.Future[Any]]`` that
    maps request IDs to awaiting futures.  The dict is owned by
    ``WebSocketTransport`` as ``self._pending`` — this class receives
    a reference and provides helper methods.
    """

    def __init__(self, pending: dict[int, asyncio.Future[Any]]) -> None:
        """Wrap *pending*, a dict owned by the transport."""
        self._pending = pending

    def register(self, rid: int, future: asyncio.Future[Any]) -> None:
        """Register *future* under request ID *rid*."""
        self._pending[rid] = future

    def pop(self, rid: int) -> asyncio.Future[Any] | None:
        """Remove and return the future for *rid*.

        Returns ``None`` if *rid* is not in the map.
        """
        return self._pending.pop(rid, None)

    def get(self, rid: int) -> asyncio.Future[Any] | None:
        """Return the future for *rid* without removing it.

        Returns ``None`` if *rid* is not in the map.
        """
        return self._pending.get(rid)

    def cancel_all(self) -> None:
        """Cancel all incomplete futures and clear the map.

        Futures that have already completed (result or exception set)
        are left untouched.
        """
        for fut in self._pending.values():
            if not fut.done():
                fut.cancel()
        self._pending.clear()
```

**Line count:** ~35 lines (including imports, docstrings) ≤200 ✅.

---

## 3. `_PendingRequestManager` API

### 3.1 Constructor

```
_PendingRequestManager(pending: dict[int, asyncio.Future[Any]]) → None
```

Accepts the transport-owned `_pending` dict by reference.  The manager
does **not** copy or own the dict — it stores the reference and
operates on it directly.

### 3.2 `register(rid: int, future: asyncio.Future[Any]) → None`

Registers a future under the given request ID.  Called by `_send_and_wait`
before the payload is sent.

**Preconditions:** `rid` is unique (monotonically incrementing in
`WebSocketTransport._request_id`).

**Postconditions:** `self._pending[rid] == future`.

### 3.3 `pop(rid: int) → asyncio.Future[Any] | None`

Removes and returns the future for the given request ID.  Returns `None`
if the ID is not found.  Called in the `finally` block of `_send_and_wait`
to clean up after the request completes or times out.

**Postconditions:** `rid` is no longer in the dict (either popped or
wasn't there).

### 3.4 `get(rid: int) → asyncio.Future[Any] | None`

Looks up a future by request ID without removing it.  Returns `None` if
the ID is not found.  Called by `_try_response` to match incoming
responses to pending requests.

### 3.5 `cancel_all() → None`

Cancels every incomplete future in the dict and then clears the dict.
Futures that have already been resolved (`.done()` returns `True`) are
left untouched — only pending ones are cancelled.

Called by `_cancel_pending()` during `close()`.

**Postconditions:**
- All incomplete futures have `.cancelled() == True`
- `self._pending` is empty (`.clear()` invoked)

### 3.6 Why Option A (reference-based)

| Aspect | Option A (chosen) | Option B (rejected) |
|---|---|---|
| Dict ownership | Transport | Manager |
| `t._pending` type | `dict[int, Future]` ✅ | Manager instance ❌ |
| Test compatibility | Zero changes | Would need `__getitem__` proxy |
| Coupling | Low — manager is stateless helper | Medium — manager owns state |

The only test accessing `t._pending` directly is `test_close_cancels_pending`,
which does `t._pending[999] = fut`.  With Option A, `t._pending` is a plain
dict and the test works without modification.

**Trade-off acknowledged:** The transport code uses the manager for
register/pop/get while tests can still access the dict directly.  This
two-interface pattern is intentional for backward compatibility and will
be documented in the class docstring.

---

## 4. Extraction Mappings

### 4.1 Complete Function Line Count Reconciliation

| Original function | Original lines | Extracted helpers | Target lines | Status |
|---|---|---|---|---|
| `__init__` | 24 | _(trim blanks/comments)_ | 14 | ✅ |
| `is_connected` | 2 | _(unchanged)_ | 2 | ✅ |
| `connect` | 22 | `_build_url(host, port)` — module helper | 9 | ✅ |
| `send_request` | 39 | `_build_payload()` + `_send_and_wait()` | 5 | ✅ |
| `close` | 25 | `_stop_reader()` + `_close_ws()` + `_cancel_pending()` | 5 | ✅ |
| `_reader_loop` | 15 | _(unchanged)_ | 8 | ✅ |
| `_dispatch` | 23 | `_try_notification()` + `_try_response()` | 4 | ✅ |
| `_reconnect` | 18 | _(syntax fix only)_ | 11 | ✅ |

### 4.2 Extracted Method Details

| Extracted method | Extracted from | Body lines | Key behavior |
|---|---|---|---|
| `_build_url(host, port)` | `connect`, `_reconnect` | 1 | Returns `f"ws://{host}:{port}/jsonrpc"` |
| `_build_payload(method, params, *, add_secret)` | `send_request` | 3 | Conditionally builds auth/no-auth payload |
| `_send_and_wait(payload, rid)` | `send_request` | 8 | Creates future, registers with mgr, sends, awaits, cleans up |
| `_stop_reader()` | `close` | 6 | Cancels reader task, awaits, nulls reference |
| `_close_ws()` | `close` | 4 | Closes WebSocket, nulls reference |
| `_cancel_pending()` | `close` | 2 | Delegates to `_pending_mgr.cancel_all()` |
| `_try_notification(raw)` | `_dispatch` | 7 | Parses notification, dispatches to callback, returns bool |
| `_try_response(raw)` | `_dispatch` | 9 | Matches response to pending future, sets result/exception |

### 4.3 File Line Count Reconciliation

| File | Lines | Limit | Status |
|---|---|---|---|
| `ws/__init__.py` | ~5 | 200 | ✅ |
| `ws/transport.py` | ~160 | 200 | ✅ |
| `ws/_pending.py` | ~35 | 200 | ✅ |
| _(deleted)_ `ws.py` | 207 → removed | — | — |

### 4.4 Behavioral Delta

**The only behavioral change is a bug fix:**

| Location | Before | After |
|---|---|---|
| `_reconnect` line 205 | `except TimeoutError, OSError:` | `except (TimeoutError, OSError):` |

In Python 3, `except E1, E2:` catches `E1` and binds the exception
instance to the name `E2` (here, rebinding the built-in `OSError`).
The fix catches **both** `TimeoutError` and `OSError` as a tuple.

This code path is not exercised by the existing test suite (no test
triggers reconnection), so the bug has been latent.

**All other behavior is byte-for-byte identical** — same payloads sent,
same responses parsed, same errors raised, same futures resolved.

---

## 5. Data Flow

### 5.1 Connect Lifecycle

```
User calls transport.connect()
  │
  ▼
connect()
  ├─ _build_url(host, port) → "ws://localhost:6800/jsonrpc"
  ├─ ws_connect(url, open_timeout, close_timeout)
  │    ├─ Success → self._ws = WebSocket connection
  │    └─ Failure (TimeoutError|OSError) → raise Aria2ConnectionError
  ├─ self._should_reconnect = True
  └─ self._reader_task = asyncio.create_task(_reader_loop())
       │
       ▼
       _reader_loop() runs in background
         ├─ async for raw in self._ws: ...
         └─ on ConnectionClosed → _reconnect() (if should_reconnect)
```

### 5.2 Send Request Lifecycle

```
User calls transport.send_request("aria2.addUri", [params])
  │
  ▼
send_request()
  ├─ Guard: if not is_connected → raise Aria2ConnectionError
  ├─ self._request_id += 1          (e.g., 1 → 2)
  ├─ _build_payload(method, params, add_secret)
  │    ├─ add_secret=True  → _build(method, secret, params, request_id)
  │    └─ add_secret=False → _build_noauth(method, params, request_id)
  │    Returns: '{"jsonrpc":"2.0","method":"aria2.addUri",...}'
  │
  └─ _send_and_wait(payload, rid)
       ├─ future = create_future()
       ├─ _pending_mgr.register(rid, future)
       ├─ await self._ws.send(payload)        ← sent over wire
       ├─ await asyncio.wait_for(future, timeout)  ← blocks until resolved
       │    │
       │    │  ┌── _reader_loop receives response ──┐
       │    │  │  _dispatch(raw)                     │
       │    │  │    _try_notification → False        │
       │    │  │    _try_response(raw)                │
       │    │  │      future = _pending_mgr.get(rid) │
       │    │  │      result = _parse_response(raw)  │
       │    │  │      future.set_result(result)      │
       │    │  └─────────────────────────────────────┘
       │    │
       │    └─ Returns result
       └─ finally: _pending_mgr.pop(rid)  ← cleanup
```

### 5.3 Dispatch Lifecycle (Notification + Response)

```
_reader_loop receives raw message
  │
  ▼
_dispatch(raw)  [wrapped in suppress(Exception)]
  │
  ├─ _try_notification(raw)
  │    ├─ _parse_notification(raw)
  │    │    ├─ Has "id" field    → returns None  (this is a response)
  │    │    └─ No "id" field     → returns (method, params)
  │    │
  │    ├─ If notification:
  │    │    ├─ self._event_callback is set → call it with (method, params)
  │    │    └─ self._event_callback is None → silent no-op
  │    └─ Returns True (handled)
  │
  └─ _try_response(raw)  [only reached if not a notification]
       ├─ json.loads(raw) → {"jsonrpc": "2.0", "result": ..., "id": N}
       ├─ rid = obj.get("id")
       ├─ future = _pending_mgr.get(rid)
       │    ├─ None → return silently (stale/unknown response)
       │    └─ Future found:
       │         ├─ future.done() → return (already resolved by timeout/cancel)
       │         └─ not done:
       │              ├─ result = _parse_response(raw)
       │              │    ├─ Success → future.set_result(result)
       │              │    └─ Aria2RpcError → future.set_exception(e)
       │              └─ Any other Exception → future.set_exception(e)
```

### 5.4 Close Lifecycle

```
User calls transport.close()
  │
  ▼
close()
  ├─ self._should_reconnect = False   ← prevents reconnection on ConnectionClosed
  │
  ├─ _stop_reader()
  │    ├─ if self._reader_task:
  │    │    ├─ self._reader_task.cancel()
  │    │    ├─ await self._reader_task   (suppress CancelledError)
  │    │    └─ self._reader_task = None
  │    └─ if no task: no-op
  │
  ├─ _close_ws()
  │    ├─ if self._ws:
  │    │    ├─ await self._ws.close()
  │    │    └─ self._ws = None
  │    └─ if no ws: no-op
  │
  └─ _cancel_pending()
       └─ _pending_mgr.cancel_all()
            ├─ for fut in _pending.values():
            │    └─ if not fut.done(): fut.cancel()
            └─ _pending.clear()

Result: is_connected → False, all futures cancelled, all resources released.
```

### 5.5 Reconnection Flow

```
_reader_loop catches websockets.ConnectionClosed
  │
  ├─ self._should_reconnect == False → coroutine exits (clean close)
  │
  └─ self._should_reconnect == True → await self._reconnect()
       │
       ▼
_reconnect()
  ├─ delay = self._reconnect_delay   (e.g., 1.0s)
  │
  └─ while self._should_reconnect:
       ├─ await asyncio.sleep(delay)
       ├─ ws_connect(_build_url(...), ...)
       │    ├─ Success → self._ws = new connection
       │    │             await self._reader_loop()  ← recursive reader
       │    │             (may trigger nested _reconnect)
       │    │             return (success)
       │    │
       │    └─ (TimeoutError | OSError)  → FIXED SYNTAX
       │         delay = min(delay * 2, max_reconnect_delay)
       │         loop continues
       │
       └─ If _should_reconnect becomes False during sleep/wait
            → loop exits, coroutine returns
```

**Note on recursion:** In the current code, `_reconnect()` calls
`await self._reader_loop()` inline.  If that inner reader loop also
detects a drop and `_should_reconnect` is still `True`, it calls
`_reconnect()` again, creating a recursive call stack.  This is
pre-existing behavior and is not changed by the refactoring.  In
practice, the recursion depth equals the number of reconnection
cycles, which is bounded by the daemon uptime.

---

## 6. Test Strategy

### 6.1 Existing Test Suite Validation

All 11 existing tests in `tests/test_ws.py` **MUST pass without modification**.
The refactoring is pure structural extraction; no test changes are required.

| Test | What it validates | Key extractions exercised |
|---|---|---|
| `test_connect_and_request` | Full happy path: connect → request → result → close | `_build_url`, `connect`, `_build_payload`, `_send_and_wait`, `_stop_reader`, `_close_ws` |
| `test_rpc_error` | JSON-RPC error propagation | `_try_response` error path, `_parse_response` raising `Aria2RpcError` |
| `test_notification_dispatched` | Push notification → event callback | `_try_notification`, `_parse_notification` |
| `test_is_connected` | Connection state transitions | `is_connected` property, `connect`, `close` |
| `test_not_connected_raises` | Guard clause in `send_request` | `send_request` → `is_connected` check |
| `test_close_without_connect_is_safe` | Idempotent close when unconnected | `_stop_reader`, `_close_ws` guard conditions (`if self._ws:`, `if self._reader_task:`) |
| `test_connect_refused_raises` | Connection failure wrapping | `connect` → `except (TimeoutError, OSError)` |
| `test_send_request_no_secret` | `add_secret=False` path | `_build_payload` → `_build_noauth` branch |
| `test_stale_response_ignored` | Unknown response ID handling | `_try_response` → `future is None` guard |
| `test_close_cancels_pending` | Pending future cancellation on close | `_cancel_pending` → `_pending_mgr.cancel_all()`. **Also validates `t._pending` is a dict.** |
| `test_dispatch_error_swallowed` | Error containment — callback raises | `_dispatch` → `suppress(Exception)` → `_try_notification` |

### 6.2 Test Coverage of Edge Cases

| Edge case | Covered by test? | Notes |
|---|---|---|
| Connection refused | `test_connect_refused_raises` | ✅ |
| RPC error from daemon | `test_rpc_error` | ✅ |
| Notification dispatch | `test_notification_dispatched` | ✅ |
| No event callback set | `test_stale_response_ignored` (callback set but unused for response path) | ⚠️ Partial — no explicit test for `event_callback=None` |
| Stale/unknown response ID | `test_stale_response_ignored` | ✅ |
| Double close / unconnected close | `test_close_without_connect_is_safe` | ✅ |
| Pending cancellation on close | `test_close_cancels_pending` | ✅ |
| Callback raises exception | `test_dispatch_error_swallowed` | ✅ |
| `add_secret=False` | `test_send_request_no_secret` | ✅ |
| Send while disconnected | `test_not_connected_raises` | ✅ |
| Reconnection with backoff | **Not covered** | No existing test triggers reconnection |
| Concurrent requests | **Not covered** | Single-request test pattern |
| Malformed JSON in reader | **Not covered** | `suppress(Exception)` in `_dispatch` would catch it |
| `TimeoutError` during `ws_connect` | **Not covered** | Server fixture stays up during tests |

### 6.3 Test Compatibility Checklist

- [x] `from aria2.client.transport.ws import WebSocketTransport` resolves via `ws/__init__.py`
- [x] `WebSocketTransport("localhost", port, timeout=5.0)` constructs identically
- [x] `t.is_connected` returns `bool` — identical behavior
- [x] `await t.connect()` — identical behavior
- [x] `await t.send_request(method, params)` — identical behavior
- [x] `await t.send_request(method, params, add_secret=False)` — identical behavior
- [x] `await t.close()` — identical behavior
- [x] `t._pending[999] = fut` — works because `_pending` is a plain `dict`
- [x] `fut.cancelled()` after close — works because `cancel_all()` cancels incomplete futures

---

## 7. Edge Cases

### 7.1 Reconnection

**Scenario:** WebSocket connection drops cleanly (daemon restart).

**Flow:** `_reader_loop` catches `websockets.ConnectionClosed` → if
`_should_reconnect` is `True`, calls `_reconnect()` → sleeps with
exponential backoff → attempts `ws_connect()` → on success, sets
`self._ws` and calls `_reader_loop()` inline.

**Edge case — nested reconnections:** If the new connection also drops,
`_reader_loop` calls `_reconnect()` recursively.  Each level of
recursion doubles the delay independently.  This is pre-existing
behavior and not changed.

**Edge case — close during reconnection:** `close()` sets
`_should_reconnect = False` and calls `_close_ws()`.  If `_reconnect`
is sleeping, it wakes, checks `_should_reconnect`, sees `False`, and
exits the while loop.  If `_reconnect` is in the middle of
`ws_connect()`, the connection attempt may succeed briefly before
`_close_ws()` runs (harmless — connection closed immediately).

**Bug fix:** The `except TimeoutError, OSError:` syntax on the
reconnection error handler is corrected to `except (TimeoutError, OSError):`.
In Python 3, the original form catches only `TimeoutError` and
unintentionally rebinds the name `OSError` to the exception instance.
The fix properly catches both exception types as a tuple.

### 7.2 Malformed Messages

**Scenario:** The WebSocket receives a message that is not valid JSON.

**Flow:** `_reader_loop` wraps `_dispatch(raw)` in `suppress(Exception)`.
If `_try_notification` or `_try_response` raises `json.JSONDecodeError`,
the exception is swallowed and the reader loop continues.  No crash,
no disruption to pending requests.

### 7.3 Double Close (Idempotency)

**Scenario:** User calls `close()` twice in succession.

**Flow — first call:**
1. `_should_reconnect = False`
2. `_stop_reader()` — cancels task, awaits, sets to `None`
3. `_close_ws()` — closes WebSocket, sets to `None`
4. `_cancel_pending()` — cancels all futures, clears dict

**Flow — second call:**
1. `_should_reconnect = False` (already false, no-op)
2. `_stop_reader()` — `self._reader_task` is `None` → no-op
3. `_close_ws()` — `self._ws` is `None` → no-op
4. `_cancel_pending()` — `self._pending` is empty → no-op in cancel_all loop, clear() is no-op on empty dict

No exception raised. ✅

### 7.4 Close Without Connect

**Scenario:** User calls `close()` on a transport that was never connected.

**Flow:** All guards (`if self._reader_task:`, `if self._ws:`) evaluate to
`False`.  `_cancel_pending()` operates on an empty dict.  No exception. ✅

### 7.5 Concurrent Requests

**Scenario:** Multiple `send_request()` calls are in-flight simultaneously.

**Flow:** Each call:
1. Increments `self._request_id` (atomic in asyncio — single thread)
2. Creates a unique future
3. Registers it in `_pending[rid]`
4. Sends the payload and awaits the future

The `_pending` dict maps unique request IDs to futures.  When a response
arrives, `_try_response` matches by ID.  Two concurrent requests have
different IDs and cannot interfere.

**No change from current behavior.** The refactoring does not alter
concurrency guarantees.

### 7.6 `_reader_loop` Restart After Reconnect

**Scenario:** `_reconnect()` succeeds and calls `await self._reader_loop()`.

**Behavior:** `self._reader_task` still references the **old** task
(completed/cancelled).  The new reader runs as a coroutine, not as a
background task.  If `close()` is called while the reader is running
inline in `_reconnect()`, `_stop_reader()` cancels the old task
(no-op since it's done) but does **not** cancel the inline reader.

**Mitigation:** `close()` also calls `_close_ws()`, which closes the
WebSocket.  The next read in the inline `_reader_loop` will raise
`ConnectionClosed`, and since `_should_reconnect` is now `False`, the
reader exits.

**This is pre-existing behavior.**  The refactoring does not change
it.  A future improvement (out of scope) would restart the reader as a
new `asyncio.Task` after reconnection.

---

## 8. Rollout Plan

### 8.1 Creation Order

Files must be created in dependency order so that each file's imports
resolve at every step:

| Step | Action | File | Dependencies |
|---|---|---|---|
| **1** | Create | `transport/ws/__init__.py` | Requires `transport/ws/` dir to exist |
| **2** | Create | `transport/ws/_pending.py` | None (stdlib only) |
| **3** | Create | `transport/ws/transport.py` | Depends on `_pending.py` (imports `_PendingRequestManager`) |
| **4** | Delete | `transport/ws.py` | After step 3 is verified working |
| **5** | Verify | Run existing test suite | All 11 tests must pass |

**Step 4 details — safe deletion protocol:**
```bash
# Before deletion, confirm new package resolves:
python -c "from aria2.client.transport.ws import WebSocketTransport; print(WebSocketTransport)"

# Only then delete:
git rm packages/aria2-sdk/src/aria2/client/transport/ws.py

# Verify again:
python -c "from aria2.client.transport.ws import WebSocketTransport; print(WebSocketTransport)"
```

### 8.2 Verification Steps

After all files are in place and `ws.py` is deleted:

| # | Check | Command | Expected |
|---|---|---|---|
| 1 | Import works | `python -c "from aria2.client.transport.ws import WebSocketTransport"` | No error |
| 2 | `__all__` is correct | `python -c "from aria2.client.transport.ws import *; print(WebSocketTransport)"` | Class prints |
| 3 | All 11 tests pass | `pytest tests/test_ws.py -v` | 11 passed |
| 4 | Lint passes | `ruff check packages/aria2-sdk/src/aria2/client/transport/ws/` | No errors |
| 5 | Type check passes | `ty --strict packages/aria2-sdk/src/aria2/client/transport/ws/` | No errors |
| 6 | Function line limits | `awk '/^    (async )?def /{f=$0} /^$/{next} /^    /{c++} /^    (async )?def /{if(f) print f, c; f=$0; c=1}' transport.py` | All ≤20 |
| 7 | File line limits | `wc -l transport/ws/*.py` | All ≤200 |
| 8 | Full test suite | `pytest` | All pass, coverage ≥80% |

### 8.3 Cleanup

No cleanup needed — old `ws.py` is deleted via `git rm`.

If any verification fails:

```bash
# Rollback: restore ws.py from git, remove ws/ package
git checkout packages/aria2-sdk/src/aria2/client/transport/ws.py
git rm -r packages/aria2-sdk/src/aria2/client/transport/ws/
pytest tests/test_ws.py -v   # confirm original tests pass
```

### 8.4 Integration Verification

Beyond unit tests, verify that the `Aria2Client` integration still works:

```bash
python -c "
from aria2.client import Aria2Client
c = Aria2Client(host='localhost', port=6800, secret='test', enable_ws=True)
assert c._ws is not None
print('Aria2Client integration OK')
"
```

---

## Appendix A: Import Path Resolution

When `ws.py` becomes a `ws/` package, Python resolves the import
`from aria2.client.transport.ws import WebSocketTransport` as follows:

```
aria2.client.transport.ws
  → looks for transport/ws/__init__.py   (package takes priority over ws.py)
  → __init__.py executes:
      from aria2.client.transport.ws.transport import WebSocketTransport
      __all__ = ["WebSocketTransport"]
  → WebSocketTransport is bound in the ws package namespace
  → consumer receives WebSocketTransport
```

**Key detail:** In Python, a directory `ws/` with `__init__.py` takes
priority over a file `ws.py` when both exist.  This means we **must**
delete `ws.py` before the import resolution is complete; otherwise
Python may still pick up the monolithic file.

The deletion step (step 4) is therefore critical — the package is not
fully active until `ws.py` is removed.

## Appendix B: Design Decisions Log

| Decision | Rationale | Alternatives considered |
|---|---|---|
| Keep `_pending` as plain dict | Test `test_close_cancels_pending` does `t._pending[999] = fut` | Option B: manager owns dict, proxy `__getitem__` — more complex for no gain |
| `_build_url` as module-level helper | Pure function, no `self` needed; reused in `connect` and `_reconnect` | Inline URL in both methods — duplicates the format string |
| `_send_and_wait` creates its own future | Clean encapsulation — `send_request` doesn't worry about future lifecycle | Create future in `send_request` and pass it — leaks future management upward |
| `_cancel_pending` delegates to `_pending_mgr.cancel_all()` | Consistent use of pending manager throughout transport | Inline the loop — duplicates cancel logic between transport and manager |
| Inline `_reader_loop` after reconnect | Preserves existing behavior; avoids task lifecycle complexity | Create new `asyncio.Task` — changes behavior re: task tracking |
| Syntax fix in `_reconnect` only | Minimal change; bug is latent (not exercised by tests) | Fix in both `connect` and `_reconnect` — `connect` already has correct syntax |
| No new tests | Tests pass without modification → behavioral equivalence proven | Add tests for new helper methods — introduces coupling to private implementation |
| Single PR (no chain) | ~200 changed lines fits 400-line review budget | Multi-PR chain — unnecessary overhead |

## Appendix C: Code Location Map

For reviewers comparing old (`ws.py:LINE`) to new (`ws/transport.py:LINE`):

| Old `ws.py` | Content | New `transport.py` |
|---|---|---|
| Lines 1-20 | Imports + docstring | Imports + docstring + `_build_url` |
| Lines 22-24 | `class WebSocketTransport(Transport):` | Same |
| Lines 27-47 | `__init__` | `__init__` (~lines 45-65) |
| Lines 51-53 | `is_connected` | `is_connected` |
| Lines 55-72 | `connect` | `connect` |
| Lines 74-106 | `send_request` | `send_request` (delegates to `_build_payload` + `_send_and_wait`) |
| — | _(new)_ | `_build_payload` |
| — | _(new)_ | `_send_and_wait` |
| Lines 108-130 | `close` | `close` (delegates to `_stop_reader` + `_close_ws` + `_cancel_pending`) |
| — | _(new)_ | `_stop_reader` |
| — | _(new)_ | `_close_ws` |
| — | _(new)_ | `_cancel_pending` |
| Lines 134-148 | `_reader_loop` | `_reader_loop` |
| Lines 150-188 | `_dispatch` | `_dispatch` (delegates to `_try_notification` + `_try_response`) |
| — | _(new)_ | `_try_notification` |
| — | _(new)_ | `_try_response` |
| Lines 190-207 | `_reconnect` | `_reconnect` (syntax fix, uses `_build_url`) |
| — | _(new in `_pending.py`)_ | `_PendingRequestManager` class |
