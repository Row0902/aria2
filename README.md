<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://img.shields.io/badge/python-3.14+-blue?style=for-the-badge&logo=python&logoColor=white&labelColor=1a1a2e">
  <img alt="Python 3.14+" src="https://img.shields.io/badge/python-3.14+-blue?style=for-the-badge&logo=python&logoColor=white">
</picture>
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://img.shields.io/pypi/v/aria2-sdk?style=for-the-badge&logo=pypi&logoColor=white&labelColor=1a1a2e">
  <img alt="PyPI" src="https://img.shields.io/pypi/v/aria2-sdk?style=for-the-badge&logo=pypi">
</picture>
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://img.shields.io/github/actions/workflow/status/Row0902/aria2/lint.yml?style=for-the-badge&logo=github&logoColor=white&labelColor=1a1a2e&label=lint">
  <img alt="Lint" src="https://img.shields.io/github/actions/workflow/status/Row0902/aria2/lint.yml?style=for-the-badge&label=lint">
</picture>
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://img.shields.io/github/actions/workflow/status/Row0902/aria2/test.yml?style=for-the-badge&logo=github&logoColor=white&labelColor=1a1a2e&label=test">
  <img alt="Test" src="https://img.shields.io/github/actions/workflow/status/Row0902/aria2/test.yml?style=for-the-badge&label=test">
</picture>
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://img.shields.io/github/actions/workflow/status/Row0902/aria2/typecheck.yml?style=for-the-badge&logo=github&logoColor=white&labelColor=1a1a2e&label=typecheck">
  <img alt="TypeCheck" src="https://img.shields.io/github/actions/workflow/status/Row0902/aria2/typecheck.yml?style=for-the-badge&label=typecheck">
</picture>
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://img.shields.io/badge/license-MIT-green?style=for-the-badge&labelColor=1a1a2e">
  <img alt="MIT" src="https://img.shields.io/badge/license-MIT-green?style=for-the-badge">
</picture>

<br>
<br>

<h1 align="center">aria2-sdk</h1>
<p align="center"><strong>Async Python SDK for the aria2 download daemon — real-time events, static typing, and a bundled binary, ready in one <code>pip install</code>.</strong></p>

---

```python
import asyncio
from aria2 import Aria2Client

async def main():
    async with Aria2Client(secret="mytoken") as client:
        # Add a download, check progress, print live speed
        gid = await client.downloads.add_uri(["https://example.com/video.mp4"])
        status = await client.status.tell_status(gid)
        print(f"⏬ {status.progress_pct:.1f}% · {status.speed_kbps:.0f} KB/s")
        print(f"📁 {status.total_length_human} → {status.completed_length_human}")

asyncio.run(main())
```

---

## Quick start

```bash
pip install aria2-sdk
```

Make sure `aria2c` is running (or use the bundled binary via the CLI):

```bash
aria2 start --secret mytoken --daemon
```

Then open a Python shell or script:

```python
import asyncio
from aria2 import Aria2Client

async def quick_demo():
    async with Aria2Client(secret="mytoken") as client:
        gid = await client.downloads.add_uri(["https://example.com/file.zip"])
        status = await client.status.tell_status(gid)
        print(f"Status: {status.status.value}")
        print(f"Progress: {status.progress_pct:.1f}%")

asyncio.run(quick_demo())
```

> **Requires Python ≥3.14.** Dependencies: `httpx`, `pydantic`, `websockets`.

---

## Why aria2-sdk?

[aria2](https://aria2.github.io/) is one of the fastest download utilities ever written — it supports HTTP/HTTPS, BitTorrent, Metalink, multi-connection downloads, and runs as a lightweight JSON-RPC daemon. But talking to the daemon directly means writing your own client code, managing WebSocket reconnection, handling JSON-RPC 2.0 serialization, and parsing every response by hand.

**aria2-sdk gives you a modern, typed Python interface to aria2 in a single import:**

| Instead of this… | …you write this |
|---|---|
| Manual JSON-RPC over HTTP | `client.downloads.add_uri([url])` |
| Parse status from raw dicts | `status.progress_pct`, `status.speed_kbps` |
| Build your own event loop | `client.events.on_download_complete(cb)` |
| Handle disconnects yourself | Built-in WebSocket reconnection |
| Find aria2c binary manually | Bundled binary + auto-discovery |
| Roll your own error handling | `Aria2RpcError`, `Aria2ConnectionError` |

---

## Key features

| | Feature | What it means for you |
|---|---|---|
| ⚡ | **Async-first** | Built on `asyncio` — non-blocking, concurrent downloads |
| 🔌 | **Dual transport** | WebSocket by default, transparent HTTP fallback |
| 🔔 | **Push events** | Subscribe to download start/pause/complete/error in real time |
| 🧩 | **Sub-manager API** | 5 focused managers — no 40-method monster object |
| 🎯 | **Fully typed** | pydantic models, StrEnums, `ty`-checkable — catches mistakes before runtime |
| 📦 | **Binary bundling** | Ships with static `aria2c` 1.37.0 (linux x86_64) — no system install needed |
| 🛡️ | **Rich error hierarchy** | Catch `Aria2ConnectionError` separate from `Aria2RpcError` |
| 📋 | **TUI-friendly CLI** | `aria2 start`, `aria2 status`, `aria2 check` — zero-config startup |
| ✅ | **Tested** | 119 tests, 86% coverage, real integration tests against live aria2c |

---

## Feature highlights

### Real-time download events

Register callbacks for download lifecycle events — no polling required:

```python
from aria2 import Aria2Client

def on_complete(gid: str) -> None:
    print(f"✅ Download finished: {gid}")

def on_error(gid: str) -> None:
    print(f"❌ Download failed: {gid}")

async with Aria2Client(secret="mytoken") as client:
    client.events.on_download_complete(on_complete)
    client.events.on_download_error(on_error)
    gid = await client.downloads.add_uri(["https://example.com/file.zip"])
    await asyncio.sleep(30)  # events fire as they happen
```

### Clean batch operations

Multi-call, pause-all, query batches — all in one async call:

```python
# Pause everything
await client.downloads.pause_all()
await client.downloads.unpause_all()

# Batch RPC (system.multicall)
results = await client.system.multicall([
    {"methodName": "aria2.tellStatus", "params": [gid]},
    {"methodName": "aria2.getGlobalStat"},
])

# Query all download states
active = await client.status.tell_active()
waiting = await client.status.tell_waiting(offset=0, num=50)
stopped = await client.status.tell_stopped(offset=0, num=50)
```

### Runtime metadata

Every download status is a pydantic model with typed convenience properties:

```python
status = await client.status.tell_status(gid)
status.progress_pct      # float: 0.0–100.0
status.speed_kbps        # float: download speed in KB/s
status.total_length_human  # str: "1.2 GiB"
status.is_active         # bool
status.is_complete       # bool

match status.status:
    case DownloadStatus.ACTIVE:
        print(f"⏬ {status.progress_pct:.1f}% @ {status.speed_kbps:.0f} KB/s")
    case DownloadStatus.COMPLETE:
        print(f"✅ Done at {status.completed_time}")
```

### No-system-install mode

The package ships a static musl build of aria2c 1.37.0. No need to compile or install aria2 system-wide — it just works:

```bash
aria2 start --secret mytoken --daemon   # uses bundled binary
aria2 check                              # verify binary is usable
```

At runtime, the SDK discovers the binary automatically (bundled → system PATH):

```python
from aria2.bin import get_binary_path, get_binary_version
path = get_binary_path()        # Path to aria2c
ver = get_binary_version()      # e.g. "release-1.37.0"
```

---

## Comparison

| | aria2-sdk | Raw `httpx` + JSON-RPC | Other Python wrappers |
|---|---|---|---|
| **WebSocket events** | ✅ Built-in | ❌ Manual | ❌ Most don't |
| **Static typing** | ✅ pydantic + `ty` | ❌ Raw dicts | ⚠️ Partial |
| **Error hierarchy** | ✅ Structured | ❌ HTTP errors | ⚠️ Basic |
| **Binary bundling** | ✅ Yes | — | ❌ No |
| **Async** | ✅ `asyncio` | ✅ Manual | ⚠️ Varies |
| **Sub-manager API** | ✅ Yes | — | ❌ Monolithic |
| **CLI** | ✅ Included | — | ❌ No |
| **Integration tests** | ✅ Against live daemon | — | ⚠️ Rare |

---

## Project status

**v0.1.0** — first production-ready release. The complete JSON-RPC 2.0 API is covered (add, remove, pause, tellStatus, getGlobalStat, multicall, options, BitTorrent, WebSocket notifications). All features are documented and tested.

**[CHANGELOG](CHANGELOG.md)** — [Contributing](CONTRIBUTING.md) — **MIT License**

### Upcoming

- Windows + macOS binary bundling
- Connection pooling / multi-daemon support
- Download queue management
- Structured logging integration
- Download progress bar (rich/tqdm)

---

*Built with Python 3.14, `asyncio`, `httpx`, `pydantic`, `websockets`, and a lot of ❤️ for download management.*
