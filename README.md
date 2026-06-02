# aria2

> The best SDK for [aria2](https://aria2.github.io/) — async JSON-RPC client for Python 3.14+ with WebSocket events, full static typing, and bundled binary.

```python
import asyncio
from aria2 import Aria2Client, DownloadStatus

async def main():
    async with Aria2Client(secret="mytoken") as client:
        gid = await client.add_uri(["https://example.com/file.zip"])
        status = await client.tell_status(gid)
        print(f"Progress: {status.progress_pct:.1f}%")
        print(f"Speed: {status.speed_kbps:.0f} KB/s")

asyncio.run(main())
```

## Features

- 🚀 **Async** — built on `asyncio`, `httpx`, and `websockets`
- 🔌 **Dual transport** — WebSocket primary, HTTP fallback
- 🔔 **Push events** — download start/pause/stop/complete/error via WebSocket
- 📦 **Binary bundling** — ships with aria2c (linux x86_64)
- 🎯 **Full static typing** — pydantic models, StrEnums, type-checked
- 🛡️ **Error hierarchy** — `Aria2RpcError`, `Aria2ConnectionError`, etc.
- 📋 **CLI** — `aria2 start`, `aria2 status`, `aria2 check`
- 📖 **42 RPC methods** — full aria2 JSON-RPC coverage

## Quickstart

### Install

```bash
pip install aria2
```

Requires Python ≥3.14. Dependencies: `httpx`, `pydantic`, `websockets`.

### Usage

```python
import asyncio
from aria2 import Aria2Client

async def main():
    async with Aria2Client(host="localhost", port=6800, secret="mytoken") as c:
        # Add a download
        gid = await c.add_uri(["https://example.com/video.mp4"])

        # Check status
        status = await c.tell_status(gid)
        print(f"Status: {status.status}")
        print(f"Progress: {status.progress_pct:.1f}%")
        print(f"Speed: {status.speed_kbps:.0f} KB/s")

        # Control
        await c.pause(gid)
        await c.unpause(gid)
        await c.remove(gid, force=True)

asyncio.run(main())
```

### Event callbacks (WebSocket)

```python
def on_start(gid: str) -> None:
    print(f"Download started: {gid}")

def on_complete(gid: str) -> None:
    print(f"Download complete: {gid}")

async with Aria2Client(secret="mytoken") as client:
    client.on_download_start(on_start)
    client.on_download_complete(on_complete)
    gid = await client.add_uri(["https://example.com/file.zip"])
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

### Methods

**Download addition**

| Method | RPC |
|--------|-----|
| `add_uri(uris, options?, position?)` | `aria2.addUri` |
| `add_torrent(torrent, uris?, options?, position?)` | `aria2.addTorrent` |
| `add_metalink(metalink, options?, position?)` | `aria2.addMetalink` |

**Download control**

| Method | RPC |
|--------|-----|
| `remove(gid, force=False)` | `aria2.remove` / `aria2.forceRemove` |
| `pause(gid, force=False)` | `aria2.pause` / `aria2.forcePause` |
| `pause_all(force=False)` | `aria2.pauseAll` / `aria2.forcePauseAll` |
| `unpause(gid)` | `aria2.unpause` |
| `unpause_all()` | `aria2.unpauseAll` |
| `change_position(gid, pos, how)` | `aria2.changePosition` |

**Status retrieval**

| Method | Returns |
|--------|---------|
| `tell_status(gid, keys?)` | `DownloadStatusResponse` |
| `tell_active(keys?)` | `list[DownloadStatusResponse]` |
| `tell_waiting(offset, num, keys?)` | `list[DownloadStatusResponse]` |
| `tell_stopped(offset, num, keys?)` | `list[DownloadStatusResponse]` |
| `get_files(gid)` | `list[FileInfo]` |
| `get_uris(gid)` | `list[UriInfo]` |
| `get_servers(gid)` | `list[ServerInfo]` |
| `get_peers(gid)` | `list[PeerInfo]` |
| `get_global_stat()` | `GlobalStat` |

**Options**

| Method | RPC |
|--------|-----|
| `get_option(gid)` | `aria2.getOption` |
| `change_option(gid, options)` | `aria2.changeOption` |
| `get_global_option()` | `aria2.getGlobalOption` |
| `change_global_option(options)` | `aria2.changeGlobalOption` |

**System**

| Method | Returns |
|--------|---------|
| `get_version()` | `Aria2Version` |
| `get_session_info()` | `dict[str, str]` |
| `shutdown(force=False)` | `str` |
| `save_session()` | `str` |
| `purge_download_result()` | `str` |
| `remove_download_result(gid)` | `str` |
| `list_methods()` | `list[str]` |
| `list_notifications()` | `list[str]` |
| `multicall(calls)` | `list[Any]` |

### Models (pydantic)

All status methods return pydantic `BaseModel` instances with convenience properties:

```python
status = await client.tell_status(gid)
status.progress_pct      # float: 0.0–100.0
status.speed_kbps        # float: download speed in KB/s
status.is_active         # bool
status.is_complete       # bool
status.is_error          # bool

stat = await client.get_global_stat()
stat.download_speed_kbps # float
stat.upload_speed_kbps   # float
```

### Errors

```python
from aria2 import Aria2Error, Aria2ConnectionError, Aria2RpcError

try:
    await client.tell_status("invalid-gid")
except Aria2RpcError as e:
    print(f"RPC error [{e.code}]: {e.message}")
except Aria2ConnectionError:
    print("Cannot connect to aria2")
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

This package can bundle the `aria2c` binary inside the wheel. During build:

1. The CI workflow compiles `aria2c` statically
2. A hatchling build hook downloads the binary from `Row0902/aria2-binaries`
3. The binary is included in the wheel under `aria2/bin/`

At runtime, the SDK tries:
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
uv sync --extra dev
uv pip install mypy pytest pytest-asyncio respx

# Type checking
ty check src/aria2/
mypy src/aria2/

# Lint
ruff check src tests

# Tests
uv run pytest tests/
```

### Project structure

```
src/aria2/
├── __init__.py          # Public API
├── __main__.py          # CLI entry point
├── bin/                 # Binary discovery
├── client.py            # Aria2Client (42 methods)
├── errors.py            # Error hierarchy
├── models.py            # Pydantic models
├── rpc.py               # JSON-RPC 2.0 protocol
├── transport/
│   ├── http.py          # HTTP via httpx
│   └── ws.py            # WebSocket + events
└── types.py             # GID, StrEnums
```

## License

MIT
