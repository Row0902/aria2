# Delta for WebSocket Transport

## ADDED Requirements

### Requirement: `_WsReader` Class (Reader Module)

The system MUST implement a `_WsReader` class in a new `transport/ws/_reader.py`
file. This class SHALL own the WebSocket reader loop, message dispatch, and
automatic reconnection logic, which are moved out of `WebSocketTransport`.

`_WsReader` SHALL be initialized with:
- `ws`: the active `websockets` client connection
- `pending_mgr`: a `_PendingRequestManager` instance (from the transport)
- `event_callback`: optional notification dispatcher callable
- `url`: the WebSocket endpoint URL string
- `timeout`: connection timeout in seconds

`_WsReader` SHALL NOT own the WebSocket client lifecycle — the `_ws` reference
is provided by `WebSocketTransport.connect()` and MAY be replaced during
reconnection by `_WsReader._reconnect()`.

The class SHALL expose a `_should_reconnect` boolean flag that controls whether
the reader loop attempts reconnection on disconnect. `WebSocketTransport` SHALL
set this flag to `True` in `connect()` and to `False` in `close()`.

#### Scenario: Reader loop processes and dispatches messages

- GIVEN a `_WsReader` instance with an active WebSocket connection
- WHEN `run()` is called
- THEN the method enters an `async for raw in self._ws` loop
- AND each raw message is passed to `dispatch()`
- AND on normal `ConnectionClosed`, the loop exits

#### Scenario: Dispatch routes notifications to callback

- GIVEN a `_WsReader` instance with an `event_callback` set
- WHEN `dispatch()` receives a message that `_parse_notification` identifies as a notification
- THEN the event callback is invoked with the method name and params
- AND `dispatch()` returns without attempting to resolve a pending future

#### Scenario: Dispatch routes responses to pending futures

- GIVEN a `_WsReader` instance with a pending future registered for request ID 5
- WHEN `dispatch()` receives a JSON-RPC response with `id=5`
- THEN the pending future is resolved with the parsed result
- AND if the future is already done, no action is taken

#### Scenario: Reconnection with exponential backoff

- GIVEN `_should_reconnect` is `True` on the `_WsReader` instance
- WHEN the WebSocket connection closes unexpectedly during `run()`
- THEN `_reconnect()` is called
- AND reconnection attempts use exponential backoff starting at `_reconnect_delay` seconds, doubling on each failure, capped at `_max_reconnect_delay` seconds
- AND on successful reconnection, a new `run()` loop is started on the new connection

#### Scenario: Reader stopped by flag during intentional close

- GIVEN `_should_reconnect` is set to `False` on the `_WsReader` instance
- WHEN the WebSocket connection closes
- THEN `run()` exits without calling `_reconnect()`

### Requirement: `_init_internal_state` Helper

`WebSocketTransport` MUST extract its runtime state initialization from `__init__`
into a private `_init_internal_state()` method so that the constructor body
does not exceed 20 lines.

The `_init_internal_state()` method SHALL be called once from `__init__`, after
all constructor-argument assignments. It SHALL initialize every mutable instance
attribute: `_ws`, `_request_id`, `_reader_task`, `_should_reconnect`, `_pending`,
`_pending_mgr`, and `_reader`.

#### Scenario: Constructor stays under 20 lines

- GIVEN `WebSocketTransport.__init__`
- WHEN the constructor body line count is measured (excluding signature, docstring, and blank lines)
- THEN the body SHALL be at most 20 lines

#### Scenario: Internal state initialized correctly

- GIVEN `WebSocketTransport()` is instantiated
- WHEN `_init_internal_state()` returns
- THEN `self._ws` is `None`
- AND `self._request_id` is `0`
- AND `self._reader_task` is `None`
- AND `self._should_reconnect` is `False`
- AND `self._pending` is an empty `dict`
- AND `self._pending_mgr` is a `_PendingRequestManager` wrapping `self._pending`
- AND `self._reader` is `None`

## MODIFIED Requirements

### Requirement: Package Structure

The WebSocket transport SHALL be implemented as a `transport/ws/` package with
the following files, each under 200 lines and every function body at most 20 lines:

| File | Purpose |
|---|---|
| `transport/ws/__init__.py` | Public re-export of `WebSocketTransport` from `.transport` |
| `transport/ws/transport.py` | `WebSocketTransport` class — connection, requests, lifecycle |
| `transport/ws/_pending.py` | `_PendingRequestManager` helper — pending future lifecycle |
| `transport/ws/_reader.py` | `_WsReader` class — reader loop, dispatch, reconnection |

The canonical import path `from aria2.client.transport.ws import WebSocketTransport`
MUST continue to resolve correctly.

(Previously: the table listed only three files — `__init__.py`, `transport.py`, and
`_pending.py`. `transport.py` owned the reader loop, dispatch, and reconnection.
This change adds `_reader.py` as a fourth file and moves reader/dispatch/reconnect
responsibilities into it.)

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

### Requirement: Reader Loop Lifecycle

The transport SHALL run exactly one reader task per active connection, created by
`connect()` and stopped by `close()` or reconnection.

(Previously: the scenario referenced `_reader_loop()` as the reader task body.
The reader loop now runs via `_WsReader.run()`. The transport creates a
`_WsReader` instance in `connect()` and starts its `run()` coroutine as a
background task. All other lifecycle behavior is unchanged.)

#### Scenario: Reader task started on connect

- GIVEN `connect()` succeeds
- THEN a background `asyncio.Task` is created for `_WsReader.run()`

#### Scenario: Reader task cancelled on close

- GIVEN a connected transport with an active reader task
- WHEN `close()` is called
- THEN the reader task is cancelled
- AND the transport waits for the task to finish (suppressing `CancelledError`)
- AND the reader task reference is set to `None`

### Requirement: Structural Policy Compliance

Every function body in the `transport/ws/` package SHALL be at most 20 lines, and each
file SHALL be at most 200 lines. This is verified mechanically.

(Previously: the "all functions" scenario enumerated only `transport.py`, `_pending.py`,
and `__init__.py`. This change adds `_reader.py` to the audited file set.)

#### Scenario: All functions under 20 lines

- GIVEN the source files `transport/ws/transport.py`, `transport/ws/_pending.py`,
  `transport/ws/__init__.py`, and `transport/ws/_reader.py`
- WHEN function body line counts are measured (excluding signature, docstring, blank lines)
- THEN no function body exceeds 20 lines

#### Scenario: All files under 200 lines

- GIVEN the source files in the `transport/ws/` package
- WHEN file line counts are measured (including all lines)
- THEN no file exceeds 200 lines
