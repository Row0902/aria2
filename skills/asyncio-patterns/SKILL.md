---
name: asyncio-patterns
description: "Trigger: asyncio, async, await, event loop, TaskGroup, gather, timeout, cancellation, asyncio patterns, concurrent. Async Python patterns for SDKs — tasks, timeouts, cancellation, and graceful shutdown."
license: Apache-2.0
metadata:
  author: gentleman-programming
  version: "1.0"
---

## When to Use

- Managing concurrent async tasks in the SDK (reader loop + RPC requests)
- Setting timeouts on RPC calls or operations
- Graceful shutdown of async connections
- Cancelling background tasks (WebSocket reader)
- Running multiple RPC calls concurrently
- Using `TaskGroup` for structured concurrency

## Critical Patterns

### Structured Concurrency with TaskGroup

Python 3.14's `TaskGroup` provides structured concurrency — if one task fails, all sibling tasks are cancelled:

```python
async def main():
    async with asyncio.TaskGroup() as tg:
        tg.create_task(reader_loop())
        tg.create_task(heartbeat())
    # Both tasks complete (or both fail) before this line
```

In the SDK, the WebSocket reader loop runs as a background task:

```python
async def connect(self) -> None:
    await self._ws.connect()
    self._reader_task = asyncio.create_task(self._reader_loop())

async def close(self) -> None:
    if self._reader_task:
        self._reader_task.cancel()
        try:
            await self._reader_task
        except asyncio.CancelledError:
            pass
```

### Cancellation Patterns

```python
async def _reader_loop(self) -> None:
    """Reader loop that respects cancellation."""
    try:
        async for raw in self._ws:
            self._dispatch(raw)
    except asyncio.CancelledError:
        # Clean up on cancellation
        await self._ws.close()
        raise  # Re-raise to propagate cancellation
    except websockets.ConnectionClosed:
        if self._should_reconnect:
            await self._reconnect()
```

Key rules:
- `asyncio.CancelledError` should almost always be re-raised (unless you're truly handling shutdown).
- Use `try/finally` for cleanup that must happen regardless of cancellation.
- Don't `except asyncio.CancelledError: pass` silently — it masks cancellation.

### Timeouts

```python
# asyncio.timeout (Python 3.14+)
async def rpc_call() -> Any:
    try:
        async with asyncio.timeout(30.0):
            return await transport.send_request(method, params)
    except TimeoutError:
        raise Aria2ConnectionError("RPC call timed out")

# Shorthand — asyncio.wait_for (older API)
result = await asyncio.wait_for(transport.send_request(method, params), timeout=30.0)
```

Use `asyncio.timeout()` for complex operations with multiple awaits:

```python
async def connect_with_timeout(self) -> None:
    try:
        async with asyncio.timeout(self._timeout):
            await self._ws.connect()
            self._reader_task = asyncio.create_task(self._reader_loop())
    except TimeoutError:
        raise Aria2ConnectionError(
            f"Connection timed out after {self._timeout}s"
        )
```

### Graceful Shutdown

```python
async def close(self) -> None:
    """Shut down the transport gracefully."""

    # 1. Stop accepting new work
    self._should_reconnect = False

    # 2. Cancel background tasks
    if self._reader_task and not self._reader_task.done():
        self._reader_task.cancel()
        try:
            await asyncio.wait_for(self._reader_task, timeout=5.0)
        except (asyncio.CancelledError, TimeoutError):
            pass

    # 3. Close transport
    if self._ws:
        await self._ws.close()
        self._ws = None
```

### Gathering Concurrent Calls

```python
# Multiple parallel RPC calls
results = await asyncio.gather(
    client.tell_status(gid1),
    client.tell_status(gid2),
    client.tell_status(gid3),
    return_exceptions=True,  # Don't fail all on one error
)

# Process results
for result in results:
    if isinstance(result, Exception):
        print(f"Failed: {result}")
    else:
        print(f"Status: {result}")
```

### Shield (protect from cancellation)

```python
async def critical_operation(self) -> None:
    """An operation that should not be cancelled."""
    try:
        result = await asyncio.shield(self._do_critical_work())
        return result
    except asyncio.CancelledError:
        # The shielded operation completed, but we still got cancelled
        raise
```

Use `asyncio.shield()` sparingly — it prevents cancellation of important cleanup.

### Event Dispatching

The SDK dispatches WebSocket notifications to callbacks:

```python
def _on_event(self, method: str, params: list[Any]) -> None:
    """Dispatch a notification to registered callbacks."""
    callbacks = self._callbacks.get(method, [])
    for cb in callbacks:
        try:
            cb(*params)
        except Exception:
            pass  # Don't let callback errors break the reader loop
```

For SDK callbacks, never let a callback exception propagate to the event dispatch loop.

### Event Loop Policy

```python
# Default: asyncio event loop
asyncio.run(main())  # Creates and manages event loop

# Custom policy for tests
@pytest_asyncio.fixture(scope="session")
def event_loop_policy():
    """Use uvloop for all tests."""
    import uvloop
    return uvloop.EventLoopPolicy()
```

### asyncio.run() vs Manual Loop

```python
# Simple — creates loop, runs, closes
asyncio.run(main())

# Manual (for frameworks or embedded)
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
try:
    loop.run_until_complete(main())
finally:
    loop.run_until_complete(loop.shutdown_asyncgens())
    loop.close()
```

### Condition Variables & Events

```python
from asyncio import Event

class WebSocketTransport:
    def __init__(self):
        self._connected = Event()

    async def connect(self):
        self._connected.set()

    async def wait_until_connected(self):
        await self._connected.wait()
```

### Queue for Message Processing

```python
from asyncio import Queue

class EventDispatcher:
    def __init__(self):
        self._queue: Queue[Event] = Queue()

    async def enqueue(self, event: Event) -> None:
        await self._queue.put(event)

    async def process_events(self) -> None:
        while True:
            event = await self._queue.get()
            await self._handle(event)
```

## Best Practices for SDKs

### 1. Never block the event loop
No `time.sleep()`, no synchronous I/O in async code. Use `asyncio.sleep()`.

### 2. Handle CancelledError properly
Clean up resources, then re-raise. Never swallow `CancelledError` silently.

### 3. Use timeouts on all external calls
Any network call should have a timeout. The SDK default is 30.0s.

### 4. Structure concurrency with TaskGroup
Prefer `TaskGroup` over raw `asyncio.create_task` for related tasks.

### 5. Don't mix sync and async callbacks
SDK event callbacks should be async-aware. If users pass sync callbacks, run them in executor or accept the limitation.

### 6. Guard against callback exceptions
Never let a user callback exception crash the SDK's internal event loop.

### 7. Provide grace period for shutdown
When closing, give background tasks time to finish (5s timeout) before force-killing.

## Common Pitfalls

- **Swallowing CancelledError**: `except Exception` catches `CancelledError` in Python 3.14. Use `except BaseException` if you must, or re-raise cancelled.
- **Shared mutable state**: Async code with shared state needs locks (`asyncio.Lock`). Sync primitives are not thread-safe in async.
- **`asyncio.run()` called multiple times**: Creates a new loop each time. Use `asyncio.run()` only once at the top level.
- **Unclosed tasks**: Tasks that outlive their parent are garbage collected with a warning. Track and cancel them.
- **`await` in non-async callbacks**: User-provided callbacks that are `async def` need to be awaited. Detect with `asyncio.iscoroutinefunction()`.

## Commands

```bash
uv run python -c "import asyncio; print(asyncio.__version__)"
```

## Resources

- asyncio docs: <https://docs.python.org/3/library/asyncio.html>
- TaskGroup: <https://docs.python.org/3/library/asyncio-task.html#asyncio.TaskGroup>
- Timeouts: <https://docs.python.org/3/library/asyncio-task.html#asyncio.timeout>
- Cancellation: <https://docs.python.org/3/library/asyncio-task.html#task-cancellation>
