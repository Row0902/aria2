# Spec: Cohesion Refinements for aria2-sdk

## Overview

Six targeted fixes to improve module cohesion, reduce connascence, and
eliminate dead code.  Each fix is self-contained and independently reviewable.

## Changes

### C1 — Split SystemManager (high cohesion)

**Problem**: `SystemManager` mixes three unrelated concerns:
read-only introspection, daemon lifecycle control, and batch execution.

**Solution**: Extract two new managers — `DaemonManager` for lifecycle
operations and move `multicall` to the client level.

**Before** (`client/system.py`):
```
SystemManager
├── get_version           ✓ introspection
├── get_session_info      ✓ introspection
├── shutdown              ✗ lifecycle (destructive)
├── force_shutdown        ✗ lifecycle
├── save_session          ✗ lifecycle
├── purge_download_result ✗ lifecycle
├── remove_download_result ✗ lifecycle
├── list_methods          ✓ introspection
├── list_notifications    ✓ introspection
└── multicall             ✗ cross-cutting (batch any RPC)
```

**After**:
```
SystemManager              DaemonManager              Aria2Client
├── get_version            ├── shutdown                └── multicall
├── get_session_info       ├── force_shutdown
├── list_methods           ├── save_session
└── list_notifications     ├── purge_download_result
                            └── remove_download_result
```

**API change**: `client.system.shutdown()` → `client.daemon.shutdown()`
New property `Aria2Client.daemon` returning `DaemonManager`.
`multicall` moves to `client.multicall(calls)`.

### C2 — Rename `_helpers.py` to `_key_utils.py` (semantic naming)

**Problem**: `_helpers` is a generic name that invites unrelated code.

**Solution**: Rename to `_key_utils.py`. Update all imports.

**Affected files**:
- `client/_helpers.py` → `client/_key_utils.py`
- `client/status.py` — update import
- `client/system.py` — update import

**Non-breaking**: This is a private module (`_` prefix). No public API impact.

### C3 — Replace speculative `is_*` properties with `StatusType` enum (cohesion)

**Problem**: `_BaseDownloadStatus` has `is_active`, `is_complete`, `is_error`
returning `False` by default. `PausedStatus` has dead override.
The pattern forces connascence across the entire status model hierarchy.

**Solution**:
1. Add `StatusType` enum to `aria2/types/__init__.py` with an `is_active`,
   `is_complete`, `is_error` properties
2. Replace `is_*` properties on `_BaseDownloadStatus` with a single
   `status_type` property derived from `self.status`
3. Remove unnecessary `is_*` overrides from status subclasses

**Before**:
```python
class _BaseDownloadStatus(BaseModel):
    status: DownloadStatus
    @property
    def is_active(self) -> bool: return False
    @property
    def is_complete(self) -> bool: return False
    @property
    def is_error(self) -> bool: return False

class ActiveStatus(_BaseDownloadStatus):
    @property
    def is_active(self) -> bool: return True

class PausedStatus(_BaseDownloadStatus):
    @property
    def is_active(self) -> bool: return False  # DEAD CODE
```

**After**:
```python
# types/__init__.py
class StatusType(StrEnum):
    ACTIVE = "active"
    WAITING = "waiting"
    PAUSED = "paused"
    ERROR = "error"
    COMPLETE = "complete"
    REMOVED = "removed"

    @property
    def is_active(self) -> bool:
        return self in (StatusType.ACTIVE, StatusType.WAITING)

    @property
    def is_complete(self) -> bool:
        return self == StatusType.COMPLETE

    @property
    def is_error(self) -> bool:
        return self == StatusType.ERROR

# models/base.py
class _BaseDownloadStatus(BaseModel):
    ...
    @property
    def status_type(self) -> StatusType:
        return StatusType(self.status.value)
    
    @property
    def is_active(self) -> bool: return self.status_type.is_active
    @property
    def is_complete(self) -> bool: return self.status_type.is_complete
    @property
    def is_error(self) -> bool: return self.status_type.is_error
```

### C4 — Consolidate event mapping (reduce connascence)

**Problem**: Event names duplicated across `_EVENT_MAP` (client/__init__.py)
and `EventManager` method names (events.py). Adding an event requires
touching 3 locations.

**Solution**: Make `_EVENT_MAP` the single source of truth by moving it
to `events.py` and driving EventManager methods from the map.

**Before**: `_EVENT_MAP` in `client/__init__.py`, EventManager hardcodes
callback dict keys, `_on_event` iterates the map.

**After**: `_EVENT_MAP` is defined in `events.py`. EventManager constructor
builds registration methods from the map. `_on_event` in client imports
the map from events.

**Non-breaking**: Public API (`client.events.on_download_start(...)`) stays
identical. The mapping is internal.

### C5 — Fix dead code in `ws.py:_reconnect` (bugfix)

**Problem**: Unreachable `delay = min(...)` after `return` in the
`else` branch. The exponential backoff never actually backs off.

**Fix**: Move the delay update before the `return` or restructure the
loop so the delay update is reachable.

### C6 — Move late import to module top (code quality)

**Problem**: `from aria2.rpc import build_request as _build_noauth`
inside `send_request` method.

**Fix**: Move to module-level imports alongside the existing import
of `build_request_with_secret`.

## Non-goals

- No changes to the public API beyond the SystemManager→DaemonManager split
  (which is additive — old `client.system.shutdown` still works if we
  keep a forwarding property, but the spec proposes removing it)
- No changes to the transport ABC interface
- No changes to model field definitions or serialization
- No test additions (existing tests must continue to pass)
