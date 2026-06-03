# Contributing

Thanks for your interest in aria2-sdk! This document covers the development setup and workflow.

## Setup

```bash
# Clone
git clone git@github.com:Row0902/aria2.git
cd aria2

# Sync dependencies
uv sync
```

## Development commands

```bash
# Type checking
ty check src/aria2/

# Lint + format
ruff check src tests
ruff format --check src

# Tests
uv run pytest tests/

# Coverage
uv run pytest --cov=src/aria2 --cov-report=term-missing tests/
```

## Project structure

```
src/aria2/
├── __init__.py           # Public API re-exports
├── __main__.py           # CLI entry point
├── py.typed              # PEP 561 marker
├── bin/
│   └── __init__.py       # Binary discovery
├── cli/
│   └── __init__.py       # CLI commands (start, stop, status)
├── client/
│   ├── __init__.py       # Aria2Client lifecycle
│   ├── download.py       # DownloadManager (9 methods)
│   ├── status.py         # StatusManager (9 methods)
│   ├── options.py        # OptionsManager (4 methods)
│   ├── system.py         # SystemManager (9 methods)
│   ├── events.py         # EventManager (6 methods)
│   ├── _helpers.py       # Internal utilities
│   └── transport/
│       ├── __init__.py   # Transport ABC
│       ├── http.py       # HTTP via httpx
│       └── ws.py         # WebSocket + events
├── errors/
│   └── __init__.py       # Error hierarchy
├── models/
│   ├── __init__.py       # Re-exports all models
│   ├── base.py           # _BaseDownloadStatus
│   ├── download_response.py  # Discriminated union
│   ├── file.py, uri.py, peer.py, server.py, bittorrent.py
│   ├── global_stat.py, version.py, session.py
│   └── status_active.py, status_complete.py, status_error.py,
│       status_paused.py, status_removed.py
├── rpc/
│   └── __init__.py       # JSON-RPC 2.0 protocol
└── types/
    └── __init__.py       # GID, DownloadStatus, PositionHow
```

## Branch strategy

See [BRANCH-STRATEGY.md](BRANCH-STRATEGY.md) — `main` is stable/prod, `develop` is canary, features branch from `develop`.

## Release

```bash
# Bump version in pyproject.toml, update CHANGELOG.md
# Tag and push
git tag v0.x.y
git push origin v0.x.y
# Then create a GitHub Release — the release workflow publishes to PyPI automatically.
```
