# Tasks: Refactor 4 SDK Functions Exceeding `max_function_lines: 20`

**Change ID:** `2026-06-03-func-lines-sdk`
**Status:** Ready

---

## Tasks

| # | Task | File(s) | Depends on | Verification |
|---|---|---|---|---|
| 1 | Move `import base64` to module-level in download.py | `download.py` | — | `ruff check download.py` |
| 2 | Extract `_build_metalink_params(b64, options, position)` | `download.py` | 1 | `pytest tests/test_client.py -k metalink` |
| 3 | Extract `_build_torrent_params(b64, uris, options, position)` | `download.py` | 1 | `pytest tests/test_client.py -k torrent` |
| 4 | Refactor `add_metalink` to delegate to `_build_metalink_params` | `download.py` | 2 | `pytest tests/test_client.py -k metalink` |
| 5 | Refactor `add_torrent` to delegate to `_build_torrent_params` | `download.py` | 3 | `pytest tests/test_client.py -k torrent` |
| 6 | Extract `_do_request(payload)` in HttpTransport | `http.py` | — | `pytest tests/test_http.py -v` |
| 7 | Refactor `send_request` to delegate to `_do_request` | `http.py` | 6 | `pytest tests/test_http.py -v` |
| 8 | Extract `_init_sub_managers()` in Aria2Client | `client/__init__.py` | — | `pytest tests/test_client.py -v` |
| 9 | Refactor `__init__` to call `_init_sub_managers()` | `client/__init__.py` | 8 | `pytest tests/test_client.py -v` |
| 10 | Full verification suite | All 3 files | 5, 7, 9 | See below |

---

## Full Verification Suite (Task 10)

```bash
uv run python scripts/lint/wc-lint.py packages/aria2-sdk/src/aria2/client/
uv run ruff check packages/aria2-sdk/src/aria2/client/
uv run ty check packages/aria2-sdk/src/
uv run pytest -x -q -m "not integration" tests/
```

---

## Review Workload Forecast

| Metric | Value |
|---|---|
| Estimated new lines | ~35 (helpers) |
| Estimated modified lines | ~25 (refactored methods) |
| Estimated total | ~60 |
| Review budget | 400 lines |
| Chained PRs recommended | **No** — single PR |

---

## Notes

- `_build_torrent_params` must use `[]` placeholder (not `{}`) when `uris` is provided,
  `position` is provided, but `options` is not. Test `test_add_torrent_with_uris_position`
  asserts `params[2] == []`.
- No test modifications needed. All existing tests exercise the public API.
- Zero behavioral changes.
