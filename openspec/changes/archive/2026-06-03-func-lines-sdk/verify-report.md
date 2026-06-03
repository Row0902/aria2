# Verify Report: Refactor 4 SDK Functions Exceeding `max_function_lines: 20`

**Change ID:** `2026-06-03-func-lines-sdk`
**Status:** ✅ **PASS**

## Verification Results

| Check | Result |
|---|---|
| `uv run python scripts/lint/wc-lint.py packages/aria2-sdk/src/aria2/client/` | ✅ 0 violations in scope |
| `uv run ruff check packages/aria2-sdk/src/aria2/client/` | ✅ All checks passed |
| `uv run ty check packages/aria2-sdk/src/` | ✅ All checks passed |
| `uv run pytest -x -q -m "not integration" tests/` | ✅ 116 passed, 17 skipped |

## Task Completion

| # | Task | File | Status |
|---|---|---|---|
| 1 | Move `import base64` to module-level | `download.py` | ✅ Done |
| 2 | Extract `_build_metalink_params` | `download.py` | ✅ Done |
| 3 | Extract `_build_torrent_params` | `download.py` | ✅ Done |
| 4 | Refactor `add_metalink` to delegate | `download.py` | ✅ Done |
| 5 | Refactor `add_torrent` to delegate | `download.py` | ✅ Done |
| 6 | Extract `_do_request` in HttpTransport | `http.py` | ✅ Done |
| 7 | Refactor `send_request` to delegate | `http.py` | ✅ Done |
| 8 | Extract `_init_sub_managers` in Aria2Client | `client/__init__.py` | ✅ Done |
| 9 | Refactor `__init__` to call `_init_sub_managers` | `client/__init__.py` | ✅ Done |
| 10 | Full verification suite | All 3 files | ✅ Done |

## Changes Delivered

| File | Before | After | Helpers added |
|---|---|---|---|
| `download.py` | `add_torrent` 29, `add_metalink` 21 | `add_torrent` ~12, `add_metalink` ~10 | `_build_torrent_params`, `_build_metalink_params` |
| `http.py` | `send_request` 33 | `send_request` ~18 | `_do_request` |
| `client/__init__.py` | `__init__` 25, file 205 lines | `__init__` ~18, file 170 lines | `_init_sub_managers` |

## Deviations from Design

None. All extractions follow the design exactly.

## Review Workload

| Metric | Value |
|---|---|
| Estimated changed lines | ~60 |
| Review budget | 400 lines |
| Chained PRs recommended | **No** — single PR |

## Remaining Violations (Out of Scope)

The following pre-existing violations are tracked separately:
- `ws/transport.py:30 WebSocketTransport.__init__` — 24 lines (issue #9)
