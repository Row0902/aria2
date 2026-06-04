# aria2-bin Specification

## Purpose

The `aria2-bin` package provides a hatchling build hook that downloads a pre-built
static `aria2c` binary from the
[abcfy2/aria2-static-build](https://github.com/abcfy2/aria2-static-build) GitHub
releases and bundles it into the project wheel. The hook runs during `uv build` and
ensures every platform-specific wheel ships with the correct binary.

## Requirements

### Requirement: Build Hook Registration

The module MUST expose a `BuildHookInterface` subclass registered as a hatchling
custom build hook with plugin name `"aria2-binary"`.

#### Scenario: Plugin name is exposed as a class attribute

- GIVEN the module `packages/aria2-bin/hatch_build.py`
- WHEN it is imported by hatchling during a build
- THEN `Aria2BinaryHook.PLUGIN_NAME` MUST equal `"aria2-binary"`

#### Scenario: Build hook is registered in pyproject.toml

- GIVEN `pyproject.toml` declares a custom hook at `[tool.hatch.build.targets.wheel.hooks.custom]`
- WHEN the build system resolves hooks
- THEN the hook MUST import and execute `Aria2BinaryHook` from the module

#### Scenario: initialize signature matches BuildHookInterface contract

- GIVEN `Aria2BinaryHook` is a subclass of `BuildHookInterface`
- WHEN hatchling calls the hook
- THEN `initialize(self, version: str, build_data: dict[str, Any]) -> None` MUST be the
  only public method and its signature MUST match the base class contract

---

### Requirement: Platform Detection

The system MUST detect the current build platform and map it to the correct zip
asset name and canonical binary name using the `PLATFORM_MAP` dictionary.

#### Scenario: Supported Linux x86_64 platform

- GIVEN `sys.platform` is `"linux"` and `platform.machine()` is `"x86_64"`
- WHEN `_detect_platform()` is called
- THEN it MUST return `("aria2-x86_64-linux-musl_static.zip", "aria2c-linux-x86_64")`

#### Scenario: Supported Windows amd64 platform

- GIVEN `sys.platform` is `"win32"` and `platform.machine()` is `"AMD64"`
- WHEN `_detect_platform()` is called
- THEN it MUST return `("aria2-x86_64-w64-mingw32_static.zip", "aria2c-windows-amd64.exe")`

#### Scenario: Unsupported platform raises OSError

- GIVEN `sys.platform` is `"darwin"` (macOS)
- WHEN `_detect_platform()` is called
- THEN it MUST raise `OSError` with a message listing supported platforms

---

### Requirement: Binary Download

The system MUST download the binary zip from the abcfy2 GitHub release using
HTTP GET with a configurable timeout.

#### Scenario: Successful download of a release zip

- GIVEN the zip asset name `"aria2-x86_64-linux-musl_static.zip"` and release tag `"1.37.0"`
- WHEN the download is initiated
- THEN the system MUST fetch the zip from
  `https://github.com/abcfy2/aria2-static-build/releases/download/1.37.0/aria2-x86_64-linux-musl_static.zip`
- AND save it to the cache directory with the original filename
- AND print a progress message with the URL and resulting file size

#### Scenario: Download uses Accept header

- GIVEN any binary download
- WHEN the HTTP request is constructed
- THEN the request MUST include the header `Accept: application/octet-stream`

#### Scenario: Download timeout is configurable

- GIVEN a download with `timeout=120`
- WHEN the HTTP transfer takes longer than 120 seconds
- THEN the download MUST fail with a timeout error

#### Scenario: HTTP 404 response becomes OSError

- GIVEN the release tag or asset name does not exist at the GitHub URL
- WHEN the server returns HTTP 404
- THEN the system MUST raise `OSError` with a message indicating the zip was not found
- AND the original `HTTPError` MUST be chained as the cause

---

### Requirement: Binary Extraction

The system MUST extract the `aria2c` (or `aria2c.exe`) binary from the downloaded
zip file, remove the zip after successful extraction, and return the binary path.

#### Scenario: Extract Linux binary from zip

- GIVEN a downloaded zip containing a file named `"aria2c"`
- AND the canonical name is `"aria2c-linux-x86_64"`
- WHEN extraction is performed
- THEN the inner file `"aria2c"` MUST be written to `<cache_dir>/aria2c-linux-x86_64`
- AND the zip file MUST be deleted after extraction
- AND a progress message with the canonical name and file size MUST be printed

#### Scenario: Extract Windows binary from zip

- GIVEN a downloaded zip containing a file named `"aria2c.exe"`
- AND the canonical name ends with `".exe"`
- WHEN extraction is performed
- THEN the inner file `"aria2c.exe"` MUST be written to `<cache_dir>/<canonical_name>.exe`

#### Scenario: Expected inner file is missing

- GIVEN a zip that does not contain a file named `"aria2c"` (or `"aria2c.exe"` on Windows)
- WHEN extraction is attempted
- THEN `OSError` MUST be raised indicating the expected inner file was not found

---

### Requirement: Binary Execution Permissions

On Unix platforms, the extracted binary MUST be made executable for user, group,
and other.

#### Scenario: Unix binary receives execute permissions

- GIVEN the canonical name does not end with `".exe"`
- WHEN the binary is written to disk
- THEN its file mode MUST include `S_IXUSR | S_IXGRP | S_IXOTH`

#### Scenario: Windows binary skips chmod

- GIVEN the canonical name ends with `".exe"`
- WHEN the binary is written to disk
- THEN no `chmod` call MUST be made

---

### Requirement: Binary Caching

The system MUST cache downloaded binaries in the `aria2_bin/` directory and reuse
a cached binary on subsequent builds if it exists and is non-empty.

#### Scenario: Cache hit — binary already exists

- GIVEN `<cache_dir>/aria2c-linux-x86_64` already exists and has a non-zero size
- WHEN `initialize` is called
- THEN the binary MUST NOT be re-downloaded
- AND a message `"✓ Using cached <path>"` MUST be printed

#### Scenario: Cache miss — binary does not exist

- GIVEN `<cache_dir>/aria2c-linux-x86_64` does not exist
- WHEN `initialize` is called
- THEN the binary MUST be downloaded and extracted

#### Scenario: Cache miss — binary exists but is empty

- GIVEN `<cache_dir>/aria2c-linux-x86_64` exists but has size 0
- WHEN `initialize` is called
- THEN the binary MUST be re-downloaded

#### Scenario: Cache directory is created if missing

- GIVEN the `aria2_bin/` directory does not exist in the project root
- WHEN `initialize` is called
- THEN the directory MUST be created with `parents=True`

---

### Requirement: Wheel Inclusion via force_include

The system MUST register the downloaded binary and a VERSION file in the wheel's
`force_include` mapping so they are bundled at predictable in-wheel paths.

#### Scenario: Binary is force-included in the wheel

- GIVEN a successfully downloaded binary at `<cache_dir>/aria2c-linux-x86_64`
- WHEN `initialize` completes
- THEN `build_data["force_include"]` MUST contain a mapping from the absolute
  binary path to `"aria2_bin/aria2c-linux-x86_64"`

#### Scenario: VERSION file is force-included in the wheel

- GIVEN the release tag is `"1.37.0"`
- WHEN `initialize` completes
- THEN a file `aria2_bin/VERSION` MUST be written containing the text `"1.37.0"`
- AND `build_data["force_include"]` MUST contain a mapping from the VERSION file
  path to `"aria2_bin/VERSION"`

#### Scenario: force_include is created if not present in build_data

- GIVEN `build_data` does not contain a `"force_include"` key
- WHEN `initialize` runs
- THEN the key MUST be set to a new `dict` before adding entries

#### Scenario: Release tag is read from hook config

- GIVEN the project `pyproject.toml` specifies a custom tag under the hook config
- WHEN `initialize` reads `self.config.get("tag", RELEASE_TAG)`
- THEN the configured tag MUST be used for the download URL and VERSION file
- AND if no tag is configured, `RELEASE_TAG` (`"1.37.0"`) MUST be used as the default

---

### Requirement: Graceful Error Handling

The build hook MUST handle unsupported platforms and download failures without
crashing the build, printing a warning and skipping binary bundling.

#### Scenario: Unsupported platform — print warning and return

- GIVEN the current platform is not in `PLATFORM_MAP`
- WHEN `initialize` is called
- THEN `"⚠  Unsupported platform; skipping binary bundling"` MUST be printed
- AND `initialize` MUST return without modifying `build_data`

#### Scenario: Download failure — print warning and return

- GIVEN a supported platform but the download raises `OSError` (e.g., 404 or network failure)
- WHEN `initialize` calls the download logic
- THEN `"⚠  Binary fetch failed; continuing without bundling"` MUST be printed
- AND `initialize` MUST return without adding entries to `force_include`

---

### Requirement: Source-Level Quality Constraints

Every function and method in the build hook module MUST comply with the project's
lines-of-code thresholds enforced by `scripts/lint/wc-lint.py`.

#### Scenario: Each function body is at most 20 lines

- GIVEN the module `packages/aria2-bin/hatch_build.py`
- WHEN `python scripts/lint/wc-lint.py packages/aria2-bin/hatch_build.py` is run
- THEN zero function-line violations MUST be reported
- AND every function's AST span (`end_lineno - lineno + 1`) MUST be ≤ 20

#### Scenario: File is at most 200 lines

- GIVEN the module `packages/aria2-bin/hatch_build.py`
- WHEN `wc-lint.py` checks file line count
- THEN the file MUST have ≤ 200 lines

#### Scenario: Ruff reports zero errors

- GIVEN the module `packages/aria2-bin/hatch_build.py`
- WHEN `ruff check` is run
- THEN zero errors MUST be reported

#### Scenario: Type checker reports zero errors

- GIVEN the module `packages/aria2-bin/hatch_build.py`
- WHEN `ty --strict` is run
- THEN zero type errors MUST be reported

---

### Requirement: Behavioral Equivalence

The refactored build hook MUST produce byte-identical wheel output compared to the
pre-refactoring version for every supported platform.

#### Scenario: Wheel output is identical

- GIVEN the same platform, release tag, and cache state
- WHEN `uv build --wheel -p packages/aria2-bin` is run before and after the refactoring
- THEN the resulting wheel MUST contain the same set of files under `aria2_bin/`
- AND each binary file MUST be byte-identical

#### Scenario: All supported platforms produce valid wheels

- GIVEN each platform in `PLATFORM_MAP`
- WHEN a wheel build is simulated for that platform
- THEN `_detect_platform()` MUST return the correct mapping
- AND the download URL MUST resolve to the correct zip asset for that platform
