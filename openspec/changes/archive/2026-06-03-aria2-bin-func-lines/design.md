# SDD Design: Refactor `hatch_build.py` — Extract Module-Level Helpers

**Change ID:** `2026-06-03-aria2-bin-func-lines`
**Date:** 2026-06-03
**Status:** Draft
**Strategy:** Pure structural extraction — zero behavioral changes, zero API changes

---

## 1. Architecture

### 1.1 Problem Statement

Two functions in `packages/aria2-bin/hatch_build.py` exceed the `max_function_lines: 20`
threshold enforced by `scripts/lint/wc-lint.py`:

| Function | Current lines | Limit | Violation |
|---|---|---|---|
| `_download_and_extract_binary` | 51 | 20 | +31 |
| `Aria2BinaryHook.initialize` | 36 | 20 | +16 |

Both functions are monolithic: they mix download, extraction, caching, error handling,
and wheel configuration into single bodies. The solution is to extract focused,
single-responsibility module-level helpers along natural seams, then reduce the
original functions to thin orchestrators.

### 1.2 Extraction Strategy

```
BEFORE                                       AFTER
─────────────────────                     ─────────────────────
# Module-level (2 helpers)                # Module-level (5 helpers)
_detect_platform()                        _detect_platform()         (unchanged)
_download_and_extract_binary() (51 lines) _download_zip()            (NEW, ~14 lines)
                                          _extract_from_zip()        (NEW, ~18 lines)
                                          _download_and_extract_binary() (thin, ~7 lines)
                                          _get_or_download_binary()  (NEW, ~9 lines)

# Class (1 method, 36 lines)              # Class (1 method, ~20 lines)
Aria2BinaryHook.initialize()              Aria2BinaryHook.initialize()
                                          (unchanged PLUGIN_NAME, signature)
```

Each new helper does **exactly one thing**:

| Helper | Responsibility | Lines |
|---|---|---|
| `_download_zip` | HTTP GET a zip from GitHub, handle 404, report size | ~14 |
| `_extract_from_zip` | Open zip, extract binary, delete zip, `chmod +x`, report size | ~18 |
| `_download_and_extract_binary` | Compose download + extract with URL construction | ~7 |
| `_get_or_download_binary` | Cache check → download + extract on miss | ~9 |

### 1.3 Call Graph (refactored)

```
Aria2BinaryHook.initialize()
  │
  ├─ _detect_platform()                          → (zip_asset, canonical_name) | OSError
  │
  ├─ _get_or_download_binary(zip_asset, canonical_name, cache_dir, tag)
  │    │
  │    ├─ cache hit → return binary_path
  │    │
  │    └─ cache miss:
  │         ├─ _download_zip(url, cache_dir)
  │         │    └─ urllib.request.urlopen(…) → zip_path
  │         │
  │         └─ _extract_from_zip(zip_path, canonical_name)
  │              ├─ zipfile.ZipFile(…) → extract inner binary
  │              ├─ zip_path.unlink()           ← cleanup
  │              ├─ chmod +x (Unix only)
  │              └─ return binary_path
  │
  └─ force_include setup + VERSION file write
```

`_download_and_extract_binary` remains as a module-level convenience compositor
that can be used independently. `_get_or_download_binary` calls the primitives
`_download_zip` and `_extract_from_zip` directly to avoid unnecessary indirection.

---

## 2. File Specs

### 2.1 `_download_zip(url, dest, *, timeout) -> Path`

**Purpose:** Download a zip file from a GitHub release URL to a local directory.
Handles HTTP 404 specially (raises `OSError`). Reports progress with file size.

**Signature:**
```python
def _download_zip(url: str, dest: Path, *, timeout: float = 120) -> Path:
```

**Parameters:**
| Param | Type | Description |
|---|---|---|
| `url` | `str` | Full URL to the release zip asset |
| `dest` | `Path` | Directory to save the zip into |
| `timeout` | `float` | HTTP timeout in seconds (keyword-only, default 120) |

**Returns:** `Path` — local path to the downloaded zip file.

**Raises:** `OSError` on HTTP 404 (with chained `HTTPError`), or any other HTTP error.

**Source:**

```python
def _download_zip(url: str, dest: Path, *, timeout: float = 120) -> Path:
    """Download a zip from *url* to *dest* and return the local path.

    Args:
        url: Full GitHub URL to the release zip asset.
        dest: Directory to save the zip into.
        timeout: HTTP timeout in seconds.

    Returns:
        Local path to the downloaded zip file.

    Raises:
        OSError: If HTTP 404 or any download failure.

    """
    zip_path = dest / Path(url).name

    print(f"  ⬇  Downloading {url} …")
    req = urllib.request.Request(url, headers={"Accept": "application/octet-stream"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            zip_path.write_bytes(resp.read())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            msg = f"Binary zip not found at {url}."
            raise OSError(msg) from e
        raise

    print(f"     ✓ {zip_path.name} ({zip_path.stat().st_size / 1024:.0f} KB)")
    return zip_path
```

**Line count:** ~14 (≤20 ✅).

**Behavioral equivalence:** Identical byte-for-byte to the download portion of the original `_download_and_extract_binary`. Same URL construction (handled by callers), same `urllib.request.Request` with `Accept: application/octet-stream`, same `urlopen` with timeout, same `write_bytes`, same 404→OSError wrapping, same progress print.

---

### 2.2 `_extract_from_zip(zip_path, canonical_name) -> Path`

**Purpose:** Extract the inner `aria2c` (or `aria2c.exe`) binary from the downloaded
zip, rename it to the canonical name, delete the zip, make executable on Unix,
and report progress.

**Signature:**
```python
def _extract_from_zip(zip_path: Path, canonical_name: str) -> Path:
```

**Parameters:**
| Param | Type | Description |
|---|---|---|
| `zip_path` | `Path` | Path to the downloaded zip file (deleted after extraction) |
| `canonical_name` | `str` | Renamed binary filename (e.g. `aria2c-linux-x86_64`) |

**Returns:** `Path` — path to the extracted binary.

**Raises:** `OSError` if the expected inner file is not found in the zip.

**Source:**

```python
def _extract_from_zip(zip_path: Path, canonical_name: str) -> Path:
    """Extract the aria2c binary from a zip and return its path.

    Args:
        zip_path: Path to the downloaded zip file (deleted after extraction).
        canonical_name: Renamed binary filename (e.g. ``"aria2c-linux-x86_64"``).

    Returns:
        Path to the extracted binary, ready for ``force_include``.

    Raises:
        OSError: If the expected inner file is not found inside the zip.

    """
    inner_name = "aria2c.exe" if canonical_name.endswith(".exe") else "aria2c"
    dest = zip_path.parent / canonical_name

    with zipfile.ZipFile(zip_path) as zf:
        try:
            info = zf.getinfo(inner_name)
        except KeyError:
            msg = f"Expected {inner_name!r} not found inside {zip_path.name}"
            raise OSError(msg) from None

        with zf.open(info) as src, open(dest, "wb") as dst:
            dst.write(src.read())

    zip_path.unlink()

    if not canonical_name.endswith(".exe"):
        mode = dest.stat().st_mode
        dest.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    print(f"     ✓ {canonical_name} ({dest.stat().st_size / 1024:.0f} KB)")
    return dest
```

**Line count:** ~18 (≤20 ✅).

**Behavioral equivalence:** Identical to the extraction portion of the original function. Same inner-name resolution (`"aria2c.exe"` vs `"aria2c"`), same `zf.getinfo`→`KeyError`→`OSError` chain, same `write_bytes` from zip, same `zip_path.unlink()`, same `chmod` only on non-`.exe` platforms, same progress print.

---

### 2.3 `_download_and_extract_binary` (thin orchestrator)

**Purpose:** Compose URL construction, download, and extraction. Kept for backward
compatibility and as a convenience compositor for callers that have `zip_asset`,
`canonical_name`, and `tag` but not a pre-constructed URL.

**Signature:**
```python
def _download_and_extract_binary(
    zip_asset: str,
    canonical_name: str,
    dest: Path,
    *,
    tag: str = RELEASE_TAG,
    timeout: float = 120,
) -> Path:
```

**Parameters:**
| Param | Type | Description |
|---|---|---|
| `zip_asset` | `str` | Filename of the zip asset on GitHub |
| `canonical_name` | `str` | Renamed binary filename |
| `dest` | `Path` | Cache directory |
| `tag` | `str` | GitHub release tag (keyword-only, default `RELEASE_TAG`) |
| `timeout` | `float` | HTTP timeout (keyword-only, default 120) |

**Returns:** `Path` — path to the extracted binary.

**Source:**

```python
def _download_and_extract_binary(
    zip_asset: str,
    canonical_name: str,
    dest: Path,
    *,
    tag: str = RELEASE_TAG,
    timeout: float = 120,
) -> Path:
    """Download a release .zip from abcfy2 and extract the ``aria2c`` binary.

    Args:
        zip_asset: Filename of the zip asset on the GitHub release.
        canonical_name: Renamed binary filename for the wheel.
        dest: Directory to save both the zip and extracted binary into.
        tag: GitHub release tag.
        timeout: HTTP download timeout in seconds.

    Returns:
        Path to the extracted binary.

    """
    url = f"https://github.com/{BINARIES_REPO}/releases/download/{tag}/{zip_asset}"
    zip_path = _download_zip(url, dest, timeout=timeout)
    return _extract_from_zip(zip_path, canonical_name)
```

**Line count:** ~7 (≤20 ✅).

**Behavioral note:** Returns `Path` instead of `None` (original returned `None`).
This is a benign signature change — no caller depends on the return value because
the original was always called for side effects. The new helpers return paths so
the orchestrator propagates them.

---

### 2.4 `_get_or_download_binary(zip_asset, canonical_name, cache_dir, *, tag) -> Path`

**Purpose:** Check the binary cache. On cache hit, return the cached path. On cache
miss, construct the download URL, download the zip, extract the binary, and return
the result. Raises `OSError` on download/extraction failure (caught by `initialize`).

**Signature:**
```python
def _get_or_download_binary(
    zip_asset: str,
    canonical_name: str,
    cache_dir: Path,
    *,
    tag: str = RELEASE_TAG,
) -> Path:
```

**Parameters:**
| Param | Type | Description |
|---|---|---|
| `zip_asset` | `str` | Filename of the zip asset on GitHub |
| `canonical_name` | `str` | Renamed binary filename |
| `cache_dir` | `Path` | Cache directory (created by caller) |
| `tag` | `str` | GitHub release tag (keyword-only, default `RELEASE_TAG`) |

**Returns:** `Path` — path to the (cached or freshly downloaded) binary.

**Raises:** `OSError` — propagated from `_download_zip` or `_extract_from_zip`.

**Source:**

```python
def _get_or_download_binary(
    zip_asset: str,
    canonical_name: str,
    cache_dir: Path,
    *,
    tag: str = RELEASE_TAG,
) -> Path:
    """Return cached binary path or download from GitHub.

    Args:
        zip_asset: Filename of the zip asset on the GitHub release.
        canonical_name: Renamed binary filename for the wheel.
        cache_dir: Directory for caching binaries (already created by caller).
        tag: GitHub release tag.

    Returns:
        Path to the binary (cached or freshly downloaded).

    Raises:
        OSError: If the download fails or the zip is missing the expected file.

    """
    binary_path = cache_dir / canonical_name

    if binary_path.exists() and binary_path.stat().st_size > 0:
        print(f"  ✓ Using cached {binary_path}")
        return binary_path

    url = f"https://github.com/{BINARIES_REPO}/releases/download/{tag}/{zip_asset}"
    zip_path = _download_zip(url, cache_dir)
    return _extract_from_zip(zip_path, canonical_name)
```

**Line count:** ~9 (≤20 ✅).

**Why this calls primitives directly:** `_get_or_download_binary` already constructs
the URL from `tag` and `zip_asset`. Calling `_download_and_extract_binary` would
redundantly reconstruct the same URL. The direct call to `_download_zip` + `_extract_from_zip`
avoids duplicate URL construction while keeping each function focused.

---

### 2.5 `Aria2BinaryHook.initialize` (refactored)

**Purpose:** Orchestrate the build hook: detect platform, ensure cache directory,
get or download binary, and register files in `force_include` and VERSION.

**Source:**

```python
def initialize(self, version: str, build_data: dict[str, Any]) -> None:
    """Run during build initialization — download binary if not cached.

    Args:
        version: The project version string (unused by this hook).
        build_data: Mutable build configuration dict from hatchling.

    """
    try:
        zip_asset, canonical_name = _detect_platform()
    except OSError:
        print("  ⚠  Unsupported platform; skipping binary bundling")
        return

    cache_dir = Path(self.root) / "aria2_bin"
    cache_dir.mkdir(parents=True, exist_ok=True)

    tag: str = self.config.get("tag", RELEASE_TAG)
    try:
        binary_path = _get_or_download_binary(
            zip_asset, canonical_name, cache_dir, tag=tag,
        )
    except OSError:
        print("  ⚠  Binary fetch failed; continuing without bundling")
        return

    force_include = build_data.setdefault("force_include", {})
    force_include[str(binary_path)] = f"aria2_bin/{canonical_name}"

    version_path = cache_dir / "VERSION"
    version_path.write_text(tag)
    force_include[str(version_path)] = "aria2_bin/VERSION"
```

**Line count:** ~20 (≤20 ✅).

**Behavioral equivalence:** Every execution path is preserved:

| Original path | Refactored path | Match |
|---|---|---|
| `_detect_platform()` raises → print + return | Same sequence in `initialize` | ✅ |
| Binary cached → print + use | Delegated to `_get_or_download_binary` | ✅ |
| Download succeeds → binary at `cache_dir/canonical_name` | `_download_zip` → `_extract_from_zip` | ✅ |
| Download fails → OSError → print + return | `_get_or_download_binary` raises; caught in `initialize` | ✅ |
| `force_include` mapping: `binary_path → aria2_bin/{name}` | Identical `setdefault` + assignment | ✅ |
| VERSION file written + force-included | Identical | ✅ |
| Tag from config: `self.config.get("tag", RELEASE_TAG)` | Identical | ✅ |
| Cache dir: `mkdir(parents=True, exist_ok=True)` | Identical | ✅ |

**Key difference from original:** The original `initialize` had a single exception
handler around `_download_and_extract_binary` inside a cache-check block. The refactored
version moves the cache check into `_get_or_download_binary` and wraps the entire
call in a try/except at the orchestration level. The net effect is identical: on any
`OSError` during fetch, the hook prints a warning and returns without modifying
`build_data`.

---

## 3. Data Flow

### 3.1 Happy Path (cache miss, download succeeds)

```
initialize()
  │
  ├─ _detect_platform()
  │    → ("aria2-x86_64-linux-musl_static.zip", "aria2c-linux-x86_64")
  │
  ├─ cache_dir = Path(self.root) / "aria2_bin"
  ├─ cache_dir.mkdir(parents=True, exist_ok=True)
  │
  ├─ _get_or_download_binary(zip_asset, canonical_name, cache_dir, tag="1.37.0")
  │    │
  │    ├─ binary_path = cache_dir / "aria2c-linux-x86_64"
  │    ├─ binary_path.exists() → False (cache miss)
  │    │
  │    ├─ url = "https://github.com/abcfy2/aria2-static-build/releases/download/1.37.0/aria2-x86_64-linux-musl_static.zip"
  │    │
  │    ├─ _download_zip(url, cache_dir)
  │    │    ├─ zip_path = cache_dir / "aria2-x86_64-linux-musl_static.zip"
  │    │    ├─ req = Request(url, headers={"Accept": "application/octet-stream"})
  │    │    ├─ urlopen(req, timeout=120) → resp
  │    │    ├─ zip_path.write_bytes(resp.read())
  │    │    ├─ print("✓ aria2-x86_64-linux-musl_static.zip (15028 KB)")
  │    │    └─ return zip_path
  │    │
  │    └─ _extract_from_zip(zip_path, "aria2c-linux-x86_64")
  │         ├─ inner_name = "aria2c"
  │         ├─ dest = cache_dir / "aria2c-linux-x86_64"
  │         ├─ ZipFile(zip_path) → zf
  │         ├─ zf.getinfo("aria2c") → info
  │         ├─ zf.open(info) → src; open(dest, "wb") → dst; dst.write(src.read())
  │         ├─ zip_path.unlink()
  │         ├─ chmod(dest, stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
  │         ├─ print("✓ aria2c-linux-x86_64 (14208 KB)")
  │         └─ return dest
  │
  ├─ force_include = build_data.setdefault("force_include", {})
  ├─ force_include["/path/to/aria2c-linux-x86_64"] = "aria2_bin/aria2c-linux-x86_64"
  ├─ version_path = cache_dir / "VERSION"
  ├─ version_path.write_text("1.37.0")
  └─ force_include["/path/to/VERSION"] = "aria2_bin/VERSION"
```

### 3.2 Cache Hit Path

```
_get_or_download_binary(zip_asset, canonical_name, cache_dir, tag)
  │
  ├─ binary_path = cache_dir / canonical_name
  ├─ binary_path.exists() → True
  ├─ binary_path.stat().st_size > 0 → True
  ├─ print("✓ Using cached aria2_bin/aria2c-linux-x86_64")
  └─ return binary_path
```

### 3.3 Error Paths

#### Unsupported platform

```
_detect_platform() → OSError
  │
initialize() catches OSError
  ├─ print("⚠  Unsupported platform; skipping binary bundling")
  └─ return (build_data unchanged)
```

#### Download failure (404 / network error)

```
_get_or_download_binary()
  └─ _download_zip()
       └─ urlopen() → HTTPError(404)
            → raise OSError("Binary zip not found at ...") from HTTPError
                 │
                 initialize() catches OSError
                   ├─ print("⚠  Binary fetch failed; continuing without bundling")
                   └─ return (build_data unchanged)
```

#### Missing inner file in zip

```
_get_or_download_binary()
  └─ _extract_from_zip()
       └─ zf.getinfo("aria2c") → KeyError
            → raise OSError("Expected 'aria2c' not found inside ...")
                 │
                 initialize() catches OSError
                   ├─ print("⚠  Binary fetch failed; continuing without bundling")
                   └─ return (build_data unchanged)
```

---

## 4. Complete Function Line Audit

| Function | Old lines | New lines | Status |
|---|---|---|---|
| `_detect_platform` | 8 | 8 | ✅ Already compliant |
| `_download_and_extract_binary` | 51 | ~7 | ✅ Well under 20 |
| `_download_zip` | — | ~14 | ✅ New helper |
| `_extract_from_zip` | — | ~18 | ✅ New helper |
| `_get_or_download_binary` | — | ~9 | ✅ New helper |
| `Aria2BinaryHook.initialize` | 36 | ~20 | ✅ At limit |

**File-level line count:**

| Category | Lines (est.) |
|---|---|
| Module docstring + imports | 15 |
| Constants (`BINARIES_REPO`, `RELEASE_TAG`, `PLATFORM_MAP`) | 18 |
| `_detect_platform` | 8 |
| `_download_zip` | 14 |
| `_extract_from_zip` | 18 |
| `_download_and_extract_binary` | 7 |
| `_get_or_download_binary` | 9 |
| `Aria2BinaryHook` class + `initialize` (incl. `PLUGIN_NAME`) | 22 |
| Blank lines between functions | ~10 |
| **Total** | **~121** |

Under 200-line file limit ✅.

---

## 5. Behavioral Equivalence

### 5.1 Byte-Identical Output

The refactoring is a pure structural decomposition. Every line of original logic is
preserved, just relocated into smaller helpers. There is:

- **No** change to URL construction
- **No** change to HTTP request headers or timeout
- **No** change to error handling chains (`HTTPError` → `OSError`, `KeyError` → `OSError`)
- **No** change to `force_include` mapping keys or values
- **No** change to VERSION file content or location
- **No** change to print output format
- **No** change to `chmod` permission bits
- **No** change to zip deletion behavior
- **No** change to cache-hit detection logic

### 5.2 Spec Compliance

Every scenario from `specs/aria2-bin/spec.md` is satisfied by the refactored code:

| Requirement | Scenario count | Status |
|---|---|---|
| Build Hook Registration | 3 scenarios | ✅ PLUGIN_NAME, pyproject.toml registration, signature — all unchanged |
| Platform Detection | 3 scenarios | ✅ `_detect_platform` unchanged |
| Binary Download | 4 scenarios | ✅ Same download logic in `_download_zip` |
| Binary Extraction | 3 scenarios | ✅ Same extraction logic in `_extract_from_zip` |
| Execution Permissions | 2 scenarios | ✅ Same chmod logic |
| Binary Caching | 4 scenarios | ✅ Cache check in `_get_or_download_binary` |
| Wheel Inclusion | 5 scenarios | ✅ Identical `force_include` + VERSION logic in `initialize` |
| Graceful Error Handling | 2 scenarios | ✅ Same try/except paths |
| Source Quality | 4 scenarios | ✅ All functions ≤20 lines, file ≤200 lines |
| Behavioral Equivalence | 2 scenarios | ✅ Same wheel output |

### 5.3 Return Value Semantics

| Function | Original return | New return | Impact |
|---|---|---|---|
| `_download_and_extract_binary` | `None` | `Path` | No caller consumes return value — safe change |
| `initialize` | `None` | `None` | No change |
| `_get_or_download_binary` | — (new) | `Path` or raises | Consumer (`initialize`) uses the return |
| `_download_zip` | — (new) | `Path` | Consumer uses the return |
| `_extract_from_zip` | — (new) | `Path` | Consumer uses the return |

### 5.4 Exception Propagation

All OSError exceptions follow the same propagation chain:

```
Download failure:
  _download_zip → OSError → _get_or_download_binary (propagates) → initialize (catches, warns, returns)

Extraction failure:
  _extract_from_zip → OSError → _get_or_download_binary (propagates) → initialize (catches, warns, returns)

Unsupported platform:
  _detect_platform → OSError → initialize (catches, warns, returns)
```

---

## 6. Edge Cases

### 6.1 Empty Cache File

**Scenario:** `aria2_bin/aria2c-linux-x86_64` exists but has size 0 (partial download).

**Flow:** `_get_or_download_binary` checks `stat().st_size > 0`. A zero-size file
fails the check, triggering a fresh download. The download overwrites the empty file.

**No difference from original:** The original `initialize` had the identical check
(`binary_path.exists() and binary_path.stat().st_size > 0`).

### 6.2 Concurrent Builds (same cache dir)

**Scenario:** Two `uv build` processes run simultaneously, sharing the same
`aria2_bin/` directory.

**Flow:** `_download_zip` writes to `cache_dir / zip_asset`. If two processes
download the same zip simultaneously, the second `write_bytes` overwrites the
first. `_extract_from_zip` extracts to `cache_dir / canonical_name` and calls
`zip_path.unlink()`. If Process A's unlink happens while Process B is reading
the same zip, Process B will fail with `FileNotFoundError`.

**Mitigation:** This is a pre-existing race condition, not introduced by the
refactoring. The original code had the same vulnerability. In practice, `uv build`
uses isolated environments and the cache dir is per-project, making concurrent
access rare.

### 6.3 Zip Without Expected Inner File

**Scenario:** GitHub release contains a zip whose internal structure differs
from the expected `aria2c` / `aria2c.exe`.

**Flow:** `_extract_from_zip` calls `zf.getinfo(inner_name)`. If the inner file
is missing, `KeyError` is caught and re-raised as `OSError`. The `OSError`
propagates through `_get_or_download_binary` to `initialize`, which catches it
and prints the warning.

**No difference from original:** Same error chain.

### 6.4 Windows: No chmod

**Scenario:** `canonical_name` ends with `.exe` (Windows platform).

**Flow:** `_extract_from_zip` sets `inner_name = "aria2c.exe"`, extracts it,
and skips `chmod`. The `if not canonical_name.endswith(".exe"):` guard is
identical to the original.

### 6.5 Release Tag Override via Config

**Scenario:** User configures `[tool.hatch.build.targets.wheel.hooks.custom]` with
a `tag = "1.38.0"` setting.

**Flow:** `initialize` reads `self.config.get("tag", RELEASE_TAG)`. If a custom
tag is set, it's passed to `_get_or_download_binary` → URL construction uses the
custom tag. The VERSION file is also written with the custom tag.

**No difference from original:** `self.config.get("tag", RELEASE_TAG)` is unchanged.

---

## 7. Test Strategy

### 7.1 Existing Test Coverage

There are no dedicated unit tests for `hatch_build.py` in the test suite. The
build hook is verified implicitly through `uv build` in the CI workflow. All
functions are exercised during the build process.

### 7.2 Build Verification (Primary)

The primary verification is a successful wheel build:

```bash
# Build the aria2-bin package
uv build --wheel -p packages/aria2-bin

# Inspect wheel contents
python -m zipfile -l dist/*.whl
```

**Expected output (Linux x86_64):**
```
aria2_bin/aria2c-linux-x86_64    (~14 MB)
aria2_bin/VERSION                (~6 bytes, "1.37.0")
aria2_bin/__init__.py            (~3 KB)
```

### 7.3 Lint Verification

```bash
# Function line limits
python scripts/lint/wc-lint.py packages/aria2-bin/hatch_build.py
# Expected: zero violations

# Ruff
ruff check packages/aria2-bin/hatch_build.py
# Expected: zero errors

# Type check
ty --strict packages/aria2-bin/hatch_build.py
# Expected: zero errors
```

### 7.4 Manual Verification Checklist

- [ ] `_detect_platform()` returns correct mapping for current platform
- [ ] `_download_zip()` produces correct zip at cache dir with expected size
- [ ] `_extract_from_zip()` produces executable binary at cache dir
- [ ] `_get_or_download_binary()` returns cached binary on second call (no re-download)
- [ ] `_get_or_download_binary()` deletes cached empty file and re-downloads
- [ ] `initialize()` sets `force_include` with correct paths
- [ ] `initialize()` writes VERSION file with correct tag
- [ ] `initialize()` respects `self.config.get("tag", …)` override
- [ ] Unsupported platform → warning printed, no crash
- [ ] Download failure (network down) → warning printed, no crash

---

## 8. Rollout Plan

### 8.1 Single File, Single PR

| Metric | Value |
|---|---|
| File modified | `packages/aria2-bin/hatch_build.py` |
| Lines added (new helpers + docstrings) | ~50 |
| Lines removed (extracted from originals) | ~55 |
| Total changed lines | ~105 |
| Review budget | 400 lines ✅ |
| PR strategy | Single PR — no chaining needed |

### 8.2 Edit Order

All edits happen in a single file. The logical edit order within the file:

| Step | Edit | Purpose |
|---|---|---|
| 1 | Add `_download_zip` after `_detect_platform` | New helper must exist before callers |
| 2 | Add `_extract_from_zip` after `_download_zip` | New helper must exist before callers |
| 3 | Rewrite `_download_and_extract_binary` as thin orchestrator | Must exist before `_get_or_download_binary` calls its primitives |
| 4 | Add `_get_or_download_binary` after `_download_and_extract_binary` | New helper must exist before `initialize` |
| 5 | Rewrite `initialize` | Calls `_get_or_download_binary` |
| 6 | Run lint checks | Verify function lines, file lines, ruff, ty |

### 8.3 Verification Order

Run these in sequence. Stop and fix if any fail:

```bash
# 1. Syntax and imports
python -c "import ast; ast.parse(open('packages/aria2-bin/hatch_build.py').read())"

# 2. Function line limits
python scripts/lint/wc-lint.py packages/aria2-bin/hatch_build.py

# 3. Lint
ruff check packages/aria2-bin/hatch_build.py

# 4. Type check
ty --strict packages/aria2-bin/hatch_build.py

# 5. Build
uv build --wheel -p packages/aria2-bin

# 6. Wheel contents
python -m zipfile -l dist/*.whl | grep aria2_bin
```

### 8.4 Rollback

```bash
git checkout packages/aria2-bin/hatch_build.py
```

The refactoring is contained entirely in one file. Reverting restores the
original state instantly.

---

## Appendix A: Naming Convention

All extracted helpers use the `_` prefix (module-private convention) and follow
the existing naming pattern of `_detect_platform`:

| Function | Pattern | Rationale |
|---|---|---|
| `_detect_platform` | `_verb_noun` | Existing |
| `_download_zip` | `_verb_noun` | Downloads a zip file |
| `_extract_from_zip` | `_verb_preposition_noun` | Extracts from a zip file |
| `_get_or_download_binary` | `_verb_or_verb_noun` | Cache-hit or download |

All names are unique within the module and do not shadow stdlib, hatchling,
or third-party names.

## Appendix B: Design Decisions Log

| Decision | Rationale | Alternatives considered |
|---|---|---|
| `_get_or_download_binary` calls `_download_zip` + `_extract_from_zip` directly | Avoids duplicate URL construction (both `_get_or_download_binary` and `_download_and_extract_binary` would construct the same URL) | Call `_download_and_extract_binary` — adds an unnecessary level of indirection |
| Keep `_download_and_extract_binary` as thin orchestrator | Backward compatibility; useful for direct callers that prefer `(zip_asset, canonical_name, dest, tag)` interface | Remove it — but it's a documented interface and costs only ~7 lines |
| `_download_and_extract_binary` returns `Path` (was `None`) | All extracted helpers return their output `Path`. The orchestrator propagates for consistency. No caller consumed the original `None`. | Return `None` as before — would break the useful return chain |
| Error handling at `initialize` level (not in `_get_or_download_binary`) | `_get_or_download_binary` is a pure function — it either returns a `Path` or raises. Error handling (warn + return) is the caller's concern. | Handle OSError inside `_get_or_download_binary` and return `Path \| None` — mixes concerns |
| All extracted helpers are module-level (not methods) | They don't use `self` or any `BuildHookInterface` state. Module-level functions are simpler to reason about and test. | Make them static/class methods — unnecessary coupling to the class |
| `tag` parameter is keyword-only (`*`) | Consistent with the original `_download_and_extract_binary` signature which used `*` for `tag` and `timeout` | Positional `tag` — less explicit at call sites |

## Appendix C: Import Compatibility

The refactoring adds no new imports and removes none. All functions use the
same stdlib modules already imported at the top of the file:

```python
import platform
import stat
import sys
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

from hatchling.builders.hooks.plugin.interface import BuildHookInterface
```

No `from __future__ import annotations` is needed — the file already has it.

## Appendix D: Code Location Map

For reviewers comparing old to new:

| Contents | Old location (lines) | New location |
|---|---|---|
| Module docstring | 1–22 | 1–22 (unchanged) |
| Imports | 24–31 | 24–31 (unchanged) |
| Constants (`BINARIES_REPO`, `RELEASE_TAG`, `PLATFORM_MAP`) | 33–67 | 33–67 (unchanged) |
| `_detect_platform` | 70–77 | 70–77 (unchanged) |
| — | — | `_download_zip` (NEW, ~14 lines) |
| — | — | `_extract_from_zip` (NEW, ~18 lines) |
| Download portion of old `_download_and_extract_binary` | 80–99 | Extracted to `_download_zip` |
| Extraction portion of old `_download_and_extract_binary` | 101–120 | Extracted to `_extract_from_zip` |
| `_download_and_extract_binary` (thin) | — | After `_extract_from_zip` (~7 lines) |
| — | — | `_get_or_download_binary` (NEW, ~9 lines) |
| `Aria2BinaryHook` class | 123–162 | After `_get_or_download_binary` |
| `PLUGIN_NAME` | 126 | Unchanged |
| `initialize` (refactored) | 128–162 | ~20 lines |
