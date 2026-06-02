# Apply Progress — aria2 SDK Initial Implementation

## Change Description

Initial implementation of the aria2 Python SDK — async JSON-RPC client with
WebSocket events, full static typing, and bundled binary.

## Evidence

### File Structure

```
src/aria2/
├── __init__.py              # Public API re-exports
├── __main__.py              # CLI entry point (typer)
├── py.typed                 # PEP 561 marker
├── bin/__init__.py           # Bundled aria2c binary discovery
├── cli/__init__.py           # CLI commands
├── errors/__init__.py        # Error hierarchy (4 exception types)
├── models/
│   ├── __init__.py           # Re-exports all models
│   ├── base.py, bittorrent.py, download_response.py, file.py,
│   ├── global_stat.py, peer.py, server.py, session.py, uri.py,
│   │   version.py
│   └── status_active.py, status_complete.py, status_error.py,
│       status_paused.py, status_removed.py
├── rpc/__init__.py           # JSON-RPC 2.0 protocol helpers
├── types/__init__.py         # GID (NewType), DownloadStatus (StrEnum), PositionHow
└── client/
    ├── __init__.py           # Aria2Client (lifecycle only)
    ├── _helpers.py           # Key conversion utilities
    ├── download.py           # DownloadManager (9 methods)
    ├── status.py             # StatusManager (9 methods)
    ├── options.py            # OptionsManager (4 methods)
    ├── system.py             # SystemManager (9 methods)
    ├── events.py             # EventManager (6 methods)
    └── transport/
        ├── __init__.py       # Transport ABC
        ├── http.py           # HttpTransport (httpx)
        └── ws.py             # WebSocketTransport (websockets + events)
```

### Tests (5 files, 56 test functions)

| File | Tests | Coverage |
|------|-------|----------|
| tests/test_rpc.py | 12 tests (2 classes) | Types, RPC protocol helpers |
| tests/test_http.py | 6 tests | HTTP transport (respx) |
| tests/test_ws.py | 7 tests | WebSocket transport |
| tests/test_errors.py | 6 tests | Error hierarchy |
| tests/test_client.py | 25 tests | Client + all 5 sub-managers |

### CI/CD (4 workflows)

- `.github/workflows/lint.yml` — ruff check
- `.github/workflows/typecheck.yml` — ty type check
- `.github/workflows/test.yml` — pytest
- `.github/workflows/release.yml` — PyPI release

### Build

- `hatch_build.py` — downloads pre-built static binary from abcfy2/aria2-static-build
- `pyproject.toml` — hatchling config, dependencies, dev deps, CLI entry point
- Binary bundling: aria2c binary in `aria2_bin/` force-included in wheel

## Deviations from Spec/Design

| # | Deviation | Rationale |
|---|-----------|-----------|
| 1 | DownloadManager.remove returns `str` instead of `int` | Spec says `int` but aria2 RPC returns GID string. Implementation matches actual protocol. |
| 2 | SystemManager.__init__ receives `secret` param not in spec | Needed for multicall token injection (system.multicall requires secret per sub-call). |
| 3 | `__main__.py` missing from initial commit | Entry point declared in pyproject.toml but file was not created. Fixed post-verify. |

## Pending Tasks (from tasks.md)

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | README.md update | 🔲 | Still shows flat API (`client.add_uri`) instead of sub-manager API |
| 2 | Integration test fixture | 🔲 | Auto-start aria2c daemon for CI |
| 3 | Torrent functional test | 🔲 | With actual .torrent URL |
| 4 | add_torrent with web seed URIs | 🔲 | Edge case test |
| 5 | CHANGELOG update | 🔲 | Version history |

## Commands Run

```bash
# Lint
ruff check src/aria2/ tests/

# Type check
ty check src/aria2/

# Tests
uv run pytest tests/ -v
```

## Review Workload

- Total lines of code: ~2573 (src + tests)
- Files changed: 35+ Python files
- Single commit (initial) — no chaining needed
