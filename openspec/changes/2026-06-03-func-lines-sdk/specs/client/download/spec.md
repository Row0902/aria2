# Download Manager Specification

## Purpose

The `DownloadManager` sub-manager controls the download lifecycle in the aria2 Python SDK:
adding downloads (by URI, torrent file, or Metalink), removing, pausing, resuming, and
reordering. It is accessed via `Aria2Client.downloads`.

This specification covers the internal structural requirements introduced by the
pure-structural refactoring of `add_torrent` and `add_metalink`. All public API
contracts are unchanged.

## Requirements

### Requirement: Module-Level `import base64`

The `download.py` module MUST import `base64` at module level (top of file). No function
body within the module SHALL contain a local `import base64` statement.

#### Scenario: Module-level import

- GIVEN `download.py` is loaded
- WHEN the module is imported
- THEN `import base64` appears at module scope, not inside any function body

### Requirement: `_build_torrent_params` Helper

The module SHALL define a module-level private helper function
`_build_torrent_params(b64, uris, options, position) -> list[Any]` that builds the RPC
params array for the `aria2.addTorrent` method.

The function MUST produce the exact same params arrays as the pre-refactoring inline
logic in `DownloadManager.add_torrent` for all input combinations.

#### Scenario: Torrent with uris only

- GIVEN `_build_torrent_params(b64="<base64>", uris=["http://seed"], options=None, position=None)` is called
- WHEN the function returns
- THEN the result is `["<base64>", ["http://seed"]]`

#### Scenario: Torrent with uris, options, and position

- GIVEN `_build_torrent_params(b64="<base64>", uris=["http://seed"], options={"dir":"/tmp"}, position=1)` is called
- WHEN the function returns
- THEN the result is `["<base64>", ["http://seed"], {"dir":"/tmp"}, 1]`

#### Scenario: Torrent with uris and position (no options) — placeholder constraint

- GIVEN `_build_torrent_params(b64="<base64>", uris=["http://seed"], options=None, position=0)` is called
- WHEN the function returns
- THEN the result is `["<base64>", ["http://seed"], [], 0]`
- AND `params[2]` is `[]` (the placeholder for the skipped options slot)
- AND `params[2]` is NOT `{}`

#### Scenario: Torrent with options and position (no uris)

- GIVEN `_build_torrent_params(b64="<base64>", uris=None, options={"dir":"/tmp"}, position=1)` is called
- WHEN the function returns
- THEN the result is `["<base64>", {"dir":"/tmp"}, 1]`

#### Scenario: Torrent with position only

- GIVEN `_build_torrent_params(b64="<base64>", uris=None, options=None, position=2)` is called
- WHEN the function returns
- THEN the result is `["<base64>", 2]`

#### Scenario: Torrent with no optional params

- GIVEN `_build_torrent_params(b64="<base64>", uris=None, options=None, position=None)` is called
- WHEN the function returns
- THEN the result is `["<base64>"]`

### Requirement: `_build_metalink_params` Helper

The module SHALL define a module-level private helper function
`_build_metalink_params(b64, options, position) -> list[Any]` that builds the RPC
params array for the `aria2.addMetalink` method.

The function MUST produce the exact same params arrays as the pre-refactoring inline
logic in `DownloadManager.add_metalink` for all input combinations.

#### Scenario: Metalink with no optional params

- GIVEN `_build_metalink_params(b64="<base64>", options=None, position=None)` is called
- WHEN the function returns
- THEN the result is `["<base64>"]`

#### Scenario: Metalink with options and position

- GIVEN `_build_metalink_params(b64="<base64>", options={"dir":"/tmp"}, position=1)` is called
- WHEN the function returns
- THEN the result is `["<base64>", {"dir":"/tmp"}, 1]`

#### Scenario: Metalink with position only (no options)

- GIVEN `_build_metalink_params(b64="<base64>", options=None, position=0)` is called
- WHEN the function returns
- THEN the result is `["<base64>", 0]`

### Requirement: `add_torrent` Behavioral Equivalence

The `DownloadManager.add_torrent` method MUST delegate param construction to
`_build_torrent_params` and MUST produce the exact same RPC call as the pre-refactoring
implementation.

#### Scenario: add_torrent delegates to helper

- GIVEN a `DownloadManager` instance with a mock `_request` callable
- WHEN `add_torrent(b"data", uris=["http://seed"], options={"dir":"/tmp"}, position=1)` is called
- THEN `_request` is called with `("aria2.addTorrent", [b64, ["http://seed"], {"dir":"/tmp"}, 1])`
- WHERE `b64` is the base64-encoded representation of `b"data"`

### Requirement: `add_metalink` Behavioral Equivalence

The `DownloadManager.add_metalink` method MUST delegate param construction to
`_build_metalink_params` and MUST produce the exact same RPC call as the pre-refactoring
implementation.

#### Scenario: add_metalink delegates to helper

- GIVEN a `DownloadManager` instance with a mock `_request` callable
- WHEN `add_metalink(b"metal", options={"dir":"/tmp"}, position=1)` is called
- THEN `_request` is called with `("aria2.addMetalink", [b64, {"dir":"/tmp"}, 1])`
- WHERE `b64` is the base64-encoded representation of `b"metal"`

### Requirement: Function Line Limits

Every function body in `download.py` MUST be at most 20 lines, as measured by
`scripts/lint/wc-lint.py`. This includes the refactored `add_torrent` and `add_metalink`
methods.

#### Scenario: Refactored functions within line limit

- GIVEN the refactored `download.py`
- WHEN `scripts/lint/wc-lint.py packages/aria2-sdk/src/aria2/client/download.py` is run
- THEN no function body exceeds 20 lines

### Requirement: No Public API Changes

The `DownloadManager` class SHALL retain the exact same public method signatures it had
before the refactoring. No public method name, parameter list, return type, or raised
exception type SHALL change.

#### Scenario: Public API unchanged

- GIVEN the refactored `DownloadManager` class
- WHEN compared to the pre-refactoring class
- THEN all 10 public methods (`__init__`, `add_uri`, `add_torrent`, `add_metalink`,
  `remove`, `pause`, `pause_all`, `unpause`, `unpause_all`, `change_position`)
  have identical signatures
- AND all existing tests pass without modification
