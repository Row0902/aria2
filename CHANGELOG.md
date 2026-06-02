# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Integration test fixture (`tests/conftest.py`) — auto-discovers bundled
  or system aria2c binary, starts daemon with temp config and random port,
  provides connected ``Aria2Client``
- 17 integration tests covering:
  - Basic connectivity and daemon version
  - ``add_uri`` with options and position
  - ``add_torrent`` with inline minimal torrent data
  - ``add_torrent`` with web seed URIs and per-download options
  - ``add_metalink`` with minimal Metalink v4 XML
  - Full lifecycle: pause → unpause → remove
  - ``pause_all`` / ``unpause_all``
  - Queue reordering via ``change_position``
  - Global stats, RPC method listing, session info
  - ``system.multicall`` batch requests
- All integration tests skip gracefully when aria2c binary is unavailable

## [0.1.0] — 2026-06-02

### Added

- Async JSON-RPC client (`Aria2Client`) with 5 sub-managers:
  - `DownloadManager` — add/remove/pause/unpause downloads (9 methods)
  - `StatusManager` — query status, files, URIs, peers, servers (9 methods)
  - `OptionsManager` — get/set per-download and global options (4 methods)
  - `SystemManager` — version, session, shutdown, multicall (9 methods)
  - `EventManager` — WebSocket event callback registration (6 methods)
- Dual transport: WebSocket (primary, with event dispatch) and HTTP (fallback via `httpx`)
- WebSocket auto-reconnect with exponential backoff
- Pydantic v2 models with discriminated unions for 5 download status variants
  (`ActiveStatus`, `PausedStatus`, `ErrorStatus`, `CompleteStatus`, `RemovedStatus`)
- 14 Pydantic models covering all aria2 data structures (FileInfo, UriInfo, PeerInfo,
  ServerInfo, BittorrentInfo, GlobalStat, Aria2Version, SessionInfo)
- Full aria2 JSON-RPC method coverage (42 methods mapped to RPC calls)
- `system.multicall` support with automatic secret injection per sub-call
- CLI entry point (`aria2` command) for daemon management:
  - `aria2 start` — start aria2c daemon
  - `aria2 check` — verify binary availability
  - `aria2 status` — query running daemon
- Binary bundling via Hatchling build hook:
  - Downloads pre-compiled static binary from `abcfy2/aria2-static-build`
  - Supports 7 platform targets (Linux x86_64/aarch64/arm, Windows AMD64/x86)
  - Runtime discovery: bundled binary first, then system `PATH`
- Error hierarchy: `Aria2Error` → `Aria2ConnectionError`, `Aria2AuthError`,
  `Aria2RpcError`, `Aria2BinaryNotFoundError`
- Full static typing with `ty` (120+ rules, strict mode)
- `py.typed` marker for PEP 561 compliance
- Ruff linting with Google-style docstring conventions
- 25 project skills covering tools, patterns, and workflows
- CI/CD workflows: lint, type-check, test, release
- SDD artifacts: spec, design, tasks, verify report, archive

### Internal

- Project scaffolding with `uv` and `hatchling` build backend
- 56 tests across 5 test files (client, HTTP, WebSocket, RPC, errors)
- `CODE-REVIEW-RULES.md` with quality gates

[unreleased]: https://github.com/Row0902/aria2/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Row0902/aria2/releases/tag/v0.1.0
