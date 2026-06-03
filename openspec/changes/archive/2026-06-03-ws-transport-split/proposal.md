# SDD Proposal: WebSocketTransport Refactoring — Extract into `ws/` Package

**Change ID:** `2026-06-03-ws-transport-split`
**Date:** 2026-06-03
**Status:** Draft

---

## Intent

Refactor `packages/aria2-sdk/src/aria2/client/transport/ws.py` (207 lines, multiple functions exceeding 20-line limit) into a `transport/ws/` package that complies with project policies:

- **`max_function_lines: 20`** — no function body exceeds 20 lines
- **`max_file_lines: 200`** — each source file stays under 200 lines
- **`strict_single_responsibility`** — each module owns one concern

The refactoring is purely structural: **zero behavioural changes**, **zero API changes**, **zero test modifications**.

---

## Scope

### In scope

| File | Description | Est. lines |
|---|---|---|
| `transport/ws/__init__.py` | Public re-export of `WebSocketTransport` from `.transport` | 8 |
| `transport/ws/transport.py` | `WebSocketTransport` class (~160 lines) — host, connect, send_request, close, reader loop, reconnect | ≤200 ✅ |
| `transport/ws/_pending.py` | `_PendingRequestManager` helper — pending futures lifecycle | ~35 |

### Out of scope

- Changes to `Transport` ABC in `transport/__init__.py`
- Changes to `Aria2Client` in `client/__init__.py`
- Changes to existing tests
- Adding new tests (test coverage is verified separately)
- Fixing `except TimeoutError, OSError:` syntax bug beyond the inline fix (tracked separately)

---

## Affected Areas

### Directly affected

| Module | Change |
|---|---|
| `src/aria2/client/transport/ws.py` | **Deleted** — replaced by `transport/ws/` package |
| `src/aria2/client/transport/ws/__init__.py` | **Created** — canonical import path |
| `src/aria2/client/transport/ws/transport.py` | **Created** — core `WebSocketTransport` class |
| `src/aria2/client/transport/ws/_pending.py` | **Created** — pending request manager |

### Indirectly affected (imports must keep working)

| Module | Why |
|---|---|
| `src/aria2/client/__init__.py` | Imports `from aria2.client.transport.ws import WebSocketTransport` |
| `src/aria2/client/transport/__init__.py` | No change needed (re-export not required, but must not break) |
| Any test importing `WebSocketTransport` | Must resolve via the same import path |
| Any test accessing `t._pending` | Must remain a `dict[int, Future]` on the instance |

---

## Architecture: Strategy A — Package Extraction

### Before (monolithic file)

```
transport/
├── __init__.py          # Transport ABC
├── http.py              # HttpTransport
└── ws.py                # WebSocketTransport (207 lines, multiple violations)
```

### After (split package)

```
transport/
├── __init__.py          # Transport ABC (unchanged)
├── http.py              # HttpTransport (unchanged)
└── ws/
    ├── __init__.py      # re-export WebSocketTransport from .transport (8 lines)
    ├── transport.py     # WebSocketTransport class (~160 lines, under 200 ✅)
    └── _pending.py      # _PendingRequestManager helper (~35 lines)
```

### File-by-file design

#### `transport/ws/__init__.py`

```python
"""WebSocket transport package for aria2 JSON-RPC."""
from aria2.client.transport.ws.transport import WebSocketTransport

__all__ = ["WebSocketTransport"]
```

- Single purpose: re-export the public symbol.
- Preserves `from aria2.client.transport.ws import WebSocketTransport`.

#### `transport/ws/transport.py`

Contains the `WebSocketTransport` class and the module-level helper `_build_url`.

**Module-level helper:**
```python
def _build_url(host: str, port: int) -> str:
    """Build the WebSocket URL for the aria2 JSON-RPC endpoint."""
    return f"ws://{host}:{port}/jsonrpc"
```

**`WebSocketTransport`** (methods and their line counts):

| Method | Lines | Status |
|---|---|---|
| `__init__` | ~16 | ✅ under 20 |
| `is_connected` (property) | 2 | ✅ |
| `connect` | ~15 | ✅ — delegates URL to `_build_url` |
| `send_request` | ~18 | ✅ — delegates payload to `_build_payload`, pending tracking to `_pending` |
| `close` | ~18 | ✅ — delegates to `_stop_reader`, `_close_ws`, `_cancel_pending` |
| `_reader_loop` | ~15 | ✅ |
| `_dispatch` | ~18 | ✅ — delegates to `_try_notification`, `_try_response` |
| `_reconnect` | ~18 | ✅ — syntax fix only |

Total: ~160 lines, under 200 ✅

New private methods extracted (all module-private via leading underscore):

| Extracted method | Origin | Lines |
|---|---|---|
| `_build_payload(method, params, add_secret) -> str` | from `send_request` | ≤5 |
| `_send_and_wait(payload, rid) -> Any` | from `send_request` | ≤12 |
| `_stop_reader() -> None` | from `close` | ≤8 |
| `_close_ws() -> None` | from `close` | ≤6 |
| `_cancel_pending() -> None` | from `close` | ≤8 |
| `_try_notification(raw) -> bool` | from `_dispatch` | ≤10 |
| `_try_response(raw) -> None` | from `_dispatch` | ≤12 |

#### `transport/ws/_pending.py` (new)

```python
class _PendingRequestManager:
    """Manages the lifecycle of pending JSON-RPC request futures.

    Wraps the ``dict[int, asyncio.Future[Any]]`` that maps request IDs
    to their awaiting futures.  Instance is stored as ``self._pending``
    on ``WebSocketTransport`` so existing tests accessing ``t._pending``
    continue to work (the dict is exposed via ``.__iter__`` / key access
    if needed, but tests that access it as a dict still work because
    ``_pending`` is still a plain ``dict`` — this class wraps it).
    """

    def __init__(self) -> None:
        self._futures: dict[int, asyncio.Future[Any]] = {}

    def register(self, rid: int, future: asyncio.Future[Any]) -> None: ...
    def resolve(self, rid: int) -> asyncio.Future[Any] | None: ...
    def cancel_all(self) -> None: ...
    def clear(self) -> None: ...
```

**Design constraint:** `t._pending` must remain a `dict[int, Future]` on the instance for test compatibility. Two options evaluated:

1. **Option A (chosen):** Keep `_pending` as a plain `dict` on `WebSocketTransport`. The `_PendingRequestManager` operates on the dict passed to it. The transport owns the dict; the manager provides stateless helper methods.

   ```python
   # On WebSocketTransport:
   self._pending: dict[int, asyncio.Future[Any]] = {}
   # _PendingRequestManager receives it as argument:
   self._pending_mgr = _PendingRequestManager(self._pending)
   ```

2. **Option B (rejected):** Make `_PendingRequestManager` own the dict and proxy access. This would require `__getitem__`, `__iter__`, etc. to maintain duck-type compatibility with tests — more coupling than Option A for no gain.

---

## Function Line Count Reconciliation

### Current violations and resolution

| Function | Current lines | Target lines | Resolution |
|---|---|---|---|
| `__init__` | 24 | ≤20 | Trim comments/blank lines; actual assignment lines are ~16 |
| `connect` | 22 | ≤20 | Extract `_build_url` helper, reduce inline URL construction |
| `send_request` | 39 | ≤20 | Extract `_build_payload` + `_send_and_wait` |
| `close` | 25 | ≤20 | Extract `_stop_reader` + `_close_ws` + `_cancel_pending` |
| `_dispatch` | 23 | ≤20 | Extract `_try_notification` + `_try_response` |
| `_reconnect` | 18 | ≤20 | ✅ Already under (syntax fix only) |

### File line count

| File | Lines |
|---|---|
| `ws/__init__.py` | ~8 |
| `ws/transport.py` | ~160 |
| `ws/_pending.py` | ~35 |
| **Total** | **~203** (each file under 200 ✅) |

---

## Implementation Order

1. **Create `openspec/changes/2026-06-03-ws-transport-split/` directory** and write this proposal.
2. **Create `src/aria2/client/transport/ws/__init__.py`** with the re-export.
3. **Create `src/aria2/client/transport/ws/_pending.py`** with `_PendingRequestManager`.
4. **Create `src/aria2/client/transport/ws/transport.py`** — extract `WebSocketTransport` from `ws.py`, applying all method extractions and the `_build_url` helper.
5. **Delete `src/aria2/client/transport/ws.py`** — the old monolithic file.
6. **Run all existing tests** to confirm zero regressions.
7. **Run `ruff check` and `ty`** (type checker) to verify compliance.

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| **Import breakage** — existing consumers use the old path | Medium | High | The `ws/__init__.py` re-export preserves `from aria2.client.transport.ws import WebSocketTransport`. Verify with `grep` for any alternate import patterns. |
| **`t._pending` test access** — tests reference `self._pending` directly | High | Medium | Keep `_pending` as a plain `dict` on `WebSocketTransport`. The `_PendingRequestManager` wraps operations on it. |
| **Missing `__all__`** — ruff/completion surface area changes | Low | Low | Define `__all__` in `__init__.py`. |
| **Reader task restart bug** — `_reader_loop` in `_reconnect` references old `self._ws` after reconnect assignment | Medium | Medium | Inline the `_reader_loop` restart into `_reconnect` after the new `ws_connect` succeeds. The flow remains identical to current code. |
| **Coverage regression** — new files not tracked | Low | Low | `pytest-cov` sources from package discovery; adding files to the same package is automatically picked up. Verify coverage ≥80%. |

---

## Rollback Plan

If the refactoring breaks the build or tests:

1. **Revert** the deletion of `ws.py` (restore via `git checkout`).
2. **Remove** the `transport/ws/` directory (`git rm -r`).
3. Verify original tests pass against the restored `ws.py`.
4. File a follow-up issue with the failure details.

The monolithic `ws.py` is preserved in git history at commit `<current-HEAD>`, so recovery is a single `git checkout` away. No irreversible data loss occurs.

---

## Success Criteria

All of the following must pass:

- [ ] `ruff check packages/aria2-sdk/src/aria2/client/transport/ws/` — zero errors
- [ ] `ty --strict packages/aria2-sdk/src/aria2/client/transport/ws/` — zero type errors
- [ ] All 11 existing tests pass without modification
- [ ] `from aria2.client.transport.ws import WebSocketTransport` works (test import)
- [ ] `client = Aria2Client(...); client._ws._pending` is a `dict[int, Future]`
- [ ] Each function body is ≤20 lines (verify with `awk`/`wc -l`)
- [ ] Each file is ≤200 lines
- [ ] Coverage ≥80% (no regression from current baseline)

---

## Chained PR Forecast

Estimated total changed lines: **~200** (3 new files + 1 deletion).

Given the 400-line review budget, this fits in a **single PR** — no chaining needed.

---

## Appendix: Current `ws.py` Function Line Audit

```
Function                Lines    Violates 20?
──────────────────────  ─────    ─────────────
__init__                24       ❌ (trim to ~16)
is_connected             2       ✅
connect                 22       ❌ (trim to ~15)
send_request            39       ❌ (extract to ~18)
close                   25       ❌ (extract to ~18)
_reader_loop            15       ✅
_dispatch               23       ❌ (extract to ~18)
_reconnect              18       ✅ (syntax bug)
```

Total file: 207 lines → post-refactor: ~203 lines across 3 files (all under 200 ✅).
