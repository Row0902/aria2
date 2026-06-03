# Design: Refactor 4 SDK Functions Exceeding `max_function_lines: 20`

**Change ID:** `2026-06-03-func-lines-sdk`
**Status:** Draft
**Precedent:** `2026-06-03-ws-transport-split` (same extraction pattern)

---

## 1. Architecture

This is a pure structural refactoring. No new types, no new modules, no API changes. Each
violating function is decomposed by extracting its parameter-building or I/O-wrapping logic
into a private helper — the same pattern established in the WebSocket transport refactoring.

The four extractions are independent. They touch three different files and have zero
inter-dependencies. Implementation order does not matter.

---

## 2. Extraction Details

### 2.1 `download.py` — `_build_torrent_params` + `_build_metalink_params`

**Problem:** `add_torrent` (29 lines) and `add_metalink` (21 lines) both contain deeply
nested conditional logic for building the positional RPC params array. Both also contain
`import base64` inside the function body.

**Solution:**

1. Move `import base64` from both function bodies to module-level.
2. Extract `_build_torrent_params(b64, uris, options, position) -> list[Any]` as a
   module-level function (not a method — it doesn't need `self`).
3. Extract `_build_metalink_params(b64, options, position) -> list[Any]` as a module-level
   function.

**Design decisions:**

| Decision | Rationale |
|---|---|
| Module-level, not static method | Pure data transformation, no access to `self` needed. Easier to test. |
| `[]` placeholder, not `{}` | Test `test_add_torrent_with_uris_position` asserts `params[2] == []`. |
| Sequential if-blocks, not | Each conditional is independent — the `has_uris and options is None` |
| nested if/elif | check only applies when `position` is present. |

**Refactored `add_torrent`:**
```python
async def add_torrent(self, torrent, uris=None, options=None, position=None) -> str:
    b64 = base64.b64encode(torrent).decode("ascii")
    params = _build_torrent_params(b64, uris, options, position)
    return await self._request("aria2.addTorrent", params)
```

**Refactored `add_metalink`:**
```python
async def add_metalink(self, metalink, options=None, position=None) -> list[str]:
    b64 = base64.b64encode(metalink).decode("ascii")
    params = _build_metalink_params(b64, options, position)
    return await self._request("aria2.addMetalink", params)
```

### 2.2 `http.py` — `_do_request`

**Problem:** `HttpTransport.send_request` (33 lines) mixes connection guard, ID management,
payload building, HTTP I/O, status checking, response parsing, and error wrapping.

**Solution:** Extract the HTTP I/O + error wrapping block into `_do_request(payload) -> Any`.

**Design decisions:**

| Decision | Rationale |
|---|---|
| Instance method, not module-level | Needs `self._client` and `self._url`. |
| Mirrors WS `_send_and_wait` | Same pattern: public `send_request` does guard/ID/payload, |
| | private `_do_request` does I/O + error wrapping. |
| Keeps `except Aria2RpcError: raise` | Redundant but harmless. Removing it is a minor behavioral change. |
| | Keeping it is zero risk. |

**Refactored `send_request`:**
```python
async def send_request(self, method, params, *, add_secret=True) -> Any:
    if not self.is_connected:
        raise Aria2ConnectionError("HTTP transport is not connected")
    self._request_id += 1
    payload = self._build_payload(method, params, add_secret)
    return await self._do_request(payload)
```

### 2.3 `client/__init__.py` — `_init_sub_managers`

**Problem:** `Aria2Client.__init__` (25 lines) stores parameters, creates transports,
initialises callbacks, and wires 6 sub-managers.

**Solution:** Extract sub-manager instantiation into `_init_sub_managers(self)`.

**Design decisions:**

| Decision | Rationale |
|---|---|
| Instance method | Needs `self` to set instance attributes. |
| Follows `_init_ws_transport` precedent | Existing pattern in the same class. |
| Called at end of `__init__` | After all other fields are set (transports, callbacks). |

**Refactored `__init__`:**
```python
def __init__(self, host="localhost", port=6800, secret=None, *, enable_ws=True, timeout=30.0):
    self._host = host
    self._port = port
    self._secret = secret
    self._timeout = timeout
    self._http = HttpTransport(host, port, secret, timeout=timeout)
    self._ws = self._init_ws_transport(host, port, secret, timeout, enable_ws)
    self._callbacks = {name: [] for name in _EVENT_MAP}
    self._init_sub_managers()
```

---

## 3. Error Handling

No new error paths are introduced. All exception types (and the existing re-raise guard
in `_do_request`) are preserved from the original code.

| Extraction | Error handling |
|---|---|
| `_build_torrent_params` | Pure data — no error paths. |
| `_build_metalink_params` | Pure data — no error paths. |
| `_do_request` | Preserves all 3 exception handlers from original `send_request`. |
| `_init_sub_managers` | Pure object construction — no error paths beyond existing import errors. |

---

## 4. Testing Strategy

- **No new tests.** All existing tests exercise the refactored public methods.
- **No test modifications.** Public API surfaces are unchanged.
- Verification commands:
  ```bash
  uv run python scripts/lint/wc-lint.py packages/aria2-sdk/src/aria2/client/
  uv run pytest -x -q -m "not integration" tests/
  uv run ty check packages/aria2-sdk/src/
  ```

---

## 5. File Impact

| File | Before | After | Δ |
|---|---|---|---|
| `download.py` | ~87 lines, 2 violations | ~95 lines, 0 violations | +8 lines, +2 helpers |
| `http.py` | ~93 lines, 1 violation | ~100 lines, 0 violations | +7 lines, +1 helper |
| `client/__init__.py` | ~155 lines, 1 violation | ~160 lines, 0 violations | +5 lines, +1 helper |

All files remain under 200 lines. Total change: ~60 lines. Well within 400-line review budget.

---

## 6. Rollback

```bash
git checkout packages/aria2-sdk/src/aria2/client/download.py
git checkout packages/aria2-sdk/src/aria2/client/transport/http.py
git checkout packages/aria2-sdk/src/aria2/client/__init__.py
pytest tests/ -x -q  # verify original state
```
