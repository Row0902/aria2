# SDD Tasks: Extract `_WsReader` from `ws/transport.py`

**Change ID:** `2026-06-04-extract-ws-reader`
**Date:** 2026-06-04
**Status:** Tasks

---

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~120 (~55 new + ~65 modified/deleted) |
| 400-line budget risk | Low |
| Chained PRs recommended | No |
| Suggested split | single PR |
| Delivery strategy | single-pr |
| Chain strategy | pending |

---

Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: pending
400-line budget risk: Low

---

## TDD Alignment

This is a pure structural refactoring — zero behavioral changes, zero API
changes, all 11 existing tests pass without modification. The tests serve
as the GREEN safety net. Every task is a REFACTOR step verified to stay
GREEN before proceeding.

| Phase | Step | TDD Role |
|-------|------|----------|
| Task 1 | Verify current state | **GREEN baseline** — prove all tests pass now |
| Task 2 | Create `_reader.py` | **REFACTOR** — add new module (no wiring yet) |
| Task 3 | Extract `_init_internal_state()` | **REFACTOR** — smallest safe structural change |
| Task 4 | Wire `_WsReader` into transport | **REFACTOR** — swap implementation, tests guard |
| Task 5 | Remove dead methods/imports | **REFACTOR** — clean up, tests guard |
| Task 6 | Full verification | **GREEN confirmation** — structural + behavioral |

---

## Task 1 — GREEN Baseline: Verify current state

**Goal:** Confirm all tests, lint, and type checks pass before any changes.

**File:** `tests/test_ws.py`

**Steps:**

1. Run the WebSocket test suite:
   ```bash
   cd /home/Row/development/workspaces/python/aria2
   uv run pytest tests/test_ws.py -v
   ```
   Expected: all 11 tests pass.

2. Run lint on the target package:
   ```bash
   uv run ruff check packages/aria2-sdk/src/aria2/client/transport/ws/
   ```
   Expected: zero errors.

3. Run type checker:
   ```bash
   uv run ty --strict packages/aria2-sdk/src/aria2/client/transport/ws/
   ```
   Expected: zero errors.

4. Run the full test suite to catch any pre-existing side effects:
   ```bash
   uv run pytest
   ```
   Expected: full suite passes (or same failure count as before).

**Verify:** All checks pass. If any fail, stop and report — do not proceed.

**Artifacts:** None (verification only).

---

## Task 2 — Create `ws/_reader.py` with `_WsReader` class

**Goal:** Create the new module with the complete `_WsReader` class. At this
stage the module is standalone — not yet imported or wired by `transport.py`.

**Files created:**

- `packages/aria2-sdk/src/aria2/client/transport/ws/_reader.py` (~55 lines)

**Class:** `_WsReader`

**Constructor parameters (per design §3.1):**

| Param | Type | Purpose |
|-------|------|---------|
| `ws` | `Any` | Active `websockets` client connection |
| `pending_mgr` | `_PendingRequestManager` | Shared pending-request manager from transport |
| `event_callback` | `Callable[[str, list[Any]], None] \| None` | Optional notification dispatcher |
| `url` | `str` | Pre-built WebSocket endpoint URL (`ws://host:port/jsonrpc`) |
| `timeout` | `float` | Connection timeout in seconds |

**Methods to implement (exactly as specified in design §3.1):**

| Method | Signature | Body lines | Behavior |
|--------|-----------|------------|----------|
| `__init__` | `(self, ws, pending_mgr, event_callback, url, timeout)` | 9 | Store params; init `_should_reconnect = False`, `_reconnect_delay = 1.0`, `_max_reconnect_delay = 30.0` |
| `run` | `async (self) -> None` | 7 | `async for raw in self._ws` → `with suppress(Exception): self._dispatch(raw)`; on `websockets.ConnectionClosed` → `if self._should_reconnect: await self._reconnect()` |
| `_dispatch` | `(self, raw: str) -> None` | 4 | Route to `_try_notification` or `_try_response` |
| `_try_notification` | `(self, raw: str) -> bool` | 8 | Parse notification → invoke callback → return `True`/`False` |
| `_try_response` | `(self, raw: str) -> None` | 11 | `json.loads(raw)` → lookup future by `id` → resolve or set exception; guard `future.done()` |
| `_reconnect` | `async (self) -> None` | 11 | Exponential backoff loop: sleep, `ws_connect(url, timeout)`, on success → `await self.run()`; doubles delay on failure, capped at `_max_reconnect_delay` |
| `stop` | `(self) -> None` | 2 | Set `self._should_reconnect = False` |

**Imports needed in `_reader.py`:**

```python
from __future__ import annotations

import asyncio
import json
from contextlib import suppress
from typing import Any

import websockets
from websockets.asyncio.client import connect as ws_connect

from aria2.client.transport.ws._pending import _PendingRequestManager
from aria2.rpc import parse_notification as _parse_notification
from aria2.rpc import parse_response as _parse_response
```

**Key design decisions to follow:**

1. **No import from `transport.py`.** `_WsReader` receives a pre-built `url: str`,
   not `host` + `port`. The URL is built once in `WebSocketTransport.connect()`.

2. **`_should_reconnect` is on the reader instance.** `connect()` sets it to
   `True` via `self._reader._should_reconnect = True`. `close()` sets it to
   `False` via `self._reader.stop()`.

3. **`_reconnect_delay` and `_max_reconnect_delay` are hardcoded** to `1.0`
   and `30.0`. The transport's constructor parameters for these are preserved
   but not injected into the reader.

4. **`except TimeoutError, OSError:` syntax** — pre-existing bug in the current
   `_reconnect()` method. Leave as-is in `_reader.py` (tracked separately,
   not introduced by this refactor).

5. **`stop()` is idempotent** — safe to call multiple times.

**Verify:**

```bash
# Import check — module loads without error
uv run python -c "from aria2.client.transport.ws._reader import _WsReader; print('OK')"

# ruff on new file only
uv run ruff check packages/aria2-sdk/src/aria2/client/transport/ws/_reader.py
```

**Artifacts:** `ws/_reader.py` (new file).

---

## Task 3 — Extract `_init_internal_state()` from `__init__`

**Goal:** Extract mutable state initialization from `WebSocketTransport.__init__`
into a private `_init_internal_state()` method. This keeps the constructor body
under 20 lines. Add the `_reader` attribute placeholder.

**File:** `packages/aria2-sdk/src/aria2/client/transport/ws/transport.py`

**Changes:**

1. Move these 7 assignment lines from `__init__` body to a new method:

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

2. Replace those 7 lines in `__init__` with a single call:
   ```python
   self._init_internal_state()
   ```

3. The `__init__` body is now: 8 constructor-argument assignments + 1 method
   call = 9 body lines ✅ (well under 20).

**Note:** `self._reader: _WsReader | None = None` is added now but the
`_WsReader` import is NOT added yet — that happens in Task 4. For now,
use a `# type: ignore[annotation-unchecked]` comment on the annotation,
or use `Any` temporarily. The actual import will be added in Task 4.

**Actually:** Since the type annotation `_WsReader | None` requires the import,
and we want each task to be independently verifiable, use `Any` for `_reader`
in this task:

```python
self._reader: Any = None  # Will be _WsReader | None after Task 4
```

The `from __future__ import annotations` is already present in transport.py,
so string-based annotations would work, but the symbol must still be resolvable
at type-check time. For this intermediate step, `Any` is the safe choice.

**Verify:**

```bash
# Test suite: all 11 tests still pass
uv run pytest tests/test_ws.py -v

# Constructor body line count check
uv run python -c "
import ast
with open('packages/aria2-sdk/src/aria2/client/transport/ws/transport.py') as f:
    tree = ast.parse(f.read())
for node in ast.walk(tree):
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        if node.name == '__init__':
            # Count non-docstring body lines
            body = [n for n in node.body if not (isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant) and isinstance(n.value.value, str))]
            print(f'__init__ body lines: {len(body)}')
        if node.name == '_init_internal_state':
            body = [n for n in node.body if not (isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant) and isinstance(n.value.value, str))]
            print(f'_init_internal_state body lines: {len(body)}')
"
# Expected: __init__ body lines: 9, _init_internal_state body lines: 7

# ruff/ty still clean
uv run ruff check packages/aria2-sdk/src/aria2/client/transport/ws/transport.py
uv run ty --strict packages/aria2-sdk/src/aria2/client/transport/ws/transport.py
```

**Artifacts:** `transport.py` modified (`__init__` shortened, `_init_internal_state` added).

---

## Task 4 — Wire `_WsReader` into `connect()` and `close()`

**Goal:** Import `_WsReader`, create it in `connect()`, delegate stop to it in
`close()`. The old reader-loop/dispatch/reconnect methods still exist on the
transport at this stage but are dead code (removed in Task 5).

**File:** `packages/aria2-sdk/src/aria2/client/transport/ws/transport.py`

**Changes:**

### 4a. Add import

```python
from aria2.client.transport.ws._reader import _WsReader
```

### 4b. Fix `_init_internal_state` annotation

Change `self._reader: Any = None` to:
```python
self._reader: _WsReader | None = None
```

(Now that the import is present, the annotation resolves.)

### 4c. Rewrite `connect()`

Current `connect()` body:

```python
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
```

Replace with:

```python
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

Key changes:
- URL pre-built once into `url` variable
- `_WsReader` instantiated with pre-built URL, NOT host+port
- `_reader._should_reconnect = True` set on the reader instance
- Task wraps `self._reader.run()` instead of `self._reader_loop()`

### 4d. Rewrite `close()`

Current `close()` body:

```python
self._should_reconnect = False
await self._stop_reader()
await self._close_ws()
self._cancel_pending()
```

Replace with:

```python
if self._reader is not None:
    self._reader.stop()
await self._stop_reader()
await self._close_ws()
self._cancel_pending()
```

Key changes:
- `self._should_reconnect = False` replaced by `self._reader.stop()`
- `if self._reader is not None:` guard added for pre-connect close safety
- `_stop_reader`, `_close_ws`, `_cancel_pending` unchanged

**Note on `_should_reconnect` on transport:** After this change,
`self._should_reconnect` on the transport is initialized to `False` in
`_init_internal_state` but never written or read. It becomes dead code.
The design (§3.2.3) keeps it in `_init_internal_state` for safety;
removal is deferred to a future cleanup pass.

**Dead-but-still-present methods after this task:** `_reader_loop`, `_dispatch`,
`_try_notification`, `_try_response`, `_reconnect` — these still exist on the
transport but are no longer called. Removed in Task 5.

**Verify:**

```bash
# All 11 WebSocket tests pass
uv run pytest tests/test_ws.py -v

# Specific test checks:
# test_close_without_connect_is_safe — guard `if self._reader is not None` tested
# test_close_cancels_pending — _pending dict still on transport, _cancel_pending unchanged
# test_connect_and_request — full lifecycle connect → send → close
# test_notification_dispatched — notification dispatch through _WsReader
# test_stale_response_ignored — response matching through _WsReader
# test_dispatch_error_swallowed — error suppression in _WsReader.run()

# ruff/ty
uv run ruff check packages/aria2-sdk/src/aria2/client/transport/ws/
uv run ty --strict packages/aria2-sdk/src/aria2/client/transport/ws/
```

**Expected ruff findings:** May warn about unused imports (`json`, `suppress`,
`_parse_notification`, `_parse_response`, `websockets`) and unused methods
(`_reader_loop`, `_dispatch`, `_try_notification`, `_try_response`, `_reconnect`).
These are acceptable at this intermediate stage — cleaned up in Task 5.

**Artifacts:** `transport.py` modified (import added, `connect()` and `close()` rewritten).

---

## Task 5 — Remove dead methods and unused imports

**Goal:** Delete the 5 methods that have moved to `_WsReader` and clean up
imports that are no longer needed in `transport.py`.

**File:** `packages/aria2-sdk/src/aria2/client/transport/ws/transport.py`

### 5a. Remove dead methods

Delete these methods from `WebSocketTransport`:

1. `_reader_loop` (13 lines)
2. `_dispatch` (4 lines)
3. `_try_notification` (8 lines)
4. `_try_response` (12 lines)
5. `_reconnect` (12 lines)

**Total removed:** ~49 lines of method bodies + signatures + docstrings.

### 5b. Remove unused imports

Remove these from the import block:

| Import removed | Reason |
|---|---|
| `import json` | Only used by `_try_response` → moved to `_reader.py` |
| `from contextlib import suppress` | Only used by `_reader_loop` → moved to `_reader.py` |
| `import websockets` | Only used for `websockets.ConnectionClosed` in `_reader_loop` → moved to `_reader.py` |
| `from aria2.rpc import parse_notification as _parse_notification` | Only used by `_try_notification` → moved to `_reader.py` |
| `from aria2.rpc import parse_response as _parse_response` | Only used by `_try_response` → moved to `_reader.py` |

**Imports that STAY in `transport.py`:**

| Import kept | Reason |
|---|---|
| `import asyncio` | `asyncio.Task`, `create_task`, `get_event_loop`, `wait_for`, `CancelledError` |
| `from collections.abc import Callable` | `__init__` parameter annotation |
| `from typing import Any` | Type annotations throughout |
| `from websockets.asyncio.client import connect as ws_connect` | `connect()` uses it |
| `from aria2.client.transport import Transport` | Base class |
| `from aria2.client.transport.ws._pending import _PendingRequestManager` | `_init_internal_state` uses it |
| `from aria2.errors import Aria2ConnectionError` | Error raising |
| `from aria2.rpc import build_request as _build_noauth` | `_build_payload` |
| `from aria2.rpc import build_request_with_secret as _build` | `_build_payload` |
| `from aria2.client.transport.ws._reader import _WsReader` | Added in Task 4 |

**Net change:** –5 imports removed, transport.py ~115 lines total (well under 200).

**Verify:**

```bash
# All 11 WebSocket tests pass
uv run pytest tests/test_ws.py -v

# ruff: zero errors (no more unused-import or unused-method warnings)
uv run ruff check packages/aria2-sdk/src/aria2/client/transport/ws/

# ty: zero errors
uv run ty --strict packages/aria2-sdk/src/aria2/client/transport/ws/
```

**Artifacts:** `transport.py` modified (dead methods + unused imports removed).

---

## Task 6 — Full structural and behavioral verification

**Goal:** Comprehensive verification that the refactoring meets all structural
policies and preserves all behavior.

**Files under verification:** All files in `packages/aria2-sdk/src/aria2/client/transport/ws/`

### 6a. Lint and type check

```bash
uv run ruff check packages/aria2-sdk/src/aria2/client/transport/ws/
uv run ty --strict packages/aria2-sdk/src/aria2/client/transport/ws/
```

Expected: zero errors on both.

### 6b. WebSocket test suite

```bash
uv run pytest tests/test_ws.py -v
```

Expected: all 11 tests pass without modification.

Verify each test exercises the correct refactored code path:

| Test | Assertion | Refactored path verified |
|------|-----------|--------------------------|
| `test_connect_and_request` | `result == "mock-gid-abc"` | `_WsReader.run()` → `_dispatch` → `_try_response` → future resolved |
| `test_rpc_error` | `Aria2RpcError` with `code=-1` | `_try_response` → `future.set_exception()` |
| `test_notification_dispatched` | Event received + result | `_try_notification` → callback |
| `test_is_connected` | True after connect, False after close | Property unchanged |
| `test_not_connected_raises` | `Aria2ConnectionError` | Guard unchanged |
| `test_close_without_connect_is_safe` | No exception | `if self._reader is not None` guard |
| `test_connect_refused_raises` | `Aria2ConnectionError` | `connect()` exception handling unchanged |
| `test_send_request_no_secret` | Result, no token in payload | Payload building unchanged |
| `test_stale_response_ignored` | Result, stale ignored | `_try_response` `future.done()` guard |
| `test_close_cancels_pending` | Future cancelled | `_pending` dict stays on transport |
| `test_dispatch_error_swallowed` | Result despite callback error | `with suppress(Exception)` in `run()` |

### 6c. Full test suite

```bash
uv run pytest
```

Expected: same pass/fail count as Task 1 baseline.

### 6d. Import resolution

```bash
uv run python -c "from aria2.client.transport.ws import WebSocketTransport; print(type(WebSocketTransport))"
```

Expected: resolves to `<class 'type'>` (the class object).

Also verify `__all__` exports only `"WebSocketTransport"`:
```bash
uv run python -c "from aria2.client.transport.ws import __all__; print(__all__)"
# Expected: ['WebSocketTransport']
```

### 6e. Structural compliance — function body line counts

```bash
uv run python -c "
import ast, os
base = 'packages/aria2-sdk/src/aria2/client/transport/ws'
for fname in ['_reader.py', 'transport.py']:
    path = os.path.join(base, fname)
    with open(path) as f:
        tree = ast.parse(f.read())
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            body = [n for n in node.body if not (isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant) and isinstance(n.value.value, str))]
            lines = len(body)
            flag = '❌' if lines > 20 else '✅'
            print(f'{flag} {fname}:{node.lineno} {node.name} → {lines} body lines (limit 20)')
"
```

Expected: no function exceeds 20 body lines. Every entry shows `✅`.

### 6f. Structural compliance — file line counts

```bash
wc -l packages/aria2-sdk/src/aria2/client/transport/ws/transport.py
wc -l packages/aria2-sdk/src/aria2/client/transport/ws/_reader.py
wc -l packages/aria2-sdk/src/aria2/client/transport/ws/_pending.py
wc -l packages/aria2-sdk/src/aria2/client/transport/ws/__init__.py
```

Expected: all files ≤200 lines.

### 6g. No circular imports

```bash
uv run python -c "
import ast, sys
# Parse both files and check imports
for fname in ['_reader.py', 'transport.py']:
    with open(f'packages/aria2-sdk/src/aria2/client/transport/ws/{fname}') as f:
        tree = ast.parse(f.read())
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module:
                print(f'{fname} imports from {node.module}')
"
```

Expected: `transport.py` imports from `_reader`, but `_reader.py` does NOT
import from `transport`. (One-way dependency, no cycle.)

---

## Dependency Order

```
Task 1 (GREEN baseline)
   │
   ▼
Task 2 (create _reader.py)
   │
   ▼
Task 3 (extract _init_internal_state)
   │
   ▼
Task 4 (wire _WsReader into connect/close)
   │
   ▼
Task 5 (remove dead methods/imports)
   │
   ▼
Task 6 (full verification)
```

Tasks must run sequentially. Each task verifies its own step before proceeding.

---

## Rollback Plan

If any task fails verification, rollback is straightforward:

```bash
# Full rollback (any task)
cd /home/Row/development/workspaces/python/aria2
git checkout -- packages/aria2-sdk/src/aria2/client/transport/ws/transport.py
rm -f packages/aria2-sdk/src/aria2/client/transport/ws/_reader.py
uv run pytest tests/test_ws.py -v  # confirm original state
```

Or per-task rollback:
- **Task 3 failure:** `git checkout -- transport.py`
- **Task 4 failure:** revert to Task 3 state, debug, retry
- **Task 5 failure:** `git checkout -- transport.py` + keep `_reader.py`

---

## Risk Notes

| Risk | Mitigation |
|------|------------|
| `_should_reconnect` flag sync | Flag lives ONLY on reader. Transport sets it via `self._reader._should_reconnect` (connect) and `self._reader.stop()` (close). No dual-location flag to sync. |
| Reader task double-start | Same as current code — no protection against double `connect()`. Not introduced by this change. |
| `except TimeoutError, OSError:` in `_reconnect` | Pre-existing bug in original code. Copied as-is to `_reader.py`. Tracked separately. |
| `_reader` is `None` guard in `close()` | Explicit `if self._reader is not None:` before calling `.stop()`. Handles pre-connect close. |
| Coverage regression | All 11 tests exercise refactored code paths. `_reconnect()` path remains uncovered (pre-existing gap, not introduced by this refactor). |

---

## Success Criteria (all must pass on Task 6)

- [ ] `ruff check` zero errors on `ws/` package
- [ ] `ty --strict` zero errors on `ws/` package
- [ ] `pytest tests/test_ws.py -v` — all 11 tests pass without modification
- [ ] `pytest` — full suite passes (no regressions)
- [ ] `from aria2.client.transport.ws import WebSocketTransport` resolves
- [ ] `__all__` exports only `"WebSocketTransport"`
- [ ] Every function body ≤20 lines
- [ ] `transport.py` ≤200 lines, `_reader.py` ≤200 lines
- [ ] No circular imports (`_reader.py` does not import from `transport.py`)
- [ ] `t._pending` is a `dict[int, Future]` accessible on transport instances
