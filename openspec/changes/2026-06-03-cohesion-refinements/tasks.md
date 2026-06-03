# Tasks: Cohesion Refinements for aria2-sdk

## Task list

| # | Task | File(s) | Depends on |
|---|---|---|---|
| 1 | Fix dead code and syntax bug in ws.py `_reconnect` | `transport/ws.py` | — |
| 2 | Move late import in ws.py to module level | `transport/ws.py` | — |
| 3 | Rename `_helpers.py` → `_key_utils.py`, update imports | `client/_helpers.py` → `client/_key_utils.py`, `status.py`, `system.py` | — |
| 4 | Add `StatusType` enum to types, refactor `is_*` in base model | `types/__init__.py`, `models/base.py`, `models/status_*.py` | — |
| 5 | Consolidate event mapping — move `_EVENT_MAP` to events.py | `client/__init__.py`, `client/events.py` | — |
| 6 | Split SystemManager — extract DaemonManager + multicall move | `client/system.py`, `client/daemon.py` (new), `client/__init__.py` | 1, 2, 3, 4, 5 |
