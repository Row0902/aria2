# Aria2 Python Wrapper — SDD Spec

## 1. Overview

Async Python 3.14+ wrapper for aria2's JSON-RPC interface. Dual-transport: HTTP for
request/response, WebSocket for push notifications. Full static typing with Pydantic
discriminated unions and StrEnum types for all aria2 data structures.

## 2. Module Structure

```
src/aria2/
├── __init__.py              # Public API re-exports (Aria2Client, models, types, errors)
├── __main__.py              # CLI entry point (`aria2` command)
├── py.typed                 # PEP 561 marker
├── types/__init__.py        # GID (NewType), DownloadStatus (StrEnum), PositionHow
├── errors/__init__.py       # Exception hierarchy (Aria2Error, Aria2ConnectionError, ...)
├── models/                  # Pydantic models — one public class per file
│   ├── __init__.py          # Re-exports all models
│   ├── uri.py               # UriInfo
│   ├── file.py              # FileInfo
│   ├── peer.py              # PeerInfo
│   ├── server.py            # ServerInfo
│   ├── bittorrent.py        # BittorrentInfo
│   ├── base.py              # _BaseDownloadStatus (private base)
│   ├── status_active.py     # ActiveStatus
│   ├── status_paused.py     # PausedStatus
│   ├── status_error.py      # ErrorStatus
│   ├── status_complete.py   # CompleteStatus
│   ├── status_removed.py    # RemovedStatus
│   ├── download_response.py # DownloadStatusResponse (discriminated union) + _parse_status
│   ├── global_stat.py       # GlobalStat
│   ├── version.py           # Aria2Version
│   └── session.py           # SessionInfo
├── rpc/__init__.py          # JSON-RPC 2.0 helpers: build_request, parse_response
├── bin/__init__.py          # Bundled aria2c binary discovery
├── cli/__init__.py          # CLI commands (start, stop, status)
└── client/
    ├── __init__.py           # Aria2Client (lifecycle only — connect, close, sub-manager properties)
    ├── _helpers.py           # Internal utilities (snake_case key conversion)
    ├── download.py           # DownloadManager — 9 public methods
    ├── status.py             # StatusManager — 9 public methods
    ├── options.py            # OptionsManager — 4 public methods
    ├── system.py             # SystemManager — 9 public methods
    ├── events.py             # EventManager — 6 public methods
    └── transport/
        ├── __init__.py       # Transport ABC
        ├── http.py           # HttpTransport
        └── ws.py             # WebSocketTransport (with auto-reconnect + events)
```

## 3. Public API

```python
class Aria2Client:
    # Lifecycle (≤ 10 public)
    async def connect(self) -> None
    async def close(self) -> None
    async def __aenter__(self) -> Aria2Client
    async def __aexit__(self, ...) -> None

    # Properties providing sub-managers
    @property downloads -> DownloadManager
    @property status -> StatusManager
    @property options -> OptionsManager
    @property system -> SystemManager
    @property events -> EventManager

class DownloadManager:
    # 9 public methods
    async def add_uri(...) -> str
    async def add_torrent(...) -> str
    async def add_metalink(...) -> list[str]
    async def remove(gid, force) -> str
    async def pause(gid, force) -> str
    async def pause_all(force) -> str
    async def unpause(gid) -> str
    async def unpause_all() -> str
    async def change_position(gid, pos, how) -> int

class StatusManager:
    # 9 public methods
    async def tell_status(gid, keys) -> DownloadStatusResponse
    async def tell_active(keys) -> list[DownloadStatusResponse]
    async def tell_waiting(offset, num, keys) -> list[DownloadStatusResponse]
    async def tell_stopped(offset, num, keys) -> list[DownloadStatusResponse]
    async def get_files(gid) -> list[FileInfo]
    async def get_uris(gid) -> list[UriInfo]
    async def get_servers(gid) -> list[ServerInfo]
    async def get_peers(gid) -> list[PeerInfo]
    async def get_global_stat() -> GlobalStat

class OptionsManager:
    # 4 public methods
    async def get_option(gid) -> dict
    async def change_option(gid, options) -> str
    async def get_global_option() -> dict
    async def change_global_option(options) -> str

class SystemManager:
    # 9 public methods
    async def get_version() -> Aria2Version
    async def get_session_info() -> dict
    async def shutdown(force) -> str
    async def save_session() -> str
    async def purge_download_result() -> str
    async def remove_download_result(gid) -> str
    async def list_methods() -> list[str]
    async def list_notifications() -> list[str]
    async def multicall(calls) -> list

class EventManager:
    # 6 public methods
    def on_download_start(callback) -> None
    def on_download_pause(callback) -> None
    def on_download_stop(callback) -> None
    def on_download_complete(callback) -> None
    def on_download_error(callback) -> None
    def on_bt_download_complete(callback) -> None
```

## 4. Data Flow

```
User Code
  │
  ▼
Aria2Client  ──►  Sub-manager  ──►  _request()  ──►  WebSocketTransport (preferred)
                                                       └── HttpTransport (fallback)
                                                              │
                                                              ▼
                                                         aria2c daemon
                                                         (JSON-RPC on port 6800)
```

Notifications flow:
- WebSocket reader loop receives JSON-RPC notifications
- `_on_event()` dispatches to registered callbacks via `_callbacks` dict
- EventManager provides the registration API

## 5. Discriminated Unions

All 5 download status variants (ActiveStatus, PausedStatus, ErrorStatus, CompleteStatus,
RemovedStatus) are parsed via a Pydantic discriminated union (`DownloadStatusResponse`)
using a custom `_status_discriminator` function.

## 6. Transport

- **WebSocket**: primary transport via `websockets` library. Auto-reconnect with
  exponential backoff. Push notification dispatch.
- **HTTP**: fallback transport via `httpx`. Used when WebSocket fails or is disabled.
