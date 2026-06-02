# Aria2 Python Wrapper — SDD Tasks

## Implemented

| # | Task | File(s) | Status |
|---|------|---------|--------|
| 1 | Types (GID, DownloadStatus, PositionHow) | `src/aria2/types/__init__.py` | ✅ |
| 2 | Error hierarchy | `src/aria2/errors/__init__.py` | ✅ |
| 3 | Pydantic models (14 classes, one per file) | `src/aria2/models/*.py` | ✅ |
| 4 | Discriminated union for status | `src/aria2/models/download_response.py` | ✅ |
| 5 | JSON-RPC protocol helpers | `src/aria2/rpc/__init__.py` | ✅ |
| 6 | HTTP transport | `src/aria2/client/transport/http.py` | ✅ |
| 7 | WebSocket transport + auto-reconnect + events | `src/aria2/client/transport/ws.py` | ✅ |
| 8 | Aria2Client (lifecycle only) | `src/aria2/client/__init__.py` | ✅ |
| 9 | DownloadManager (9 methods) | `src/aria2/client/download.py` | ✅ |
| 10 | StatusManager (9 methods) | `src/aria2/client/status.py` | ✅ |
| 11 | OptionsManager (4 methods) | `src/aria2/client/options.py` | ✅ |
| 12 | SystemManager (9 methods) | `src/aria2/client/system.py` | ✅ |
| 13 | EventManager (6 methods) | `src/aria2/client/events.py` | ✅ |
| 14 | Public re-exports | `src/aria2/__init__.py` | ✅ |
| 15 | Binary discovery | `src/aria2/bin/__init__.py` | ✅ |
| 16 | CLI entry point | `src/aria2/__main__.py`, `src/aria2/cli/__init__.py` | ✅ |
| 17 | Build hook (abcfy2 static builds) | `hatch_build.py` | ✅ |
| 18 | pyproject.toml | `pyproject.toml` | ✅ |
| 19 | Tests: RPC protocol | `tests/test_rpc.py` | ✅ |
| 20 | Tests: HTTP transport | `tests/test_http.py` | ✅ |
| 21 | Tests: WebSocket transport | `tests/test_ws.py` | ✅ |
| 22 | Tests: Client + sub-managers | `tests/test_client.py` | ✅ |
| 23 | Tests: Errors | `tests/test_errors.py` | ✅ |
| 24 | CI: lint (ruff) | `.github/workflows/lint.yml` | ✅ |
| 25 | CI: type-check (ty) | `.github/workflows/typecheck.yml` | ✅ |
| 26 | CI: test (pytest) | `.github/workflows/test.yml` | ✅ |
| 27 | CI: release to PyPI | `.github/workflows/release.yml` | ✅ |

## Pending

| # | Task | Notes |
|---|------|-------|
| 1 | README.md | Usage docs, API reference, examples |
| 2 | Integration test fixture | Auto-start aria2c daemon for CI |
| 3 | Torrent functional test | With actual .torrent URL |
| 4 | `add_torrent` with web seed URIs | Uncommon parameter combination |
| 5 | CHANGELOG update | Version history for releases |
