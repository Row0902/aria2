# SDD Tasks: Refactor `hatch_build.py` — Extract Module-Level Helpers

**Change ID:** `2026-06-03-aria2-bin-func-lines`
**Strategy:** Pure structural extraction — zero behavioral changes, zero API changes

---

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~96 (41 added, 55 removed) |
| 400-line budget risk | Low |
| Chained PRs recommended | No |
| Suggested split | Single PR |
| Delivery strategy | single-pr |
| Chain strategy | not-applicable |

Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: not-applicable
400-line budget risk: Low

---

## Task Summary

| # | Task | Phase | File | Est. lines |
|---|---|---|---|---|
| 1 | Establish baseline — confirm wc-lint violations | RED | — | 0 |
| 2 | Extract `_extract_from_zip` helper | GREEN | `hatch_build.py` | +18 |
| 3 | Extract `_download_zip` helper | GREEN | `hatch_build.py` | +14 |
| 4 | Rewrite `_download_and_extract_binary` as orchestrator | GREEN | `hatch_build.py` | ~–41 |
| 5 | Intermediate verification | VERIFY | — | 0 |
| 6 | Extract `_get_or_download_binary` helper | GREEN | `hatch_build.py` | +9 |
| 7 | Rewrite `Aria2BinaryHook.initialize` as orchestrator | GREEN | `hatch_build.py` | ~–14 |
| 8 | Final verification | VERIFY | — | 0 |

All tasks operate on a single file: `packages/aria2-bin/hatch_build.py`.

---

## Task 1: Establish Baseline — Confirm Current Violations

**Phase:** RED
**Purpose:** Confirm `wc-lint.py` detects the two function-line violations before any edits. Also confirm the build still works as of HEAD.

### Steps

1. Run `python scripts/lint/wc-lint.py packages/aria2-bin/hatch_build.py`
   - **Expected:** Two `[FAIL]` lines:
     - `_download_and_extract_binary` (~48 lines, exceeds 20)
     - `Aria2BinaryHook.initialize` (~34 lines, exceeds 20)

2. Run `ruff check packages/aria2-bin/hatch_build.py`
   - **Expected:** Zero errors.

3. Run `ty --strict packages/aria2-bin/hatch_build.py`
   - **Expected:** Zero errors (or note any pre-existing findings).

4. Run `uv build --wheel -p packages/aria2-bin`
   - **Expected:** Build succeeds on current platform.

5. Inspect wheel: `python -m zipfile -l dist/*.whl | grep aria2_bin`
   - **Expected:** `aria2_bin/` entries present (binary + VERSION).

### Verification
- [ ] wc-lint shows exactly 2 function-line violations
- [ ] ruff clean
- [ ] ty clean
- [ ] `uv build` succeeds
- [ ] Wheel contains expected `aria2_bin/` files

---

## Task 2: Extract `_extract_from_zip` Helper

**Phase:** GREEN
**File:** `packages/aria2-bin/hatch_build.py`
**Lines added:** ~18 (new function + blank + docstring)
**Lines removed:** 0 (extraction from original happens in Task 4)

### What to do

Insert `_extract_from_zip` as a new module-level function **after** `_detect_platform` and **before** `_download_and_extract_binary`.

This is a pure *addition* — do NOT modify `_download_and_extract_binary` yet. The function is added standalone and will be wired in Task 4.

### Source (copy exactly from design §2.2)

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

### Key gotchas

- `dest = zip_path.parent / canonical_name` — the binary is written to the same directory as the zip (the cache dir). This is correct because `_download_zip` writes the zip into `cache_dir`, so `zip_path.parent` is `cache_dir`.
- `from None` on the `KeyError → OSError` chain — preserves the original's exception semantics.
- The `chmod` guard uses `not canonical_name.endswith(".exe")` — identical to the original.

### Verification
- [ ] File still parses: `python -c "import ast; ast.parse(open('packages/aria2-bin/hatch_build.py').read())"`
- [ ] No import errors: `python -c "import packages.aria2-bin.hatch_build"` (may fail due to `hatchling` import — that's OK at this stage)
- [ ] Function is ≤20 lines (count: ~18)

---

## Task 3: Extract `_download_zip` Helper

**Phase:** GREEN
**File:** `packages/aria2-bin/hatch_build.py`
**Lines added:** ~14

### What to do

Insert `_download_zip` as a new module-level function **after** `_extract_from_zip` and **before** `_download_and_extract_binary`.

Again, this is a pure *addition* — `_download_and_extract_binary` is not modified yet.

### Source (copy exactly from design §2.1)

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

### Key gotchas

- `zip_path = dest / Path(url).name` — `url` always ends with the zip filename (e.g. `aria2-x86_64-linux-musl_static.zip`). `Path(url).name` extracts just the filename.
- The `timeout` parameter is keyword-only (`*`) — consistent with the original `_download_and_extract_binary` signature.
- HTTP 404 is re-raised as `OSError` with chaining (`from e`) — same as original.

### Verification
- [ ] File still parses: `python -c "import ast; ast.parse(open('packages/aria2-bin/hatch_build.py').read())"`
- [ ] Function is ≤20 lines (count: ~14)
- [ ] Module-level function order: `_detect_platform` → `_extract_from_zip` → `_download_zip` → `_download_and_extract_binary`

---

## Task 4: Rewrite `_download_and_extract_binary` as Thin Orchestrator

**Phase:** GREEN
**File:** `packages/aria2-bin/hatch_build.py`
**Lines:** Replace ~48-line body with ~7-line body

### What to do

Replace the entire body of `_download_and_extract_binary` with a thin orchestrator that:
1. Constructs the URL (same as before)
2. Calls `_download_zip(url, dest, timeout=timeout)`
3. Calls `_extract_from_zip(zip_path, canonical_name)`
4. Returns the `Path` from `_extract_from_zip`

The function signature stays **unchanged** except the return type changes from `None` to `Path`.

### Source (copy exactly from design §2.3)

Replace the function body so the complete function becomes:

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

### Key gotchas

- Return type changes from `None` → `Path`. No existing caller depends on the return value — the original was always called for side effects. This change is benign.
- All original logic (download, extract, chmod, cleanup, progress printing) is preserved inside `_download_zip` and `_extract_from_zip`. The orchestrator just composes them.
- The docstring is updated to reflect the `Returns:` clause.

### Verification
- [ ] File still parses: `python -c "import ast; ast.parse(open('packages/aria2-bin/hatch_build.py').read())"`
- [ ] Function is ≤20 lines (count: ~7)
- [ ] `grep -c "def _download_and_extract_binary"` returns 1 (no duplicate)
- [ ] The function body no longer contains `urllib.request`, `zipfile.ZipFile`, or `chmod` calls — those belong to helpers only

---

## Task 5: Intermediate Verification

**Phase:** VERIFY
**Purpose:** After extracting the first two helpers and wiring them, confirm everything still works before tackling `initialize`.

### Steps

1. **AST parse:**
   ```bash
   python -c "import ast; ast.parse(open('packages/aria2-bin/hatch_build.py').read())"
   ```
   - **Expected:** No `SyntaxError`.

2. **wc-lint:**
   ```bash
   python scripts/lint/wc-lint.py packages/aria2-bin/hatch_build.py
   ```
   - **Expected:** Only `Aria2BinaryHook.initialize` still violates (34 lines > 20). The new helpers (`_extract_from_zip` ~18, `_download_zip` ~14) and the refactored `_download_and_extract_binary` (~7) should all pass.
   - `_download_and_extract_binary` violation should be **gone**.

3. **Ruff:**
   ```bash
   ruff check packages/aria2-bin/hatch_build.py
   ```
   - **Expected:** Zero errors.

4. **Type check:**
   ```bash
   ty --strict packages/aria2-bin/hatch_build.py
   ```
   - **Expected:** Zero errors.

5. **Build:**
   ```bash
   uv build --wheel -p packages/aria2-bin
   ```
   - **Expected:** Build succeeds on the current platform. The wheel should contain the same `aria2_bin/` files as the baseline.

6. **Wheel inspection:**
   ```bash
   python -m zipfile -l dist/*.whl | grep aria2_bin
   ```
   - **Expected:** Same output as baseline (Task 1).

### Verification
- [ ] AST parses without error
- [ ] wc-lint: only `Aria2BinaryHook.initialize` fails (≤1 violation)
- [ ] ruff: zero errors
- [ ] ty: zero errors
- [ ] `uv build` succeeds
- [ ] Wheel contents match baseline

> **If anything fails here, stop and debug before proceeding to Task 6.**

---

## Task 6: Extract `_get_or_download_binary` Helper

**Phase:** GREEN
**File:** `packages/aria2-bin/hatch_build.py`
**Lines added:** ~9

### What to do

Insert `_get_or_download_binary` as a new module-level function **after** `_download_and_extract_binary` and **before** the `Aria2BinaryHook` class.

This helper:
1. Constructs `binary_path = cache_dir / canonical_name`
2. On cache hit (`exists()` and `st_size > 0`): prints message, returns path
3. On cache miss: constructs URL, calls `_download_zip`, calls `_extract_from_zip`, returns result
4. Lets `OSError` propagate (caught by caller — `initialize`)

Note: this helper calls `_download_zip` + `_extract_from_zip` **directly** rather than going through `_download_and_extract_binary`, because it already constructs the URL from `tag` and `zip_asset`. Calling `_download_and_extract_binary` would redundantly reconstruct the same URL.

### Source (copy exactly from design §2.4)

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

### Key gotchas

- `cache_dir` is expected to already exist (created by `initialize` before calling this function).
- The cache-hit check `binary_path.exists() and binary_path.stat().st_size > 0` is identical to the original `initialize` logic.
- Empty cache files (size 0) are treated as a cache miss — this matches the original behavior.
- `OSError` is deliberately **not** caught here. It propagates to `initialize`, which handles the warning-print-and-return. This keeps `_get_or_download_binary` a pure function (returns Path or raises).
- Direct `_download_zip` + `_extract_from_zip` call (not through `_download_and_extract_binary`) avoids duplicate URL construction.

### Verification
- [ ] Function is ≤20 lines (count: ~9)
- [ ] Module-level function order: `_detect_platform` → `_extract_from_zip` → `_download_zip` → `_download_and_extract_binary` → `_get_or_download_binary` → `Aria2BinaryHook`

---

## Task 7: Rewrite `Aria2BinaryHook.initialize` as Thin Orchestrator

**Phase:** GREEN
**File:** `packages/aria2-bin/hatch_build.py`
**Lines:** Replace ~34-line body with ~20-line body

### What to do

Rewrite `initialize` to:
1. Try `_detect_platform()` — catch `OSError` → warn + return (unchanged)
2. Create `cache_dir` + `mkdir` (unchanged)
3. Read tag from config (unchanged)
4. Call `_get_or_download_binary(...)` — catch `OSError` → warn + return
5. Set `force_include` mapping (unchanged)
6. Write VERSION file + force-include it (unchanged)

The key difference from the original: the cache-check + download block is replaced by a single `_get_or_download_binary()` call with its own `try/except`. The `_detect_platform` exception handler remains separate (as it was before).

### Source (copy exactly from design §2.5)

Replace the method body so the complete method becomes:

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

### Key gotchas

- **Two separate try/except blocks** — one for `_detect_platform`, one for `_get_or_download_binary`. This is intentional. The original had a single try/except that covered both `_detect_platform` and `_download_and_extract_binary` because the cache check was inline. Now the concerns are separated.
- The `OSError` from `_get_or_download_binary` covers both download failures (404, network) and extraction failures (missing inner file) — same coverage as the original.
- `PLUGIN_NAME = "aria2-binary"` is unchanged.
- `force_include` uses `setdefault` to avoid overwriting entries from other hooks.
- `tag` from config defaults to `RELEASE_TAG` — identical to original.

### Verification
- [ ] Method is ≤20 lines (count: ~20)
- [ ] `PLUGIN_NAME` is still `"aria2-binary"`
- [ ] `grep -n "def initialize" packages/aria2-bin/hatch_build.py` shows exactly one definition
- [ ] The method body no longer contains direct `_download_and_extract_binary`, `binary_path.exists()`, or zip download logic

---

## Task 8: Final Verification

**Phase:** VERIFY
**Purpose:** Confirm all quality gates pass and the refactored code produces identical output.

### Step 8.1: AST Syntax

```bash
python -c "import ast; ast.parse(open('packages/aria2-bin/hatch_build.py').read())"
```
- **Expected:** No `SyntaxError`.

### Step 8.2: wc-lint — Zero Violations

```bash
python scripts/lint/wc-lint.py packages/aria2-bin/hatch_build.py
```
- **Expected:**
  ```
  ✅ wc-lint: all files within thresholds (0 warnings).
  ```
- All functions must be ≤20 lines:
  - `_detect_platform`: 8 ✅
  - `_extract_from_zip`: ~18 ✅
  - `_download_zip`: ~14 ✅
  - `_download_and_extract_binary`: ~7 ✅
  - `_get_or_download_binary`: ~9 ✅
  - `Aria2BinaryHook.initialize`: ~20 ✅
- File total ≤200 lines (target ~121, original 163)

### Step 8.3: Ruff Lint

```bash
ruff check packages/aria2-bin/hatch_build.py
```
- **Expected:** Zero errors.

### Step 8.4: Type Check

```bash
ty --strict packages/aria2-bin/hatch_build.py
```
- **Expected:** Zero errors.

### Step 8.5: Wheel Build

```bash
uv build --wheel -p packages/aria2-bin
```
- **Expected:** Build succeeds. This exercises all paths: `_detect_platform` → `_get_or_download_binary` → `_download_zip` → `_extract_from_zip` → `force_include` setup → VERSION write.

### Step 8.6: Wheel Contents Match Baseline

```bash
python -m zipfile -l dist/*.whl | grep aria2_bin
```
- **Expected:** Output matches the baseline from Task 1. Specifically:
  - Binary entry: `aria2_bin/aria2c-{platform}` (e.g. `aria2c-linux-x86_64`)
  - VERSION entry: `aria2_bin/VERSION`
  - `aria2_bin/__init__.py` (unchanged)

### Step 8.7: Full-Repo wc-lint (regression check)

```bash
python scripts/lint/wc-lint.py packages apps
```
- **Expected:** Zero violations across all packages. This confirms the refactoring didn't leave any other file in violation.

### Step 8.8: Git Diff Review Checklist

Review the diff manually for these invariants:
- [ ] `PLUGIN_NAME = "aria2-binary"` — unchanged
- [ ] `BINARIES_REPO` — unchanged
- [ ] `RELEASE_TAG` — unchanged
- [ ] `PLATFORM_MAP` — unchanged
- [ ] `_detect_platform` — unchanged
- [ ] No new imports added
- [ ] No existing imports removed
- [ ] All print output strings identical to original
- [ ] All `force_include` keys/values identical to original
- [ ] `self.config.get("tag", RELEASE_TAG)` — unchanged
- [ ] `cache_dir.mkdir(parents=True, exist_ok=True)` — unchanged

---

## Dependency Graph

```
Task 1 (baseline)
  │
  ├─► Task 2 (_extract_from_zip)
  │     │
  │     └─► Task 3 (_download_zip)
  │           │
  │           └─► Task 4 (refactor _download_and_extract_binary)
  │                 │
  │                 └─► Task 5 (intermediate verification)
  │                       │
  │                       └─► Task 6 (_get_or_download_binary)
  │                             │
  │                             └─► Task 7 (refactor initialize)
  │                                   │
  │                                   └─► Task 8 (final verification)
  │
  (Tasks 2–3 can be swapped — they're independent additions)
```

---

## Rollback

If any verification step fails, revert the single file:

```bash
git checkout packages/aria2-bin/hatch_build.py
```

Then re-run Task 1 to confirm the baseline is restored.

---

## Completion Checklist

- [ ] `ruff check` — zero errors
- [ ] `ty --strict` — zero errors
- [ ] `wc-lint.py` — zero function-line violations
- [ ] File total ≤200 lines
- [ ] `uv build --wheel` succeeds
- [ ] Wheel contents match baseline
- [ ] `PLUGIN_NAME` is `"aria2-binary"`
- [ ] All 5 helpers + 1 class method are ≤20 lines
