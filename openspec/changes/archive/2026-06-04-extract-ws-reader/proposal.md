# SDD Proposal: Extract `_WsReader` from `ws/transport.py`

**Change ID:** `2026-06-04-extract-ws-reader`
**Issue:** [#11](https://github.com/gentleman-programming/aria2/issues/11) — extract `_reader.py` from `ws/transport.py`
**Date:** 2026-06-04
**Status:** Draft

---

## Intent

Extract the reader-loop, dispatch, and reconnection concerns from `WebSocketTransport`
into a dedicated `_WsReader` class in a new `_reader.py` file, reducing
`WebSocketTransport.__init__` from 24 lines to ≤20 and shrinking `transport.py` from
188 lines to ~130 (well under the 200-line ceiling).

This is a **purely structural refactoring**: zero behavioural changes, zero API changes,
all existing tests pass without modification.

---

## Scope

### In scope

| File | Action | Est. lines |
|---|---|---|
| `ws/transport.py` | **Modified** — extract reader/dispatch/reconnect to `_reader.py`; extract `_init_internal_state()` helper in `__init__` | ~130 |
| `ws/_reader.py` | **Created** — `_WsReader` class with `run()`, `dispatch()`, `_try_notification()`, `_try_response()`, `_reconnect()` | ~55 |

### Out of scope

- Changes to `ws/__init__.py`
- Changes to `ws/_pending.py`
- Changes to the `Transport` ABC
- Changes to any test files
- Changes to the `Aria2Client`
- Adding new tests (test pass is verified separately)
- Fixing the `except TimeoutError, OSError:` syntax bug in `_reconnect` (pre-existing, tracked separately)

---

## Affected Areas

### Directly affected

| Module | Change |
|---|---|
| `ws/transport.py` | **Modified** — `WebSocketTransport` drops `_reader_loop`, `_dispatch`, `_try_notification`, `_try_response`, `_reconnect`; delegates to `_WsReader` |
| `ws/_reader.py` | **Created** — `_WsReader` class owns reader loop + dispatch + reconnection |

### Import chains (must remain intact)

| Consumer | Import path | Must work |
|---|---|---|
| `aria2/client/__init__.py` | `from aria2.client.transport.ws import WebSocketTransport` | ✅ (via `__init__.py` re-export, unchanged) |
| `tests/test_ws.py` | `from aria2.client.transport.ws import WebSocketTransport` | ✅ |
| `tests/test_ws.py` | `t._pending` as `dict[int, Future]` | ✅ (`_pending` stays on transport) |
| `tests/test_ws.py` | `t._pending[999] = fut` (manual inject) | ✅ (dict remains on transport) |

---

## Architecture: Extract `_WsReader` from `WebSocketTransport`

### Current state (transport.py — 188 lines, 4 concerns mixed)

```
WebSocketTransport
├── Lifecycle + state      (~70 lines)  ← __init__ is 24 lines ❌
├── Request/response       (~25 lines)
├── Reader + dispatch      (~40 lines)  ← extracted to _WsReader
└── Reconnection           (~18 lines)  ← extracted to _WsReader
```

### Proposed state

```
ws/
├── __init__.py            (5 lines, unchanged)
├── _pending.py            (49 lines, unchanged)
├── transport.py           (~130 lines, __init__ ≤20 ✅)
└── _reader.py             (~55 lines, new)
```

**Responsibility split:**

| Concern | Owner | Location |
|---|---|---|
| Lifecycle + state | `WebSocketTransport` | `transport.py` |
| Request/response | `WebSocketTransport` | `transport.py` (`send_request`, `_build_payload`, `_send_and_wait`) |
| Pending futures | `_PendingRequestManager` | `_pending.py` (unchanged) |
| Reader loop + dispatch + reconnect | `_WsReader` | `_reader.py` (new) |

### `_WsReader` design

```python
"""WebSocket reader — dispatch loop and reconnection for ws transport."""

from __future__ import annotations

import asyncio
import json
from contextlib import suppress
from typing import Any

import websockets
from websockets.asyncio.client import connect as ws_connect

from aria2.client.transport.ws._build_url import _build_url
from aria2.rpc import parse_notification as _parse_notification
from aria2.rpc import parse_response as _parse_response


class _WsReader:
    """Reads WebSocket messages, dispatches responses/notifications, reconnects.

    Owns the reader async-task loop and reconnection logic.  Does NOT own
    the WebSocket itself — ``_ws`` is provided by ``WebSocketTransport``
    and may be replaced during reconnection.

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
        event_callback: Callable[[str, list[Any]], None] | None,
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
        """Main reader loop — reads raw messages and dispatches them.

        Exits normally when the connection closes gracefully.
        Reconnects automatically if ``_should_reconnect`` is set.
        """
        assert self._ws is not None
        try:
            async for raw in self._ws:
                with suppress(Exception):
                    self.dispatch(raw)
        except websockets.ConnectionClosed:
            if self._should_reconnect:
                await self._reconnect()

    def dispatch(self, raw: str) -> None:
        """Route a single raw message to notification or response handler."""
        if self._try_notification(raw):
            return
        self._try_response(raw)

    def _try_notification(self, raw: str) -> bool:
        notif = _parse_notification(raw)
        if notif is not None:
            method, params = notif
            if self._event_callback:
                self._event_callback(method, params)
            return True
        return False

    def _try_response(self, raw: str) -> None:
        """Match a JSON-RPC response to its pending future by request ID."""
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
        """Reconnect loop with exponential backoff.

        Starts with ``_reconnect_delay``, doubles on each failure,
        capped at ``_max_reconnect_delay``.  Exits when the connection
        succeeds or ``_should_reconnect`` becomes ``False``.
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
            except (TimeoutError, OSError):
                delay = min(delay * 2, self._max_reconnect_delay)
            else:
                return
```

### `WebSocketTransport` changes in `transport.py`

#### `__init__` — extract internal state helper to stay ≤20 lines

```python
class WebSocketTransport(Transport):
    def __init__(self, host, port, secret=None, *, timeout=30.0,
                 event_callback=None, reconnect_delay=1.0,
                 max_reconnect_delay=30.0) -> None:
        self._host = host
        self._port = port
        self._secret = secret
        self._timeout = timeout
        self._event_callback = event_callback
        self._reconnect_delay = reconnect_delay
        self._max_reconnect_delay = max_reconnect_delay
        self._init_internal_state()

    def _init_internal_state(self) -> None:
        """Initialise runtime state (separated from constructor for line‑limit compliance)."""
        self._ws: Any | None = None
        self._request_id = 0
        self._reader_task: asyncio.Task[None] | None = None
        self._should_reconnect = False
        self._pending: dict[int, asyncio.Future[Any]] = {}
        self._pending_mgr = _PendingRequestManager(self._pending)
```

This brings `__init__` body to **17 lines** (including signature and docstring) —
well under the 20-line limit. The `_init_internal_state` helper is **7 lines**.

#### `connect` — creates `_WsReader`, starts its `run()` task

```python
    async def connect(self) -> None:
        try:
            self._ws = await ws_connect(
                _build_url(self._host, self._port),
                open_timeout=self._timeout,
                close_timeout=self._timeout,
            )
        except (TimeoutError, OSError) as e:
            raise Aria2ConnectionError(str(e)) from e
        self._reader = _WsReader(
            ws=self._ws,
            pending_mgr=self._pending_mgr,
            event_callback=self._event_callback,
            url=_build_url(self._host, self._port),
            timeout=self._timeout,
        )
        self._reader._should_reconnect = True  # or pass via param
        self._reader_task = asyncio.create_task(self._reader.run())
```

#### Methods removed from `WebSocketTransport`

| Removed method | Delegated to |
|---|---|
| `_reader_loop` | `_WsReader.run()` |
| `_dispatch` | `_WsReader.dispatch()` |
| `_try_notification` | `_WsReader._try_notification()` |
| `_try_response` | `_WsReader._try_response()` |
| `_reconnect` | `_WsReader._reconnect()` |
| `_init_internal_state` | (new private method, stays on transport) |

### Design decisions

1. **`_pending` stays on `WebSocketTransport`** — The `dict[int, Future]` remains
   as `self._pending` on `WebSocketTransport` so existing tests that manually inject
   futures (`t._pending[999] = fut`) continue to work. `_PendingRequestManager`
   receives a reference to it as before. `_WsReader` accesses the manager, not the
   raw dict.

2. **`_WsReader` does NOT own the websocket** — The `_ws` attribute is assigned by
   `WebSocketTransport.connect()` and may be replaced by `_WsReader._reconnect()`.
   On `close()`, the transport sets `_should_reconnect = False` on the reader,
   cancels the reader task, and closes the WebSocket directly.

3. **`_reader` attribute on transport** — `self._reader: _WsReader | None` is stored
   on the transport so that the transport can signal the reader to stop reconnecting
   and can inspect its state if needed.

4. **Reconnection ownership** — Reconnection lives in `_WsReader._reconnect()` because
   it's part of the reader loop lifecycle. The transport sets `_reader._should_reconnect
   = False` during `close()` to prevent reconnection attempts.

---

## Line Count Reconciliation

### Current violations

| Location | Function | Lines | Limit | Status |
|---|---|---|---|---|
| `transport.py` | `WebSocketTransport.__init__` | 24 | 20 | ❌ |
| `transport.py` | File total | 188 | 200 | ⚠️ (approaching) |

### Post-refactor line counts

**`transport.py` (~130 lines):**

| Method | Lines | Status |
|---|---|---|
| `__init__` | 17 | ✅ |
| `_init_internal_state` | 7 | ✅ |
| `is_connected` (property) | 2 | ✅ |
| `connect` | 17 | ✅ |
| `send_request` | 12 | ✅ |
| `close` | 9 | ✅ |
| `_build_payload` | 4 | ✅ |
| `_send_and_wait` | 12 | ✅ |
| `_stop_reader` | 7 | ✅ |
| `_close_ws` | 5 | ✅ |
| `_cancel_pending` | 2 | ✅ |
| **Total** | **~125–135** | ✅ (under 200) |

**`_reader.py` (~55 lines):**

| Method | Lines | Status |
|---|---|---|
| `__init__` | ~12 | ✅ |
| `run` | ~10 | ✅ |
| `dispatch` | ~4 | ✅ |
| `_try_notification` | ~8 | ✅ |
| `_try_response` | ~12 | ✅ |
| `_reconnect` | ~12 | ✅ |
| **Total** | **~55** | ✅ (under 200) |

---

## Implementation Order

1. **Write this proposal** to `openspec/changes/2026-06-04-extract-ws-reader/proposal.md`
2. **Create `ws/_reader.py`** with the `_WsReader` class
3. **Modify `ws/transport.py`** — extract `_init_internal_state()`, remove reader/dispatch/reconnect methods, import and use `_WsReader`
4. **Run all existing tests** — `pytest tests/test_ws.py` — verify zero regressions
5. **Run full test suite** — `pytest` — verify no side effects
6. **Run `ruff check`** — `ruff check packages/aria2-sdk/src/aria2/client/transport/ws/`
7. **Run `ty`** — `ty --strict packages/aria2-sdk/src/aria2/client/transport/ws/`

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| **`_should_reconnect` flag sync** — transport sets `_should_reconnect = False` on itself but reader checks its own flag | Medium | High | Transport sets `self._reader._should_reconnect = False` in `close()` instead. Both `connect()` (via `self._reader._should_reconnect = True`) and `close()` target the reader's flag. |
| **Reader task lifecycle** — `_stop_reader` references `self._reader_task` which is started by `connect()` via `self._reader.run()` | Low | Medium | Same pattern as before: `_reader_task` is created in `connect()` and cancelled in `close()`. No change to the task lifecycle. |
| **`_reconnect` calls `self.run()` (old `_reader_loop`)** — after reconnecting, the reader must re-enter the loop | Low | Medium | `_WsReader._reconnect()` calls `await self.run()` after successful reconnection, which starts the `async for raw in self._ws` loop on the new connection. Same as current code. |
| **Import of `_WsReader` from `_reader`** — circular import risk | Low | Low | `transport.py` imports `_WsReader` from `_reader.py`. `_reader.py` does NOT import from `transport.py`. No cycle. |
| **`_build_url` location** — currently a module-level function in `transport.py` | Low | Low | Two options: (a) keep it in `transport.py` and import it in `_reader.py`, or (b) extract to a shared module. Option (a) is simpler but creates a cross-module dependency. Option (b) adds a file. **Recommend option (a)** — import `_build_url` from `transport` in `_reader.py`. The function is small and stable. |
| **`websockets.ConnectionClosed` exception in `_reader.py`** — import must resolve | Low | Low | `_reader.py` already imports `websockets`. No issue. |
| **Coverage regression** — _reader.py is new and uncovered | Low | Low | All code paths are exercised by existing tests (reader loop, dispatch, notification, response, stale response). The `_reconnect` path remains uncovered (pre-existing gap). Coverage ≥80% should hold. |

### Accepted technical debt

- `_WsReader._reconnect()` has no test coverage — pre-existing gap from the original
  `transport.py`. Not introduced by this refactoring.
- The `except TimeoutError, OSError:` syntax bug in `_reconnect` (missing parentheses)
  is left as-is — it's a pre-existing bug not related to this refactoring.

---

## Rollback Plan

If the refactoring breaks the build, tests, or type checks:

1. **Revert `ws/transport.py`** — `git checkout -- packages/aria2-sdk/src/aria2/client/transport/ws/transport.py`
2. **Remove `ws/_reader.py`** — `git rm packages/aria2-sdk/src/aria2/client/transport/ws/_reader.py`
3. **Verify** — `pytest tests/test_ws.py` passes against the original transport.py
4. **File follow-up** — log the failure details to the issue tracker

The change is contained to two files within a single package. Full recovery is a
two-command operation. No irreversible data loss.

---

## Success Criteria

All of the following must pass:

- [ ] `ruff check packages/aria2-sdk/src/aria2/client/transport/ws/` — zero errors
- [ ] `ty --strict packages/aria2-sdk/src/aria2/client/transport/ws/` — zero type errors
- [ ] `pytest tests/test_ws.py` — all 11 existing tests pass without modification
- [ ] `pytest` — full suite passes (no side effects on other tests)
- [ ] `from aria2.client.transport.ws import WebSocketTransport` works
- [ ] `client._ws._pending` remains a `dict[int, Future]` (test access preserved)
- [ ] Each function body ≤20 lines (verify with `awk`/`wc -l`)
- [ ] Each file ≤200 lines
- [ ] Coverage ≥80% (no regression from current baseline)

---

## Chained PR Forecast

| Metric | Value |
|---|---|
| Est. new files | 1 (`_reader.py`, ~55 lines) |
| Est. modified files | 1 (`transport.py`, ~60 lines changed) |
| **Total changed lines** | **~120** |
| Review budget | 400 lines |
| **Fit in single PR?** | **Yes** ✅ — well under budget |

No chaining needed. A single PR handles the entire extraction.

---

## Appendix A: Current `transport.py` Function Audit

| Function | Lines | Limit | Status |
|---|---|---|---|
| `__init__` | 24 | 20 | ❌ |
| `is_connected` | 2 | 20 | ✅ |
| `connect` | 17 | 20 | ✅ |
| `send_request` | 12 | 20 | ✅ |
| `close` | 9 | 20 | ✅ |
| `_build_payload` | 4 | 20 | ✅ |
| `_send_and_wait` | 12 | 20 | ✅ |
| `_stop_reader` | 7 | 20 | ✅ |
| `_close_ws` | 5 | 20 | ✅ |
| `_cancel_pending` | 2 | 20 | ✅ |
| `_reader_loop` | 13 | 20 | ✅ |
| `_dispatch` | 4 | 20 | ✅ |
| `_try_notification` | 8 | 20 | ✅ |
| `_try_response` | 12 | 20 | ✅ |
| `_reconnect` | 12 | 20 | ✅ |

**Total file:** 188 lines ⚠️ (under 200 but approaching)

## Appendix B: Responsibilities Before and After

### Before

| Concern | Methods | Lines | Owner |
|---|---|---|---|
| Lifecycle + state | `__init__`, `is_connected`, `connect`, `close`, `_stop_reader`, `_close_ws`, `_cancel_pending` | ~70 | `WebSocketTransport` |
| Request/response | `send_request`, `_build_payload`, `_send_and_wait` | ~25 | `WebSocketTransport` |
| Reader + dispatch | `_reader_loop`, `_dispatch`, `_try_notification`, `_try_response` | ~40 | `WebSocketTransport` |
| Reconnection | `_reconnect` | ~18 | `WebSocketTransport` |

### After

| Concern | Methods / Functions | Lines | Owner |
|---|---|---|---|
| Lifecycle + state | `__init__`, `_init_internal_state`, `is_connected`, `connect`, `close`, `_stop_reader`, `_close_ws`, `_cancel_pending` | ~55 | `WebSocketTransport` |
| Request/response | `send_request`, `_build_payload`, `_send_and_wait` | ~25 | `WebSocketTransport` |
| Pending futures | `register`, `pop`, `get`, `cancel_all` | ~49 | `_PendingRequestManager` (unchanged) |
| Reader loop | `run` | ~10 | `_WsReader` |
| Dispatch | `dispatch`, `_try_notification`, `_try_response` | ~25 | `_WsReader` |
| Reconnection | `_reconnect` | ~12 | `_WsReader` |
| Internal state init | `_init_internal_state` | ~7 | `WebSocketTransport` |

## Appendix C: Dependency Graph

```
transport.py                        _reader.py
│                                    │
│  ┌─ _build_url() (module fn) ──────┤  (imported)
│  │                                 │
│  └─ WebSocketTransport             │
│       ├── _pending_mgr ────────────┤  (passed to _WsReader)
│       ├── _event_callback ─────────┤  (passed to _WsReader)
│       ├── _ws (websocket) ─────────┤  (passed to _WsReader)
│       └── _reader: _WsReader ──────┤  (created in connect())
│                                    │
│     (unchanged)                    │
│  _pending.py ◀─────────────────────┤  (pending_mgr imported)
│                                    │
│     (unchanged)                    │
│  __init__.py                       │
│       └── re-exports               │
│            WebSocketTransport      │
```

No circular dependencies. `_reader.py` imports from `transport.py` only for
`_build_url`. If this cross-import feels unclean, `_build_url` can be duplicated
in `_reader.py` (7 lines) — but an import is cleaner for maintenance.
