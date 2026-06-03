# HTTP Transport Specification

## Purpose

The `HttpTransport` is the HTTP-based JSON-RPC transport for the aria2 Python SDK. It
uses `httpx` to communicate with a running aria2c daemon via `POST` to the
`/jsonrpc` endpoint. It implements the `Transport` ABC and provides synchronous-style
request/response semantics over HTTP.

This specification covers the internal structural requirements introduced by the
pure-structural refactoring of `send_request`. All public API contracts are unchanged.

## Requirements

### Requirement: `_do_request` Private Helper

The `HttpTransport` class SHALL define a private async method
`_do_request(self, payload: str) -> Any` that encapsulates the HTTP POST, status
check, response parsing, and error-wrapping logic.

The method MUST:

1. POST the given `payload` JSON-RPC string to the configured URL
   with `Content-Type: application/json`
2. Raise `Aria2ConnectionError` if the HTTP status code is not 200
3. Parse the JSON-RPC response via `_parse()` and return the result
4. Wrap `httpx.HTTPError` and `TimeoutError` / `OSError` into `Aria2ConnectionError`
5. Re-raise `Aria2RpcError` without wrapping

#### Scenario: Successful request through helper

- GIVEN `_do_request` is called with a valid JSON-RPC payload
- WHEN the daemon returns HTTP 200 with a JSON-RPC result
- THEN `_parse()` is called on the response body
- AND the parsed result is returned

#### Scenario: RPC error through helper

- GIVEN `_do_request` is called with a valid JSON-RPC payload
- WHEN the daemon returns HTTP 200 with a JSON-RPC error in the body
- THEN `_parse()` raises `Aria2RpcError`
- AND `Aria2RpcError` propagates through `_do_request` unwrapped

#### Scenario: HTTP error through helper

- GIVEN `_do_request` is called with a valid JSON-RPC payload
- WHEN the daemon returns a non-200 HTTP status (e.g., 500)
- THEN `Aria2ConnectionError` is raised with a message containing the status code

#### Scenario: Network error through helper

- GIVEN `_do_request` is called with a valid JSON-RPC payload
- WHEN an `httpx.HTTPError`, `TimeoutError`, or `OSError` occurs during the request
- THEN `Aria2ConnectionError` is raised wrapping the original error message

### Requirement: `send_request` Delegation

The `HttpTransport.send_request` method SHALL delegate all HTTP I/O and error wrapping
to `_do_request`. The method MUST retain its existing guard-checks and request-ID
management.

#### Scenario: Connection guard stays in send_request

- GIVEN `HttpTransport` is NOT connected (`is_connected` returns `False`)
- WHEN `send_request(...)` is called
- THEN `Aria2ConnectionError` is raised immediately
- AND `_do_request` is never called

#### Scenario: Request ID management stays in send_request

- GIVEN `HttpTransport` is connected
- WHEN `send_request(...)` is called
- THEN `self._request_id` is incremented before the payload is built
- AND `_build_payload` is called with the incremented request ID

#### Scenario: Successful delegation to helper

- GIVEN `HttpTransport` is connected
- WHEN `send_request("aria2.addUri", [["http://x"]])` is called
- THEN the payload is built via `_build_payload`
- AND the payload is passed to `_do_request`
- AND the result from `_do_request` is returned

### Requirement: Behavioral Equivalence

The refactored `HttpTransport.send_request` MUST produce the exact same behavior as
the pre-refactoring implementation for all inputs and edge cases.

#### Scenario: All existing tests pass unchanged

- GIVEN the refactored `HttpTransport`
- WHEN `pytest tests/test_http.py -v` is run
- THEN all six tests pass without modification:
  - `test_send_request_success`
  - `test_send_request_rpc_error`
  - `test_send_request_http_error`
  - `test_not_connected_raises`
  - `test_http_timeout_error`
  - `test_send_request_no_secret`

### Requirement: Function Line Limits

Every function body in `http.py` MUST be at most 20 lines, as measured by
`scripts/lint/wc-lint.py`. The refactored `send_request` method body MUST be 20 lines
or fewer.

#### Scenario: Functions within line limit

- GIVEN the refactored `http.py`
- WHEN `scripts/lint/wc-lint.py packages/aria2-sdk/src/aria2/client/transport/http.py` is run
- THEN no function body exceeds 20 lines

### Requirement: File Size Limit

The `http.py` file SHALL remain at or under 200 total lines after the refactoring.

#### Scenario: File within line limit

- GIVEN the refactored `http.py`
- WHEN the total line count is measured
- THEN the file is at most 200 lines

### Requirement: No Public API Changes

The `HttpTransport` class SHALL retain the exact same public method signatures it had
before the refactoring. No public method name, parameter list, return type, or raised
exception type SHALL change.

#### Scenario: Public API unchanged

- GIVEN the refactored `HttpTransport` class
- WHEN compared to the pre-refactoring class
- THEN all public methods (`__init__`, `connect`, `send_request`, `close`) and
  properties (`is_connected`) have identical signatures
