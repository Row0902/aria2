# Aria2Client Specification

## Purpose

The `Aria2Client` is the top-level async JSON-RPC client for the aria2 Python SDK. It
manages transport lifecycle (HTTP + optional WebSocket), sub-manager property access,
and internal request dispatching.

This specification covers the internal structural requirements introduced by the
pure-structural refactoring of `Aria2Client.__init__`. All public API contracts are
unchanged.

## Requirements

### Requirement: `_init_sub_managers` Private Method

The `Aria2Client` class SHALL define a private method `_init_sub_managers(self)` that
creates all six sub-manager instances and assigns them to instance attributes. The
method MUST create the following sub-managers:

| Instance attribute | Class | Constructor args |
|---|---|---|
| `self._downloads` | `DownloadManager` | `(self._request, self._secret)` |
| `self._status` | `StatusManager` | `(self._request)` |
| `self._options` | `OptionsManager` | `(self._request)` |
| `self._system` | `SystemManager` | `(self._request)` |
| `self._daemon` | `DaemonManager` | `(self._request, self._secret)` |
| `self._events` | `EventManager` | `(self._callbacks)` |

#### Scenario: All sub-managers created

- GIVEN an `Aria2Client` instance is constructed
- WHEN `_init_sub_managers` is called (from `__init__`)
- THEN `self._downloads` is a `DownloadManager` instance
- AND `self._status` is a `StatusManager` instance
- AND `self._options` is an `OptionsManager` instance
- AND `self._system` is a `SystemManager` instance
- AND `self._daemon` is a `DaemonManager` instance
- AND `self._events` is an `EventManager` instance

#### Scenario: Sub-managers receive correct dependencies

- GIVEN an `Aria2Client` is constructed with `secret="test"`
- WHEN `_init_sub_managers` is called
- THEN `DownloadManager` receives `self._request` and `"test"` as the secret
- AND `DaemonManager` receives `self._request` and `"test"` as the secret
- AND `StatusManager`, `OptionsManager`, and `SystemManager` receive `self._request`
- AND `EventManager` receives `self._callbacks`

### Requirement: `__init__` Delegation

The `Aria2Client.__init__` method SHALL delegate sub-manager creation to
`_init_sub_managers`. The method MUST perform the following steps in order:

1. Store `host`, `port`, `secret`, and `timeout` as instance attributes
2. Create the `HttpTransport`
3. Initialize the WebSocket transport via `_init_ws_transport`
4. Initialize the callbacks dict
5. Call `self._init_sub_managers()`

#### Scenario: __init__ delegates to helper

- GIVEN `Aria2Client(host="a", port=1, secret="s", timeout=5.0, enable_ws=False)` is constructed
- WHEN `__init__` completes
- THEN `self._init_sub_managers()` was called
- AND all six sub-manager properties return non-None values

### Requirement: Property Access Unchanged

All six sub-manager properties MUST continue to return their respective sub-manager
instances after the refactoring.

#### Scenario: downloads property

- GIVEN a connected `Aria2Client` instance
- WHEN `client.downloads` is accessed
- THEN a `DownloadManager` instance is returned

#### Scenario: status property

- GIVEN a connected `Aria2Client` instance
- WHEN `client.status` is accessed
- THEN a `StatusManager` instance is returned

#### Scenario: options property

- GIVEN a connected `Aria2Client` instance
- WHEN `client.options` is accessed
- THEN an `OptionsManager` instance is returned

#### Scenario: system property

- GIVEN a connected `Aria2Client` instance
- WHEN `client.system` is accessed
- THEN a `SystemManager` instance is returned

#### Scenario: daemon property

- GIVEN a connected `Aria2Client` instance
- WHEN `client.daemon` is accessed
- THEN a `DaemonManager` instance is returned

#### Scenario: events property

- GIVEN a connected `Aria2Client` instance
- WHEN `client.events` is accessed
- THEN an `EventManager` instance is returned

### Requirement: Behavioral Equivalence

The refactored `Aria2Client.__init__` MUST produce the exact same object state as the
pre-refactoring implementation. All existing tests MUST pass without modification.

#### Scenario: All existing tests pass unchanged

- GIVEN the refactored `Aria2Client`
- WHEN `pytest tests/test_client.py -v` is run
- THEN all tests pass without modification
- AND the `client()` fixture creates a valid `Aria2Client` with all 6 sub-managers
- AND `test_enable_ws_false` passes — `_ws` is `None`, sub-managers exist
- AND `test_ws_connect_degrades_gracefully` passes — all sub-managers accessible

### Requirement: Function Line Limits

Every function body in `client/__init__.py` MUST be at most 20 lines, as measured by
`scripts/lint/wc-lint.py`. The refactored `__init__` method body MUST be 20 lines or
fewer.

#### Scenario: Functions within line limit

- GIVEN the refactored `client/__init__.py`
- WHEN `scripts/lint/wc-lint.py packages/aria2-sdk/src/aria2/client/__init__.py` is run
- THEN no function body exceeds 20 lines

### Requirement: File Size Limit

The `client/__init__.py` file SHALL remain at or under 200 total lines after the
refactoring.

#### Scenario: File within line limit

- GIVEN the refactored `client/__init__.py`
- WHEN the total line count is measured
- THEN the file is at most 200 lines

### Requirement: No Public API Changes

The `Aria2Client` class SHALL retain the exact same public attributes and method
signatures it had before the refactoring. No public method name, parameter list,
return type, or raised exception type SHALL change.

#### Scenario: Public API unchanged

- GIVEN the refactored `Aria2Client` class
- WHEN compared to the pre-refactoring class
- THEN all public methods (`__init__`, `connect`, `close`, `__aenter__`, `__aexit__`,
  `multicall`) and all six sub-manager properties have identical signatures
