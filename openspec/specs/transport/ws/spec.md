# WebSocket Transport Specification

## Purpose

The WebSocket transport is the primary JSON-RPC transport for the aria2 Python SDK. It
provides persistent, bidirectional communication with a running aria2c daemon, supporting
both request/response operations and asynchronous push notifications (e.g., download
events). It implements the `Transport` ABC and includes automatic reconnection with
exponential backoff.

The module is structured as a `transport/ws/` package to comply with project policies on
file and function length. The refactoring is purely structural: no behavioural changes,
no API changes, and all existing tests MUST pass without modification.

## Requirements

### Requirement: Package Structure

The WebSocket transport SHALL be implemented as a `transport/ws/` package with
the following files, each under 200 lines and every function body at most 20 lines:

| File | Purpose |
|---|---|
| `transport/ws/__init__.py` | Public re-export of `WebSocketTransport` from `.transport` |
| `transport/ws/transport.py` | `WebSocketTransport` class — connection, requests, reader loop, reconnection |
| `transport/ws/_pending.py` | `_PendingRequestManager` helper — pending future lifecycle |

The canonical import path `from aria2.client.transport.ws import WebSocketTransport`
MUST continue to resolve correctly.

#### Scenario: Import path preserved

- GIVEN the `transport/ws/` package is installed
- WHEN user code executes `from aria2.client.transport.ws import WebSocketTransport`
- THEN `WebSocketTransport` resolves to the same class
- AND the class is a valid `Transport` implementation

#### Scenario: Re-export completeness

- GIVEN `transport/ws/__init__.py`
- WHEN the module is imported
- THEN `WebSocketTransport` is the only public symbol exported
- AND `__all__` explicitly lists only `"WebSocketTransport"`

### Requirement: Connection Lifecycle

The transport SHALL manage a single WebSocket connection through three states:
disconnected, connected, and reconnecting.

#### Scenario: Successful connection

- GIVEN an aria2c daemon is listening on the configured host and port
- WHEN `connect()` is called
- THEN a WebSocket connection to `ws://{host}:{port}/jsonrpc` is opened
- AND `is_connected` returns `True`
- AND a background reader task is started

#### Scenario: Connection refused

- GIVEN no service is listening on the configured host and port
- WHEN `connect()` is called
- THEN `Aria2ConnectionError` is raised
- AND `is_connected` returns `False`
- AND no reader task is started

#### Scenario: Connection check when disconnected

- GIVEN the transport has never been connected or has been closed
- WHEN `is_connected` is accessed
- THEN it returns `False`

#### Scenario: Connection check after close

- GIVEN a successfully connected transport
- WHEN `close()` is called
- THEN `is_connected` returns `False`

### Requirement: Request/Response Flow

The transport SHALL send JSON-RPC 2.0 requests over the WebSocket and return parsed
results to the caller, matching responses to pending requests by ID.

#### Scenario: Basic request

- GIVEN the transport is connected
- WHEN `send_request("aria2.addUri", [["http://example.com/file.zip"]])` is called
- THEN a JSON-RPC request is sent with a unique incrementing `id`
- AND the method waits for a response matching that `id`
- AND returns the parsed `result` field

#### Scenario: Request with secret

- GIVEN the transport is configured with `secret="mytoken"`
- WHEN `send_request("aria2.addUri", [["http://example.com/file.zip"]])` is called
  (without `add_secret=False`)
- THEN the request params are prefixed with `"token:mytoken"`
- AND the request is sent with a unique incrementing `id`

#### Scenario: Request without secret (explicit opt-out)

- GIVEN the transport is configured with `secret="mytoken"`
- WHEN `send_request("aria2.addUri", [["http://example.com/file.zip"]], add_secret=False)` is called
- THEN the request params do NOT contain `"token:mytoken"`
- AND the request is sent with a unique incrementing `id`

#### Scenario: Request ID is monotonically incrementing

- GIVEN the transport is connected
- WHEN three requests are sent in sequence
- THEN each request has a distinct `id`
- AND the IDs increase strictly

#### Scenario: Request when not connected

- GIVEN the transport is NOT connected
- WHEN `send_request(...)` is called
- THEN `Aria2ConnectionError` is raised immediately
- AND no WebSocket message is sent

### Requirement: RPC Error Handling

The transport SHALL propagate JSON-RPC errors from the daemon as `Aria2RpcError`
exceptions to the caller.

#### Scenario: Daemon returns an error

- GIVEN the transport is connected
- WHEN a request is sent and the daemon responds with `{"jsonrpc": "2.0", "error": {"code": -1, "message": "msg"}, "id": N}`
- THEN the pending future for request `N` is resolved with an `Aria2RpcError` exception
- AND the caller's `send_request()` raises `Aria2RpcError`
- AND the error includes the code and message from the response

### Requirement: Push Notification Routing

The transport SHALL distinguish JSON-RPC notifications (messages without an `id` field)
from responses and dispatch them to the configured event callback.

#### Scenario: Notification dispatched

- GIVEN the transport is connected with an `event_callback` set
- WHEN a message `{"jsonrpc": "2.0", "method": "aria2.onDownloadStart", "params": [{"gid": "abc"}]}` arrives (no `id` field)
- THEN the event callback is invoked with arguments `("aria2.onDownloadStart", [{"gid": "abc"}])`

#### Scenario: No event callback configured

- GIVEN the transport is connected with `event_callback=None`
- WHEN a notification arrives
- THEN the notification is silently ignored (no error)

#### Scenario: Notification is not treated as a response

- GIVEN the transport is connected
- WHEN a notification arrives followed by a response for the pending request
- THEN the notification is dispatched to the callback
- AND the request resolves normally with the response's result

### Requirement: Stale or Unknown Responses

The transport SHALL silently ignore responses whose request ID does not match any
pending future.

#### Scenario: Unknown response ID

- GIVEN the transport is connected
- AND no request with `id=999` is pending
- WHEN a response with `id=999` arrives
- THEN the response is silently ignored
- AND no exception is raised
- AND the reader loop continues processing further messages

### Requirement: Idempotent Close

`close()` SHALL be safe to call multiple times. An already-closed transport MUST not
raise an error when `close()` is called again.

#### Scenario: Close when unconnected

- GIVEN a transport that has never been connected
- WHEN `close()` is called
- THEN no exception is raised

#### Scenario: Double close

- GIVEN a connected transport
- WHEN `close()` is called twice in succession
- THEN neither call raises an exception
- AND `is_connected` returns `False` after the first call

### Requirement: Pending Request Cancellation on Close

`close()` SHALL cancel all pending request futures and clear the pending map.

#### Scenario: Pending futures cancelled

- GIVEN a connected transport with a pending future registered in `_pending` (not yet resolved)
- WHEN `close()` is called
- THEN the future is cancelled (`.cancelled()` returns `True`)
- AND `_pending` is empty after close completes

#### Scenario: Already-resolved future unaffected

- GIVEN a connected transport with a pending future that has already been resolved with a result
- WHEN `close()` is called
- THEN the resolved future is not cancelled (result is preserved)

### Requirement: Reconnection with Exponential Backoff

When the WebSocket connection drops unexpectedly, the transport SHALL attempt to
reconnect automatically with exponential backoff up to a configured maximum delay.

#### Scenario: Reconnection loop

- GIVEN the transport is connected and `_should_reconnect` is `True`
- WHEN the WebSocket connection closes (e.g., daemon restart)
- THEN the reader loop detects the disconnection
- AND initiates reconnection with an initial delay of `reconnect_delay` seconds
- AND each failed reconnection attempt doubles the delay (capped at `max_reconnect_delay`)
- AND on successful reconnection, a new reader loop is started

#### Scenario: Reconnection suppressed during intentional close

- GIVEN the transport is connected
- WHEN `close()` is called (which sets `_should_reconnect = False`)
- THEN the reader loop exits without attempting reconnection

### Requirement: Dispatch Error Containment

Errors raised by the event callback or response parsing SHALL be contained within
the dispatch method and SHALL NOT crash the reader loop.

#### Scenario: Callback raises an exception

- GIVEN a connected transport with an event callback that raises `RuntimeError`
- WHEN a notification arrives
- THEN the callback's exception is caught and swallowed
- AND the reader loop continues processing subsequent messages
- AND subsequent requests resolve successfully

#### Scenario: Malformed message does not crash reader

- GIVEN a connected transport
- WHEN a message that cannot be parsed as JSON arrives
- THEN the parsing error is caught and swallowed
- AND the reader loop continues processing subsequent messages

### Requirement: Reader Loop Lifecycle

The transport SHALL run exactly one reader task per active connection, created by
`connect()` and stopped by `close()` or reconnection.

#### Scenario: Reader task started on connect

- GIVEN `connect()` succeeds
- THEN a background `asyncio.Task` is created for `_reader_loop()`

#### Scenario: Reader task cancelled on close

- GIVEN a connected transport with an active reader task
- WHEN `close()` is called
- THEN the reader task is cancelled
- AND the transport waits for the task to finish (suppressing `CancelledError`)
- AND the reader task reference is set to `None`

### Requirement: Pending Request Manager (Internal)

An internal `_PendingRequestManager` helper class SHALL encapsulate operations on the
pending futures dictionary without owning it. The dictionary MUST remain a plain
`dict[int, asyncio.Future[Any]]` stored as `_pending` on the `WebSocketTransport`
instance so that existing tests that access `t._pending` continue to work.

#### Scenario: Test access to _pending as dict

- GIVEN a `WebSocketTransport` instance `t`
- AND a pending future has been registered with `_pending` via `send_request()`
- WHEN test code accesses `t._pending`
- THEN it is a `dict` mapping `int` to `asyncio.Future`
- AND the registered future is accessible by its request ID

#### Scenario: Cancel all pending

- GIVEN the pending manager has been given the transport's `_pending` dict
- AND several futures are registered
- WHEN `cancel_all()` is called
- THEN all incomplete futures are cancelled
- AND the dict is cleared

### Requirement: Structural Policy Compliance

Every function body in the `transport/ws/` package SHALL be at most 20 lines, and each
file SHALL be at most 200 lines. This is verified mechanically.

#### Scenario: All functions under 20 lines

- GIVEN the source files `transport/ws/transport.py`, `transport/ws/_pending.py`, and
  `transport/ws/__init__.py`
- WHEN function body line counts are measured (excluding signature, docstring, blank lines)
- THEN no function body exceeds 20 lines

#### Scenario: All files under 200 lines

- GIVEN the source files in the `transport/ws/` package
- WHEN file line counts are measured (including all lines)
- THEN no file exceeds 200 lines

### Requirement: Behavioural Equivalence

The refactored package SHALL exhibit identical external behaviour to the original
monolithic `ws.py`. All 11 existing tests MUST pass without modification.

#### Scenario: Existing tests pass

- GIVEN the original `tests/test_ws.py` test suite
- WHEN run against the refactored `transport/ws/` package
- THEN all 11 tests pass

### Requirement: Error Type Consistency

The transport SHALL wrap all third-party exceptions from the `websockets` library
into `Aria2ConnectionError`. It SHALL NOT leak raw `OSError`, `TimeoutError`, or
`websockets.ConnectionClosed` to callers.

#### Scenario: Third-party exceptions are wrapped

- GIVEN the WebSocket connection fails during `connect()` due to a network error
- WHEN the exception propagates to the caller
- THEN it is an `Aria2ConnectionError`
- AND the original exception is available via `__cause__`

#### Scenario: Connection error during send

- GIVEN the transport is connected
- WHEN the WebSocket connection drops during `send_request()` (e.g., network failure)
- THEN the caller receives an `Aria2ConnectionError`
- AND the pending future for that request is cleaned up
