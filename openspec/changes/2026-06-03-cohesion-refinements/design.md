# Design: Cohesion Refinements for aria2-sdk

## Architecture

### C1 — Split SystemManager

**New class: `DaemonManager`**

File: `aria2/client/daemon.py`

```python
class DaemonManager:
    """Control daemon lifecycle — shutdown, session persistence, cleanup.

    Accessed via :attr:`Aria2Client.daemon`.
    """

    def __init__(self, request: Callable[..., Any], secret: str | None) -> None:
        self._request = request
        self._secret = secret

    async def shutdown(self, force: bool = False) -> str: ...
    async def save_session(self) -> str: ...
    async def purge_download_result(self) -> str: ...
    async def remove_download_result(self, gid: str) -> str: ...
```

**Modified: `SystemManager`**

Remove these methods:
- `shutdown`, `save_session`, `purge_download_result`, `remove_download_result`
- `multicall`

Keep: `get_version`, `get_session_info`, `list_methods`, `list_notifications`.

`SystemManager.__init__` no longer needs `secret` (only `DaemonManager` needs it).

**Modified: `Aria2Client`**

```python
class Aria2Client:
    def __init__(self, ...):
        ...
        self._system = SystemManager(self._request)
        self._daemon = DaemonManager(self._request, self._secret)

    @property
    def daemon(self) -> DaemonManager:
        return self._daemon
```

**`multicall` → `Aria2Client.multicall()`**

Since `multicall` is cross-cutting (executes ANY RPC method), it belongs
at the client level:

```python
class Aria2Client:
    async def multicall(self, calls: list[dict[str, Any]]) -> list[Any]:
        """Execute multiple RPC calls in a single request."""
        if self._secret:
            calls = [
                {
                    "methodName": call["methodName"],
                    "params": [f"token:{self._secret}", *call.get("params", [])],
                }
                for call in calls
            ]
        return await self._request("system.multicall", [calls], add_secret=False)
```

### C2 — Rename `_helpers.py` → `_key_utils.py`

- `git mv` the file
- Update imports in `status.py` and `system.py`
- Update any `__all__` references (none, it's private)

### C3 — `StatusType` enum

The enum goes in `types/__init__.py`. Properties are computed from the enum
value, eliminating the need for per-subclass overrides.

`_BaseDownloadStatus` gets a computed `status_type` property. The old `is_*`
properties delegate to it for backward compatibility.

Subclasses: remove `is_active`, `is_complete`, `is_error` overrides.
Remove the import of `DownloadStatus` from subclasses that no longer need it.

### C4 — Consolidate event mapping

**Move `_EVENT_MAP` to `events.py`**:

```python
# events.py
_EVENT_MAP: dict[str, str] = {
    "onDownloadStart": "aria2.onDownloadStart",
    "onDownloadPause": "aria2.onDownloadPause",
    "onDownloadStop": "aria2.onDownloadStop",
    "onDownloadComplete": "aria2.onDownloadComplete",
    "onDownloadError": "aria2.onDownloadError",
    "onBtDownloadComplete": "aria2.onBtDownloadComplete",
}
```

**Modified `EventManager`**:

```python
class EventManager:
    def __init__(self) -> None:
        self._callbacks: dict[str, list[Callable]] = defaultdict(list)
```

Registration methods stay the same (public API unchanged). They already
use `self._callbacks[short_name].append(cb)` internally.

If we want to drive methods from the map, we could use `__init_subclass__`
metaprogramming, but that's over-engineering. Keeping explicit methods is
fine — they're the public API and should be discoverable and typed.

**Modified `Aria2Client`**:

- Remove `_EVENT_MAP` from `client/__init__.py`
- Import it from `events.py` for `_on_event`
- Pass `self._on_event` to WS transport as before

### C5 — Fix dead code in `_reconnect`

**Before**:
```python
async def _reconnect(self) -> None:
    delay = self._reconnect_delay
    while self._should_reconnect:
        try:
            await asyncio.sleep(delay)
            ...
            await self._reader_loop()
        except (TimeoutError, OSError):
            delay = min(delay * 2, self._max_reconnect_delay)  # OK: inside except
        else:
            return
            delay = min(delay * 2, self._max_reconnect_delay)  # BUG: unreachable
```

The `else` branch runs when connection succeeds — no need to update delay.
The bug is having the delay update after `return`. Fix:

```python
        except (TimeoutError, OSError):
            delay = min(delay * 2, self._max_reconnect_delay)
        else:
            return
```

Also fix the bare `except` syntax: `except TimeoutError, OSError:` should
be `except (TimeoutError, OSError):` — this is Python 2 syntax, works in
3.x but is misleading. Actually wait, let me re-read the original code...

Looking at the original code:
```python
            except TimeoutError, OSError:
                delay = min(delay * 2, self._max_reconnect_delay)
            else:
                return
                delay = min(delay * 2, self._max_reconnect_delay)
```

The `except TimeoutError, OSError:` is actually `except TimeoutError as OSError:` in Python 3 — it's catching `TimeoutError` and binding it to the name `OSError`, shadowing the builtin! This is a bug. It should be `except (TimeoutError, OSError):`.

So there are actually TWO bugs:
1. `except TimeoutError, OSError:` → should be `except (TimeoutError, OSError):`
2. `delay = ...` after `return` is unreachable

### C6 — Move late import

Move `from aria2.rpc import build_request as _build_noauth` from inside
`send_request` to module level.

## Backward compatibility

**Breaking changes** (minor semver — `SystemManager.shutdown` moves):
- `client.system.shutdown()` → `client.daemon.shutdown()`
- `client.system.save_session()` → `client.daemon.save_session()`
- `client.system.purge_download_result()` → `client.daemon.purge_download_result()`
- `client.system.remove_download_result()` → `client.daemon.remove_download_result()`
- `client.system.multicall()` → `client.multicall()`

All non-breaking renames/refactors are internal (private modules).

## Testing

- Run existing tests: `uv run pytest -x --no-header packages/aria2-sdk/tests/`
- Check for import errors: `uv run ty check packages/aria2-sdk/src/`
