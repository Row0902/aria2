# Aria2 Python Wrapper — SDD Design

## 1. Architecture

```
┌─────────────────────────────────────────────────────┐
│                   User Code                          │
└──────────┬──────────────────────────┬───────────────┘
           │                          │
           ▼                          ▼
    Aria2Client ─── 5 sub-managers    CLI (args)
    (lifecycle)   │   │   │   │   │
                  │   │   │   │   │
     ┌────────────┘   │   │   │   └──────────┐
     ▼                ▼   ▼   ▼              ▼
  DownloadMgr   StatusMgr  OptionsMgr   SystemMgr  EventMgr
  (9 methods)   (9 meth)   (4 meth)     (9 meth)   (6 meth)
     │                │       │             │
     └────────────────┴───────┴─────────────┘
                    │
                    ▼
              _request()
              (transport dispatch)
                    │
           ┌────────┴────────┐
           ▼                  ▼
    WebSocketTransport    HttpTransport
    (preferred + events)  (fallback)
           │                  │
           └──────┬───────────┘
                  ▼
           aria2c daemon
           (JSON-RPC :6800)
```

## 2. Design Decisions

### 2.1 Sub-manager Pattern (Aria2Client split)

**Decision**: Split Aria2Client from 41 public methods into a thin lifecycle wrapper + 5 specialized sub-managers.

**Motivation**: CODE-REVIEW-RULES.md Rule 5 limits classes to ≤ 10 public methods.
The client had 41. Each manager now has ≤ 9 public methods.

**Pattern**:
- Aria2Client owns transports and `_request()` dispatch
- Each manager receives a `_request` callable at construction
- Managers are exposed as `@property` on the client
- EventManager shares the `_callbacks` dict with the client's `_on_event()` dispatcher

### 2.2 Dual Transport

**Decision**: WebSocket primary, HTTP fallback. The WS transport auto-reconnects
with exponential backoff.

**Rationale**: WS provides push notifications (events) without polling.
HTTP is always available as fallback for request/response operations.

### 2.3 Discriminated Unions for Status

**Decision**: Pydantic `Discriminator` + `Annotated[Union[...]]` for download status parsing.

**Rationale**: Avoids manual `if/elif/else` chains for status variant selection (Rule 3).

### 2.4 One class per file (models)

**Decision**: Split `models/__init__.py` (14 public classes) into individual files
with one public class each.

**Rationale**: CODE-REVIEW-RULES.md Rule 4. Each file is independently reviewable
and testable.

## 3. Error Handling

```
Aria2Error
├── Aria2ConnectionError    (network failures)
├── Aria2AuthError          (authentication)
├── Aria2RpcError           (JSON-RPC errors from daemon)
└── Aria2BinaryNotFoundError (missing aria2c binary)
```

- All third-party exceptions (httpx, websockets, json) are wrapped in Aria2Error
  subtypes before reaching user code.
- `except Aria2RpcError: raise` passthrough in transports ensures typed errors.

## 4. Concurrency Model

- Single event loop (asyncio)
- `asyncio.TaskGroup` for coordinated tasks (future)
- `asyncio.timeout()` for all network operations
- WebSocket reader runs as a single `asyncio.Task`
- No threading, no multiprocessing

## 5. Binary Bundling

- Build hook downloads pre-compiled static binary from abcfy2/aria2-static-build
  (tag 1.37.0) for detected platform
- 7 platform targets: Linux x86_64/aarch64/armv7l/armv6l/i686 + Windows AMD64/x86
- In-wheel location: `aria2/bin/aria2c-{platform}`
- Runtime fallback: `aria2c` on PATH for development or unsupported platforms
