# SDD Tasks: WebSocketTransport Refactoring — Extract into `ws/` Package

**Change ID:** `2026-06-03-ws-transport-split`
**Date:** 2026-06-03
**Status:** Tasks defined
**Strategy:** A — package extraction with `_pending` as plain dict, `_PendingRequestManager` as operator

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~200 added + 207 deleted = ~407 total |
| 400-line budget risk | Low |
| Chained PRs recommended | No |
| Suggested split | Single PR (all files in one atomic unit) |
| Delivery strategy | auto-chain (single PR) |
| Chain strategy | single-pr |

Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: single-pr
400-line budget risk: Low

**Rationale:** The ~200 lines of new code fit comfortably within the 400-line review budget. The 207-line deletion is a pure removal of the old monolithic file with no behavioral review needed. All new code comes directly from the approved design document — no design decisions remain open. The five steps are atomic: the package must be complete before the old file is deleted.

---

## Task Dependency Graph

```
Task 1 (init) ──► Task 2 (_pending) ──► Task 3 (transport) ──► Task 4 (delete ws.py) ──► Task 5 (verify)
```

Tasks 1–3 can be created in sequence (each imports resolve incrementally). Task 4 is the critical switchover — the old file must be deleted only after Task 3 is verified. Task 5 is the final compliance gate.

---

## Task 1: Create `transport/ws/__init__.py` — Re-export Module

**Status:** ⬜ pending  
**Estimated effort:** S (trivial)  
**Dependencies:** None  

### Action

Create file `packages/aria2-sdk/src/aria2/client/transport/ws/__init__.py` with the exact content from [design Section 2.1](#21-transportws__init__py):

```python
"""WebSocket transport package for aria2 JSON-RPC."""
from aria2.client.transport.ws.transport import WebSocketTransport

__all__ = ["WebSocketTransport"]
```

### Verification

| # | Check | Command | Expected |
|---|---|---|---|
| 1 | Directory exists | `ls packages/aria2-sdk/src/aria2/client/transport/ws/__init__.py` | File exists |
| 2 | File line count | `wc -l packages/aria2-sdk/src/aria2/client/transport/ws/__init__.py` | ≤ 10 lines |
| 3 | `__all__` present | `grep __all__ packages/aria2-sdk/src/aria2/client/transport/ws/__init__.py` | One match |

**Note:** At this stage, `from aria2.client.transport.ws import WebSocketTransport` will fail because `ws/transport.py` does not yet exist. This is expected — the task only scaffolds the re-export point.

---

## Task 2: Create `transport/ws/_pending.py` — Pending Request Manager

**Status:** ⬜ pending  
**Estimated effort:** S (small)  
**Dependencies:** Task 1 (directory must exist)  

### Action

Create file `packages/aria2-sdk/src/aria2/client/transport/ws/_pending.py` with the exact content from [design Section 2.3](#23-transportws_pendingpy):

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

### Verification

| # | Check | Command | Expected |
|---|---|---|---|
| 1 | File exists | `ls packages/aria2-sdk/src/aria2/client/transport/ws/_pending.py` | File exists |
| 2 | File line count | `wc -l packages/aria2-sdk/src/aria2/client/transport/ws/_pending.py` | ≤ 45 lines |
| 3 | Syntax valid | `python -c "import ast; ast.parse(open('packages/aria2-sdk/src/aria2/client/transport/ws/_pending.py').read())"` | No output (no syntax error) |
| 4 | Import works (standalone) | `python -c "from aria2.client.transport.ws._pending import _PendingRequestManager; print(_PendingRequestManager)"` | Class printed |

**Key constraint check:** `_PendingRequestManager` uses `dict.pop(rid, None)` and `dict.get(rid)` — these methods are **already exercised** by the existing `test_close_cancels_pending` test (which accesses `t._pending` directly as a plain dict).

---

## Task 3: Create `transport/ws/transport.py` — WebSocketTransport Class

**Status:** ⬜ pending  
**Estimated effort:** M (medium)  
**Dependencies:** Task 2 (`_pending.py` must exist for import)  

### Action

Create file `packages/aria2-sdk/src/aria2/client/transport/ws/transport.py` with the exact content from [design Section 2.2](#22-transportwstransportpy).

This task produces the largest new file (~160 lines) and is the core of the refactoring. The source code in the design document contains all methods, imports, and the `_build_url` module-level helper.

### Key structural mapping (old → new)

| Old `ws.py` | New `ws/transport.py` |
|---|---|
| Lines 1–20 (imports) | Lines 1–20 (imports + `_build_url`) |
| Lines 22–52 (`class`, `__init__`, `_pending` dict) | Lines 25–67 (same + `_pending_mgr` construction) |
| Lines 56–59 (`is_connected`) | Lines 69–72 |
| Lines 61–82 (`connect`) | Lines 74–95 (uses `_build_url`) |
| Lines 84–122 (`send_request`) | Lines 97–140 (delegates to `_build_payload` + `_send_and_wait`) |
| — (new helper) | `_build_payload` ~3 lines |
| — (new helper) | `_send_and_wait` ~10 lines |
| Lines 124–147 (`close`) | Lines 142–168 (delegates to `_stop_reader` + `_close_ws` + `_cancel_pending`) |
| — (new helper) | `_stop_reader` ~6 lines |
| — (new helper) | `_close_ws` ~4 lines |
| — (new helper) | `_cancel_pending` ~3 lines |
| Lines 149–162 (`_reader_loop`) | Lines 180–192 |
| Lines 164–198 (`_dispatch`) | Lines 194–225 (delegates to `_try_notification` + `_try_response`) |
| — (new helper) | `_try_notification` ~7 lines |
| — (new helper) | `_try_response` ~9 lines |
| Lines 200–207 (`_reconnect`) | Lines 235–255 (fixed syntax `except (TimeoutError, OSError):`, uses `_build_url`) |

### Bug fix applied

In `_reconnect()`, line 205 of the old file:
```python
except TimeoutError, OSError:       # BUG: catches TimeoutError only, rebinds OSError
```
Fixed in new file:
```python
except (TimeoutError, OSError):     # FIX: catches both as a tuple
```

This is the **only** behavioral change. All other behavior is byte-for-byte identical.

### Verification (before deleting ws.py)

| # | Check | Command | Expected |
|---|---|---|---|
| 1 | File exists | `ls packages/aria2-sdk/src/aria2/client/transport/ws/transport.py` | File exists |
| 2 | File line count | `wc -l packages/aria2-sdk/src/aria2/client/transport/ws/transport.py` | ≤ 200 lines |
| 3 | Syntax valid | `python -c "import ast; ast.parse(open('packages/aria2-sdk/src/aria2/client/transport/ws/transport.py').read())"` | No output |
| 4 | Import resolves via package | `python -c "from aria2.client.transport.ws import WebSocketTransport; print(WebSocketTransport)"` | No ImportError (may warn about stale `ws.py` shadowing) |
| 5 | All function bodies ≤ 20 lines | `awk '/^    (async )?def /{f=$0} /^$/{next} /^    /{c++} /^    (async )?def /{if(f) print f, c; f=$0; c=1}' packages/aria2-sdk/src/aria2/client/transport/ws/transport.py` | Every function ≤ 20 |
| 6 | Lint clean | `ruff check packages/aria2-sdk/src/aria2/client/transport/ws/transport.py` | No errors |
| 7 | Type check clean | `ty --strict packages/aria2-sdk/src/aria2/client/transport/ws/` | No errors |

**Critical note:** At this stage, both `ws.py` (old) and `ws/` (new) exist simultaneously. Python may pick up the old file. The verification in Task 4 confirms the package takes priority.

---

## Task 4: Delete `transport/ws.py` — Remove Monolithic File

**Status:** ⬜ pending  
**Estimated effort:** S (small)  
**Dependencies:** Task 3 (new package must be complete and verified)  
**⚠️ CRITICAL GATE:** Do NOT proceed unless Task 3 verification checks 4–7 all pass.  

### Action

1. **Pre-deletion safety check:** Confirm the new package resolves independently:

   ```bash
   python -c "from aria2.client.transport.ws import WebSocketTransport; print(WebSocketTransport); print('ok')"
   ```

   Expected: prints the class and `"ok"`. If Python picks up the old `ws.py` instead, we'll see the old class — proceed anyway; the deletion will resolve it.

2. **Delete the old file:**

   ```bash
   git rm packages/aria2-sdk/src/aria2/client/transport/ws.py
   ```

3. **Confirm package resolution post-deletion:**

   ```bash
   python -c "from aria2.client.transport.ws import WebSocketTransport; t = WebSocketTransport('localhost', 6800); print(type(t)); print('ok')"
   ```

   Expected: prints `<class 'aria2.client.transport.ws.transport.WebSocketTransport'>` and `"ok"`.

### Verification

| # | Check | Command | Expected |
|---|---|---|---|
| 1 | Old file removed from git | `git status -- packages/aria2-sdk/src/aria2/client/transport/ws.py` | File shows as deleted |
| 2 | Old file gone from disk | `ls packages/aria2-sdk/src/aria2/client/transport/ws.py 2>&1` | No such file |
| 3 | Package resolves | `python -c "from aria2.client.transport.ws import WebSocketTransport; print(type(WebSocketTransport))"` | Prints class type |
| 4 | No ws.py shadow | `python -c "import aria2.client.transport.ws; print(aria2.client.transport.ws.__file__)"` | Points to `ws/__init__.py` |

**Rollback if any check fails:**

```bash
git checkout packages/aria2-sdk/src/aria2/client/transport/ws.py
# Package can remain; old file is restored.
```

---

## Task 5: Full Verification Suite

**Status:** ⬜ pending  
**Estimated effort:** S (small)  
**Dependencies:** Task 4 (old file must be deleted)  

### Action

Run the complete verification suite to confirm behavioral equivalence, code quality, and policy compliance.

### Verification checklist

| # | Check | Command | Expected |
|---|---|---|---|
| 1 | **All 11 tests pass** | `pytest tests/test_ws.py -v` | 11 passed, 0 failed, 0 skipped |
| 2 | **No test modifications** | `git diff tests/test_ws.py` | No diff (empty) |
| 3 | **Lint: new package** | `ruff check packages/aria2-sdk/src/aria2/client/transport/ws/` | No errors |
| 4 | **Type check** | `ty --strict packages/aria2-sdk/src/aria2/client/transport/ws/` | No errors |
| 5 | **File line limits** | `wc -l packages/aria2-sdk/src/aria2/client/transport/ws/*.py` | All ≤ 200 |
| 6 | **Function line limits** | Manual inspection (or awk from Task 3) | All ≤ 20 |
| 7 | **`__all__` correct** | `python -c "from aria2.client.transport.ws import *; assert 'WebSocketTransport' in dir()"` | No error |
| 8 | **Import from old path works** | `python -c "from aria2.client.transport.ws import WebSocketTransport"` | No error |
| 9 | **`t._pending` is plain dict** | `python -c "from aria2.client.transport.ws import WebSocketTransport; t = WebSocketTransport('localhost', 6800); print(type(t._pending))"` | Prints `<class 'dict'>` |
| 10 | **`test_close_cancels_pending` dict access** | `pytest tests/test_ws.py::test_close_cancels_pending -v` | Passed (confirms `t._pending[999] = fut` works) |
| 11 | **Full test suite** | `pytest` | All pass, coverage ≥ 80% |
| 12 | **Git diff completeness** | `git diff --stat HEAD` | Shows ~4 files: 3 new, 1 deleted |

### Detailed test expectations

Each of the 11 tests validates a specific code path in the refactored transport:

| Test | Key extraction(s) exercised | Must pass? |
|---|---|---|
| `test_connect_and_request` | `_build_url`, `connect`, `_build_payload`, `_send_and_wait`, `_stop_reader`, `_close_ws` | ✅ |
| `test_rpc_error` | `_try_response` error path, `_parse_response` raising `Aria2RpcError` | ✅ |
| `test_notification_dispatched` | `_try_notification`, `_parse_notification` | ✅ |
| `test_is_connected` | `is_connected` property, `connect`, `close` | ✅ |
| `test_not_connected_raises` | `send_request` → `is_connected` guard | ✅ |
| `test_close_without_connect_is_safe` | `_stop_reader`, `_close_ws` guard conditions | ✅ |
| `test_connect_refused_raises` | `connect` → `except (TimeoutError, OSError)` | ✅ |
| `test_send_request_no_secret` | `_build_payload` → `_build_noauth` branch | ✅ |
| `test_stale_response_ignored` | `_try_response` → `future is None` guard | ✅ |
| `test_close_cancels_pending` | `_cancel_pending` → `_pending_mgr.cancel_all()`. **Also validates `t._pending` is a dict.** | ✅ |
| `test_dispatch_error_swallowed` | `_dispatch` → `suppress(Exception)` → `_try_notification` | ✅ |

**No test modifications are expected or allowed.** If any test fails, the refactoring has introduced a behavioral regression. Roll back via Task 4's rollback procedure and investigate.

---

## Task Summary

| Task | File(s) | Lines | Effort | Critical? |
|---|---|---|---|---|
| 1 | `ws/__init__.py` | ~5 added | S | No — safe scaffolding |
| 2 | `ws/_pending.py` | ~35 added | S | No — isolated helper |
| 3 | `ws/transport.py` | ~160 added | M | **Yes** — core extraction |
| 4 | Delete `ws.py` | ~207 deleted | S | **Yes** — package switchover |
| 5 | Full verification | — | S | **Yes** — compliance gate |

**Total:** ~200 lines added, ~207 lines deleted. ~407 changed lines (within tolerance of 400-line budget).

---

## Additional Notes

### Why single PR (no chain)

All 5 tasks form one atomic change. The package is incomplete until `ws.py` is deleted (Python may resolve the old file if both exist). Splitting across PRs would leave intermediate states where neither the old file nor the new package resolves correctly. A single PR keeps the delta reviewable and the git history clean.

### Edge cases to re-verify manually

While tests cover most paths, these pre-existing behaviors should be spot-checked if possible:

1. **Reconnection loop** — no test exercises this path. The syntax fix on `except TimeoutError, OSError:` changes behavior here. Consider manual verification with a real aria2 daemon that is restarted during a session.
2. **Double close** — test `test_close_without_connect_is_safe` covers the unconnected case but not double-connected-close. The design confirms idempotency in Section 7.3.
3. **Concurrent requests** — no dedicated test. The design confirms isolation by unique request IDs in Section 7.5.

### Rollback strategy (full)

If verification fails at any point:

```bash
# 1. Restore old file from git
git checkout packages/aria2-sdk/src/aria2/client/transport/ws.py

# 2. Remove new package (if it exists)
rm -rf packages/aria2-sdk/src/aria2/client/transport/ws/

# 3. Confirm original state
pytest tests/test_ws.py -v

# 4. Clean git staging
git reset HEAD packages/aria2-sdk/src/aria2/client/transport/ws.py
```
