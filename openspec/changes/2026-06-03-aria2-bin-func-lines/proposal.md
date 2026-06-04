# SDD Proposal: Refactor `hatch_build.py` to Comply with `max_function_lines: 20`

**Change ID:** `2026-06-03-aria2-bin-func-lines`
**Date:** 2026-06-03
**Status:** Draft

---

## Intent

Refactor `packages/aria2-bin/hatch_build.py` (163 lines) to comply with the `max_function_lines: 20` policy enforced by `scripts/lint/wc-lint.py` and the project's quality config (`openspec/config.yaml`). This is a **pure structural refactoring** — zero behavioral changes, zero API changes, zero changes to the hatchling build hook plugin interface.

The file must:
- Have every function/method body ≤20 lines
- Stay ≤200 total lines (currently 163 — no risk, but preserved)
- Preserve `Aria2BinaryHook.PLUGIN_NAME = "aria2-binary"`
- Preserve the `BuildHookInterface` protocol contract
- Produce byte-identical wheel output for every supported platform

---

## Scope

### In scope

| # | Function/Method | Current lines | Target lines | Strategy |
|---|---|---|---|---|
| 1 | `_download_and_extract_binary` | 48 | ≤10 (orchestrator) | Extract two module-level helpers |
| 2 | `Aria2BinaryHook.initialize` | 34 | ≤18 | Extract caching helper |

### Out of scope

- Any other file in the repository (tracked separately)
- Changes to the `BuildHookInterface` base class
- Changes to `_detect_platform` (8 lines — already compliant ✅)
- Changes to `PLATFORM_MAP`, `BINARIES_REPO`, `RELEASE_TAG` constants
- Adding new tests (existing build verification suffices)
- Changes to test files or CI workflows
- Behavioral changes of any kind

---

## Affected Areas

### Directly modified

| File | Change |
|---|---|
| `packages/aria2-bin/hatch_build.py` | Refactor two functions; add two module-level helpers |

### Unchanged (must keep working)

| Artifact | Why |
|---|---|
| `hatchling.builders.hooks.plugin.interface.BuildHookInterface` | Base class — not modified |
| `pyproject.toml` hook registration (`[tool.hatch.build.targets.wheel.hooks.custom]`) | No path or name change |
| `aria2_bin/` directory structure | Cache location unchanged |
| `Aria2BinaryHook.PLUGIN_NAME` | Plugin name must remain `"aria2-binary"` |
| Wheel output (`force_include` mapping) | Same keys, same values |

---

## Architecture & Design

### Strategy: Extract Module-Level Private Helpers

The refactoring follows the same pattern established in the SDK refactoring (`2026-06-03-func-lines-sdk`): decompose each violating function along its natural seams into focused, single-responsibility helpers ≤20 lines each.

#### Principle

Each helper does **one thing**:
- **Download** only: HTTP GET, error handling, print progress
- **Extract** only: open zip, read inner file, chmod, delete zip, print result
- **Cache check** only: stat, decide to download or skip
- **Initialize** only: orchestrate detection → cache → force_include

### 1. `_download_and_extract_binary` → `_download_zip` + `_extract_from_zip` + thin orchestrator

#### Problem

`_download_and_extract_binary` (48 lines) mixes four responsibilities:
1. URL construction
2. HTTP download with error handling and progress output
3. ZIP extraction with inner name resolution
4. Post-extraction cleanup (delete zip, chmod)

#### Solution

**Module-level helper `_download_zip(url, dest, timeout) -> Path`**:

```python
def _download_zip(url: str, dest: Path, *, timeout: float = 120) -> Path:
    """Download a zip from *url* to *dest* and return the local path.

    Raises ``OSError`` on HTTP 404 or any download failure.
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

**(~12–14 lines, under 20)** ✅

**Module-level helper `_extract_from_zip(zip_path, canonical_name) -> Path`**:

```python
def _extract_from_zip(zip_path: Path, canonical_name: str) -> Path:
    """Extract binary from *zip_path*, rename to *canonical_name*, and return path.

    Cleans up the zip file after extraction. Makes the binary executable
    on Unix platforms. Raises ``OSError`` if the expected inner file is missing.
    """
    inner_name = "aria2c.exe" if canonical_name.endswith(".exe") else "aria2c"
    dest = zip_path.parent

    with zipfile.ZipFile(zip_path) as zf:
        try:
            info = zf.getinfo(inner_name)
        except KeyError:
            msg = f"Expected {inner_name!r} not found inside {zip_path.name}"
            raise OSError(msg) from None

        binary_path = dest / canonical_name
        with zf.open(info) as src, open(binary_path, "wb") as dst:
            dst.write(src.read())

    zip_path.unlink()

    if not canonical_name.endswith(".exe"):
        _mode = binary_path.stat().st_mode
        binary_path.chmod(_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    print(f"     ✓ {canonical_name} ({binary_path.stat().st_size / 1024:.0f} KB)")
    return binary_path
```

**(~16–18 lines, under 20)** ✅

**Refactored `_download_and_extract_binary` (thin orchestrator)**:

```python
def _download_and_extract_binary(
    zip_asset: str,
    canonical_name: str,
    dest: Path,
    *,
    tag: str = RELEASE_TAG,
    timeout: float = 120,
) -> None:
    """Download a release .zip from abcfy2 and extract the ``aria2c`` binary."""
    url = f"https://github.com/{BINARIES_REPO}/releases/download/{tag}/{zip_asset}"
    zip_path = _download_zip(url, dest, timeout=timeout)
    _extract_from_zip(zip_path, canonical_name)
```

**(~7 lines, well under 20)** ✅

#### Behavioral equivalence verification

| Step | Original | New | Match |
|------|----------|-----|-------|
| URL construction | Same `f"https://github.com/{BINARIES_REPO}/releases/download/{tag}/{zip_asset}"` | Same | ✅ |
| HTTP download | `urllib.request.urlopen(req, timeout=timeout)` → `zip_path.write_bytes(resp.read())` | Same | ✅ |
| HTTP 404 handling | `if e.code == 404: raise OSError(msg) from e` | Same | ✅ |
| Download progress | `print(f"  ⬇  Downloading {url} …")` + `print(f"     ✓ {zip_path.name} ({size} KB)")` | Same | ✅ |
| Inner name resolution | `"aria2c.exe" if canonical_name.endswith(".exe") else "aria2c"` | Same | ✅ |
| ZIP extraction | `zf.getinfo(inner_name)` → `zf.open(info)` → `write_bytes` | Same | ✅ |
| ZIP deletion | `zip_path.unlink()` | Same | ✅ |
| chmod +x | `binary_path.chmod(_mode \| S_IXUSR \| S_IXGRP \| S_IXOTH)` | Same | ✅ |
| Extraction progress | `print(f"     ✓ {canonical_name} ({size} KB)")` | Same | ✅ |

All output is byte-identical. **No behavioral change.** 🔒

### 2. `Aria2BinaryHook.initialize` → Extract `_get_or_download_binary`

#### Problem

`Aria2BinaryHook.initialize` (34 lines) combines:
1. Platform detection with OSError handling
2. Cache directory creation
3. Cache check + conditional download
4. `force_include` setup
5. VERSION file write

#### Solution

**Module-level helper `_get_or_download_binary(zip_asset, canonical_name, cache_dir, tag) -> Path | None`**:

```python
def _get_or_download_binary(
    zip_asset: str,
    canonical_name: str,
    cache_dir: Path,
    tag: str = RELEASE_TAG,
) -> Path | None:
    """Return cached binary path or download it. Returns ``None`` on failure."""
    binary_path = cache_dir / canonical_name

    if binary_path.exists() and binary_path.stat().st_size > 0:
        print(f"  ✓ Using cached {binary_path}")
        return binary_path

    try:
        _download_and_extract_binary(zip_asset, canonical_name, cache_dir, tag=tag)
    except OSError:
        print("  ⚠  Binary fetch failed; continuing without bundling")
        return None

    return binary_path
```

**(~12–14 lines, under 20)** ✅

**Refactored `Aria2BinaryHook.initialize`**:

```python
def initialize(self, version: str, build_data: dict[str, Any]) -> None:
    """Run during build initialization — download binary if not cached."""
    try:
        zip_asset, canonical_name = _detect_platform()
    except OSError:
        print("  ⚠  Unsupported platform; skipping binary bundling")
        return

    cache_dir = Path(self.root) / "aria2_bin"
    cache_dir.mkdir(parents=True, exist_ok=True)

    tag: str = self.config.get("tag", RELEASE_TAG)
    binary_path = _get_or_download_binary(zip_asset, canonical_name, cache_dir, tag)
    if binary_path is None:
        return

    force_include = build_data.setdefault("force_include", {})
    force_include[str(binary_path)] = f"aria2_bin/{canonical_name}"

    version_path = cache_dir / "VERSION"
    version_path.write_text(tag)
    force_include[str(version_path)] = "aria2_bin/VERSION"
```

**(~16–18 lines, under 20)** ✅

#### Behavioral equivalence verification

| Scenario | Original | New | Match |
|----------|----------|-----|-------|
| Unsupported platform | `_detect_platform` → OSError → print + return | Same | ✅ |
| Binary already cached | `exists() && st_size > 0` → print + use | Same (inside `_get_or_download_binary`) | ✅ |
| Download succeeds | `_download_and_extract_binary` → uses binary | Same | ✅ |
| Download fails | OSError → print + return | Same | ✅ |
| `force_include` mapping | `binary_path → aria2_bin/{canonical_name}` | Same | ✅ |
| VERSION file | `version_path.write_text(tag)` + force_include | Same | ✅ |
| Tag from config | `self.config.get("tag", RELEASE_TAG)` | Same | ✅ |
| Cache dir creation | `cache_dir.mkdir(parents=True, exist_ok=True)` | Same | ✅ |

All execution paths are preserved. **No behavioral change.** 🔒

---

## File-by-File Summary

### `packages/aria2-bin/hatch_build.py`

| Before | After |
|--------|-------|
| Module-level helpers: `_detect_platform`, `_download_and_extract_binary` | Module-level helpers: `_detect_platform`, `_download_zip`, `_extract_from_zip`, `_download_and_extract_binary` (thin), `_get_or_download_binary` |
| `_download_and_extract_binary`: 48 lines (download + extract + chmod + cleanup) | `_download_zip`: ~14 lines (download only) |
| — | `_extract_from_zip`: ~18 lines (extract + chmod + cleanup) |
| — | `_download_and_extract_binary`: ~7 lines (orchestrator) |
| `Aria2BinaryHook.initialize`: 34 lines (detect + cache + download + force_include) | `Aria2BinaryHook.initialize`: ~18 lines (orchestrator) |
| — | `_get_or_download_binary`: ~14 lines (cache logic) |
| File total: ~163 lines | File total: ~175–185 lines (under 200 ✅) |

### Function line audit

| Function | Before | After | Status |
|----------|--------|-------|--------|
| `_detect_platform` | 8 | 8 | ✅ Already compliant |
| `_download_and_extract_binary` | 48 | ~7 | ✅ Well under 20 |
| `_download_zip` | — | ~14 | ✅ New helper |
| `_extract_from_zip` | — | ~18 | ✅ New helper |
| `_get_or_download_binary` | — | ~14 | ✅ New helper |
| `Aria2BinaryHook.initialize` | 34 | ~18 | ✅ Under 20 |

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| **Import shadowing** — new functions could collide with stdlib or hatchling names | Low | Low | Names have `_` prefix (module-private convention). `_download_zip`, `_extract_from_zip`, `_get_or_download_binary` — all unique in this file. |
| **Coverage regression** — new helpers not directly tested | Low | Low | All helpers are exercised through `initialize`, which is invoked during `uv build`. Existing build tests cover all paths. |
| **Type checking** — `Path | None` return type not supported on Python <3.10 | None | Project targets **Python ≥3.14** (`openspec/config.yaml`). `X \| None` syntax is fully supported. |
| **`_download_zip` dest filename** — using `Path(url).name` could produce unexpected names | Low | Low | The URL always ends with `{zip_asset}` (e.g., `aria2-x86_64-linux-musl_static.zip`). `Path(url).name` reliably extracts the last path segment. No `.git` or trailing-slash URLs are involved. |
| **`_extract_from_zip` zip_path.parent assumption** — zip and dest in same directory | Low | Low | Always called with `dest / zip_asset` from the orchestrator. The parent is always `dest`. |
| **Build hook interface contract broken** | Low | High | `PLUGIN_NAME` unchanged. `initialize` signature `(self, version, build_data)` unchanged. `self.root`, `self.config` access preserved. |

---

## Rollback Plan

If the refactoring breaks the build or produces incorrect wheels:

1. **Revert** the file:
   ```bash
   git checkout packages/aria2-bin/hatch_build.py
   ```
2. **Verify** the build still works:
   ```bash
   uv build --wheel -p packages/aria2-bin
   ```
3. **Inspect** wheel contents to confirm no regression:
   ```bash
   python -m zipfile -l dist/*.whl
   ```
4. **File a follow-up issue** with the failure details.

The refactoring is purely structural (extract + delegate). All original code is preserved in git history at HEAD, so recovery is instant and safe.

---

## Success Criteria

All of the following must pass:

- [ ] `ruff check packages/aria2-bin/hatch_build.py` — zero errors
- [ ] `ty --strict packages/aria2-bin/hatch_build.py` — zero type errors
- [ ] `python scripts/lint/wc-lint.py packages/aria2-bin/hatch_build.py` — zero function-line violations
- [ ] Each function/method body is ≤20 lines
- [ ] File is ≤200 lines
- [ ] `uv build --wheel -p packages/aria2-bin` succeeds
- [ ] Wheel contents match pre-refactoring (same files in `aria2_bin/`)
- [ ] `Aria2BinaryHook.PLUGIN_NAME` equals `"aria2-binary"`

---

## Chained PR Forecast

| Metric | Value |
|--------|-------|
| Estimated new lines added | ~30 (2 new helpers) |
| Estimated lines modified | ~55 (refactored bodies + removed code) |
| Estimated total changed lines | ~85 |
| Review budget (400 lines) | ✅ **Comfortable** — single PR, no chaining needed |
| Chained PRs recommended | **No** |

---

## Appendix: Detailed Decomposition

### `_download_and_extract_binary` Current → Proposed

```
Current (48 lines)                              Proposed
─────────────────────                          ─────────────────────
def _download_and_extract_binary(              def _download_and_extract_binary(
    zip_asset, canonical_name, dest,               zip_asset, canonical_name, dest,
    *, tag, timeout,                                *, tag, timeout,
):
    url = f".../{tag}/{zip_asset}"            ):       # ~2 lines
    zip_path = dest / zip_asset                       url = f".../{tag}/{zip_asset}"
    print(f"  ⬇  Downloading {url} …")               zip_path = _download_zip(url, dest, timeout=timeout)  # ~1 line
    req = Request(url, ...)                    →      _extract_from_zip(zip_path, canonical_name)          # ~1 line
    try:
        with urlopen(req, timeout) as resp:
            zip_path.write_bytes(resp.read())
    except HTTPError as e:
        if e.code == 404:
            msg = f"Binary zip not found at {url}."
            raise OSError(msg) from e
        raise

    print(f"     ✓ {zip_path.name} ({size} KB)")

    inner_name = "aria2c.exe" if can.ends with ".exe" else "aria2c"

    with ZipFile(zip_path) as zf:
        try:
            info = zf.getinfo(inner_name)
        except KeyError:
            raise OSError(...)

        binary_path = dest / canonical_name           # New helper: _download_zip (12-14 lines)
        with zf.open(info) as src, open(bp, "wb"):         def _download_zip(url, dest, *, timeout):
            dst.write(src.read())                              zip_path = dest / Path(url).name
                                                              print(f"  ⬇  Downloading {url} …")
    zip_path.unlink()                                       req = Request(url, headers={"Accept": "..."})
                                                              try:
    if not canonical_name.endswith(".exe"):                          with urlopen(req, timeout=timeout) as resp:
        _mode = binary_path.stat().st_mode                               zip_path.write_bytes(resp.read())
        binary_path.chmod(_mode | S_IXUSR | ...)                    except HTTPError as e:
                                                                         if e.code == 404:
    print(f"     ✓ {canonical_name} ({size} KB)")                          raise OSError(...) from e
                                                                         raise
                                                              print(f"     ✓ {zip_path.name} ({size} KB)")
                                                              return zip_path

                                                           # New helper: _extract_from_zip (16-18 lines)
                                                           def _extract_from_zip(zip_path, canonical_name):
                                                               inner_name = "aria2c.exe" if can.endswith(".exe") else "aria2c"
                                                               dest = zip_path.parent
                                                               with ZipFile(zip_path) as zf:
                                                                   try:
                                                                       info = zf.getinfo(inner_name)
                                                                   except KeyError:
                                                                       raise OSError(...)
                                                                   binary_path = dest / canonical_name
                                                                   with zf.open(info) as src, open(bp, "wb"):
                                                                       dst.write(src.read())
                                                               zip_path.unlink()
                                                               if not canonical_name.endswith(".exe"):
                                                                   _mode = bp.stat().st_mode
                                                                   bp.chmod(_mode | S_IXUSR | ...)
                                                               print(f"     ✓ {canonical_name} ({size} KB)")
                                                               return binary_path
```

### `Aria2BinaryHook.initialize` Current → Proposed

```
Current (34 lines)                              Proposed
─────────────────────                          ─────────────────────
def initialize(self, version, build_data):     def initialize(self, version, build_data):
    try:                                            try:
        zip_asset, canonical_name = _detect_platform()   zip_asset, canonical_name = _detect_platform()
    except OSError:                                 except OSError:
        print("  ⚠  Unsupported platform; skipping")     print("  ⚠  Unsupported platform; skipping")
        return                                              return

    cache_dir = Path(self.root) / "aria2_bin"       cache_dir = Path(self.root) / "aria2_bin"
    cache_dir.mkdir(parents=True, exist_ok=True)    cache_dir.mkdir(parents=True, exist_ok=True)

    binary_path = cache_dir / canonical_name         tag = self.config.get("tag", RELEASE_TAG)
    tag = self.config.get("tag", RELEASE_TAG)  →     binary_path = _get_or_download_binary(
                                                          zip_asset, canonical_name, cache_dir, tag,
    if not (binary_path.exists() and st_size > 0):   )
        try:                                         if binary_path is None:
            _download_and_extract_binary(...)              return
        except OSError:
            print("  ⚠  Binary fetch failed; skipping")  force_include = build_data.setdefault("force_include", {})
            return                                       force_include[str(binary_path)] = f"aria2_bin/{canonical_name}"
    else:
        print(f"  ✓ Using cached {binary_path}")          version_path = cache_dir / "VERSION"
                                                          version_path.write_text(tag)
    force_include = build_data.setdefault("force_include", {})  force_include[str(version_path)] = "aria2_bin/VERSION"
    force_include[str(binary_path)] = f"aria2_bin/{canonical_name}"

    version_path = cache_dir / "VERSION"            # New helper: _get_or_download_binary (12-14 lines)
    version_path.write_text(tag)                    def _get_or_download_binary(zip_asset, canonical_name, cache_dir, *, tag):
    force_include[str(version_path)] = "aria2_bin/VERSION"  binary_path = cache_dir / canonical_name
                                                            if binary_path.exists() and binary_path.stat().st_size > 0:
                                                                print(f"  ✓ Using cached {binary_path}")
                                                                return binary_path
                                                            try:
                                                                _download_and_extract_binary(...)
                                                            except OSError:
                                                                print("  ⚠  Binary fetch failed; skipping")
                                                                return None
                                                            return binary_path
```
