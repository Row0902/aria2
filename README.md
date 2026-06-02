# aria2

> The best SDK for [aria2](https://aria2.github.io/) — async JSON-RPC client for Python 3.14+ with WebSocket events, full static typing, and bundled binary.

```python
import asyncio
from aria2 import Aria2Client, DownloadStatus

async def main():
    async with Aria2Client(secret="mytoken") as client:
        gid = await client.downloads.add_uri(["https://example.com/file.zip"])
        status = await client.status.tell_status(gid)
        print(f"Progress: {status.progress_pct:.1f}%")
        print(f"Speed: {status.speed_kbps:.0f} KB/s")

asyncio.run(main())
```

## Features

- 🚀 **Async** — built on `asyncio`, `httpx`, and `websockets`
- 🔌 **Dual transport** — WebSocket primary, HTTP fallback
- 🔔 **Push events** — download start/pause/stop/complete/error via WebSocket
- 📦 **Binary bundling** — ships with aria2c (linux x86_64)
- 🎯 **Full static typing** — pydantic models, StrEnums, type-checked via `ty`
- 🛡️ **Error hierarchy** — `Aria2RpcError`, `Aria2ConnectionError`, etc.
- 📋 **CLI** — `aria2 start`, `aria2 status`, `aria2 check`
- 🧩 **Sub-manager API** — <10 public methods per class (downloads, status, options, system, events)

## Quickstart

### Install

```bash
pip install aria2-sdk
```

Requires Python ≥3.14. Dependencies: `httpx`, `pydantic`, `websockets`.

### Usage

```python
import asyncio
from aria2 import Aria2Client

async def main():
    async with Aria2Client(host="localhost", port=6800, secret="mytoken") as c:
        # Add a download
        gid = await c.downloads.add_uri(["https://example.com/video.mp4"])

        # Check status
        status = await c.status.tell_status(gid)
        print(f"Status: {status.status}")
        print(f"Progress: {status.progress_pct:.1f}%")
        print(f"Speed: {status.speed_kbps:.0f} KB/s")

        # Control
        await c.downloads.pause(gid)
        await c.downloads.unpause(gid)
        await c.downloads.remove(gid, force=True)

        # Global stats
        stat = await c.status.get_global_stat()
        print(f"Global speed: {stat.download_speed_kbps:.0f} KB/s")

        # System info
        version = await c.system.get_version()
        print(f"aria2 version: {version.version}")

asyncio.run(main())
```

### Event callbacks (WebSocket)

```python
from aria2 import Aria2Client

def on_start(gid: str) -> None:
    print(f"Download started: {gid}")

def on_complete(gid: str) -> None:
    print(f"Download complete: {gid}")

async with Aria2Client(secret="mytoken") as client:
    client.events.on_download_start(on_start)
    client.events.on_download_complete(on_complete)
    gid = await client.downloads.add_uri(["https://example.com/file.zip"])
    await asyncio.sleep(10)
```

## API

### Client lifecycle

```python
# Context manager (recommended)
async with Aria2Client(secret="token") as client:
    ...

# Manual
client = Aria2Client(secret="token")
await client.connect()
...
await client.close()
```

### Constructor

```python
Aria2Client(
    host: str = "localhost",
    port: int = 6800,
    secret: str | None = None,
    *,
    enable_ws: bool = True,
    timeout: float = 30.0,
)
```

### Sub-managers

All domain operations are grouped into 5 sub-managers, each with ≤10 public methods:

| Manager | Property | Methods | Description |
|---------|----------|---------|-------------|
| `DownloadManager` | `client.downloads` | 9 | Add, remove, pause, control downloads |
| `StatusManager` | `client.status` | 9 | Query download status, files, peers |
| `OptionsManager` | `client.options` | 4 | Get/set per-download and global options |
| `SystemManager` | `client.system` | 9 | Daemon version, session, shutdown |
| `EventManager` | `client.events` | 6 | Register WebSocket event callbacks |

### Downloads

```python
# Add
gid = await client.downloads.add_uri(["https://example.com/file.zip"])
gid = await client.downloads.add_torrent(torrent_bytes, uris=["https://..."])
gids = await client.downloads.add_metalink(metalink_bytes)

# Control
await client.downloads.remove(gid, force=True)
await client.downloads.pause(gid)
await client.downloads.pause_all()
await client.downloads.unpause(gid)
await client.downloads.unpause_all()
await client.downloads.change_position(gid, 1, "POS_CUR")
```

### Status

```python
# Single download
status = await client.status.tell_status(gid)
status.progress_pct      # float
status.speed_kbps        # float
status.is_active         # bool
status.is_complete       # bool

# Batches
active = await client.status.tell_active()
waiting = await client.status.tell_waiting(offset=0, num=10)
stopped = await client.status.tell_stopped(offset=0, num=10)

# Details
files = await client.status.get_files(gid)       # list[FileInfo]
uris = await client.status.get_uris(gid)         # list[UriInfo]
servers = await client.status.get_servers(gid)   # list[ServerInfo]
peers = await client.status.get_peers(gid)       # list[PeerInfo]
stat = await client.status.get_global_stat()     # GlobalStat
```

### Options

```python
opts = await client.options.get_option(gid)           # dict[str, str]
await client.options.change_option(gid, {"max-connection-per-server": "4"})

global_opts = await client.options.get_global_option()
await client.options.change_global_option({"max-concurrent-downloads": "5"})
```

### System

```python
version = await client.system.get_version()         # Aria2Version
info = await client.system.get_session_info()       # dict[str, str]
methods = await client.system.list_methods()        # list[str]
notifications = await client.system.list_notifications()  # list[str]

await client.system.shutdown()
await client.system.save_session()
await client.system.purge_download_result()
await client.system.remove_download_result(gid)

# Batch RPC calls
results = await client.system.multicall([
    {"methodName": "aria2.tellStatus", "params": [gid]},
    {"methodName": "aria2.getGlobalStat"},
])
```

### Errors

```python
from aria2 import Aria2Error, Aria2ConnectionError, Aria2RpcError

try:
    status = await client.status.tell_status("invalid-gid")
except Aria2RpcError as e:
    print(f"RPC error [{e.code}]: {e.message}")
except Aria2ConnectionError:
    print("Cannot connect to aria2")
```

### Models (pydantic)

All status methods return pydantic `BaseModel` instances with typed fields and
convenience properties:

```python
status = await client.status.tell_status(gid)
status.progress_pct      # float: 0.0–100.0
status.speed_kbps        # float: download speed in KB/s
status.is_active         # bool
status.is_complete       # bool
status.is_error          # bool

stat = await client.status.get_global_stat()
stat.download_speed_kbps # float
stat.upload_speed_kbps   # float
```

Download status responses use a **discriminated union** — each status variant
(`ActiveStatus`, `PausedStatus`, `ErrorStatus`, `CompleteStatus`, `RemovedStatus`)
is its own model, selected automatically at parse time:

```python
status = await client.status.tell_status(gid)
match status.status:
    case DownloadStatus.ACTIVE:
        print(f"Downloading: {status.progress_pct:.1f}%")
    case DownloadStatus.COMPLETE:
        print(f"Completed at {status.completed_time}")
```

## CLI

```bash
# Start aria2c daemon
aria2 start --secret mytoken --dir /downloads

# Check binary
aria2 check

# Query running daemon
aria2 status --secret mytoken

# Start in background
aria2 start --secret mytoken --daemon
```

## Binary bundling

This package can bundle the `aria2c` binary inside the wheel. During build,
a Hatchling build hook downloads the pre-compiled static binary from
[abcfy2/aria2-static-build](https://github.com/abcfy2/aria2-static-build)
for the detected platform.

At runtime, the SDK discovers the binary by trying:
1. Bundled binary (wheel install)
2. System `aria2c` from `PATH`

```python
from aria2.bin import get_binary_path, get_binary_version

path = get_binary_path()       # Path to aria2c
ver = get_binary_version()     # Release tag (e.g. "release-1.37.0")
```

## Development

```bash
# Setup
uv sync

# Type checking
ty check src/aria2/

# Lint
ruff check src tests

# Tests
uv run pytest tests/
```

### Project structure

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

## License

MIT
