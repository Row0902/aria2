# Implementation Tasks: CLI Modularization

**Change:** `cli-modularization` (issue #9)
**Date:** 2026-06-03
**Strict TDD:** Yes (refactoring — verify-at-each-step pattern replaces RED→GREEN)

---

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~265 (152 additions + 113 deletions) |
| 400-line budget risk | Low |
| Chained PRs recommended | No |
| Suggested split | Single PR |
| Delivery strategy | single-pr |
| Chain strategy | size-exception |

---

Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: size-exception
400-line budget risk: Low

---

## Task Graph

```
T1 (config.py) ─────────────────────────────────────────────────────┐
                                                                     │
T2 (finder.py) ───────────────────────────────────────────┐          │
                                                           │          │
T3 (commands/__init__.py) ──► T4 (commands/start.py) ─────┤──────────┤
                                  imports finder, config   │          │
                                                           │          │
                              T5 (commands/status.py) ─────┤──────────┤
                                  imports config           │          │
                                                           │          │
                              T6 (rewrite __init__.py) ◄───┴──────────┘
                                  imports from all above
                                                           │
                              T7 (smoke test) ◄────────────┘
                                                           │
                              T8 (lint + typecheck + wc-lint)
```

T1 and T2 have no inter-dependencies and can run in parallel.
T3 depends on nothing (it's a shell). T4 and T5 depend on T1+T2 (they import from them).
T6 depends on T1–T5 (it imports from all new modules).
T7 depends on T6. T8 depends on T7.

---

## Task Breakdown

### T1 — Create `config.py` with shared constants and `_fmt_speed`

**File:** `apps/cli/src/cli/config.py` (new, ~22 lines)

**Dependencies:** None (no new-module imports).

**Steps:**

1. Create `apps/cli/src/cli/config.py` with:
   - `from __future__ import annotations`
   - `DEFAULT_PORT: int = 6800`
   - `DEFAULT_HOST: str = "localhost"`
   - `def _fmt_speed(bps: int) -> str` — exact copy of the 8-line function currently at `__init__.py` lines 140–147, preserving formatting logic verbatim.

2. Verify: `python -c "from cli.config import DEFAULT_PORT, DEFAULT_HOST, _fmt_speed; assert _fmt_speed(2_500_000) == '2.5 MB/s'; assert _fmt_speed(42_000) == '42 KB/s'; assert _fmt_speed(900) == '900 B/s'"`

**Lines:** ~22 (all new).
**Risk:** None — pure extraction of constants + one helper, no behavioral change.
**Verification:** Manual import + assertion checks as above.

---

### T2 — Create `finder.py` with `find_binary()`

**File:** `apps/cli/src/cli/finder.py` (new, ~25 lines)

**Dependencies:** None (only stdlib + optional `aria2_bin`).

**Steps:**

1. Create `apps/cli/src/cli/finder.py` with:
   - Imports: `from __future__ import annotations`, `os`, `subprocess`, `sys`, `Path`
   - Module-level constant `_NOT_FOUND_MSG` (multi-line string, 3 lines): extracted from the current `msg = (...)` block in `_find_binary` (lines 29–33 of `__init__.py`).
   - `def find_binary() -> Path`:
     - Rename from `_find_binary` → `find_binary` (public)
     - Fix `except ImportError, FileNotFoundError:` → `except (ImportError, FileNotFoundError):`
     - Add `# type: ignore[import-untyped]` comment on the `from aria2_bin import get_binary_path` line
     - Keep all other logic identical (try bundled → PATH fallback → `sys.exit(_NOT_FOUND_MSG)`)
     - 18 AST-measured lines (≤20)

2. Verify:
   - `python -c "from cli.finder import find_binary; print(type(find_binary))"` → `<class 'function'>`
   - On a system with `aria2c` in PATH: `python -c "from cli.finder import find_binary; print(find_binary())"` prints a valid path.
   - Syntax fix: `python -c "import ast; ast.parse(open('apps/cli/src/cli/finder.py').read())"` → no SyntaxError.

**Lines:** ~25 (all new).
**Risk:** Medium-Low — the `except` syntax fix is the only behavioral delta (from `SyntaxError` to correct catching).
**Verification:** Manual import + SyntaxError check.

---

### T3 — Create `commands/__init__.py` (re-export shell)

**File:** `apps/cli/src/cli/commands/__init__.py` (new, ~8 lines)

**Dependencies:** None (empty re-export module; actual imports added after T4/T5).

**Steps:**

1. Create the `apps/cli/src/cli/commands/` directory.
2. Create `apps/cli/src/cli/commands/__init__.py` with initial content (no imports yet):

```python
"""CLI command implementations."""

from __future__ import annotations
```

3. Verify: `python -c "import cli.commands; print(dir(cli.commands))"` — module loads without error.

**Note:** Re-exports (`from .start import cmd_start` etc.) will be added in T6 after the command modules exist, or can be added here (importing from files that don't exist yet will fail). Best practice: create this shell now, populate re-exports as the final step of T4/T5, or defer to T6.

**Lines:** ~8 (all new).
**Risk:** None — empty package shell.

---

### T4 — Create `commands/start.py` with `cmd_start` and helpers

**File:** `apps/cli/src/cli/commands/start.py` (new, ~55 lines)

**Dependencies:** T1 (`config.py`), T2 (`finder.py`).

**Steps:**

1. Create `apps/cli/src/cli/commands/start.py` with:
   - Imports: `from __future__ import annotations`, `argparse`, `signal`, `subprocess`, `sys`
   - `from ..finder import find_binary`
   - `from ..config import DEFAULT_PORT` (imported for explicitness, though cmd_start receives args.port from argparse)

2. Extract `_build_start_cmd(binary: str, args: argparse.Namespace) -> list[str]` (18 lines):
   - Exact logic from current `__init__.py` lines 37–53 (`cmd = [...]` through `cmd.extend(["--conf-path", str(args.conf)])`)
   - Return the command list; no I/O.

3. Extract `_run_foreground(cmd: list[str], args: argparse.Namespace) -> None` (15 lines):
   - Exact logic from current `__init__.py` lines 57–72 (foreground branch: print messages, `Popen`, signal handlers, `proc.wait()`).

4. Define `cmd_start(args: argparse.Namespace) -> None` (8 lines):
   - Call `find_binary()`, then `_build_start_cmd(str(binary), args)`
   - Branch on `args.daemon`: daemon mode inline (append `--daemon=true`, print, `subprocess.run`) — exactly the current lines 56–60
   - Else: call `_run_foreground(cmd, args)`

5. Verify:
   - `python -c "from cli.commands.start import cmd_start; print(type(cmd_start))"` → `<class 'function'>`
   - AST line count: `python -c "import ast; tree=ast.parse(open('apps/cli/src/cli/commands/start.py').read()); [print(n.name, n.end_lineno-n.lineno+1) for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]"` → all ≤20.

**Lines:** ~55 (all new).
**Risk:** Low — verbatim extraction, no logic changes.

---

### T5 — Create `commands/status.py` with `cmd_status` and helpers

**File:** `apps/cli/src/cli/commands/status.py` (new, ~42 lines)

**Dependencies:** T1 (`config.py`).

**Steps:**

1. Create `apps/cli/src/cli/commands/status.py` with:
   - Imports: `from __future__ import annotations`, `argparse`, `sys`
   - `from ..config import DEFAULT_HOST, DEFAULT_PORT, _fmt_speed`

2. Extract `_print_version_info(version: object) -> None` (3 lines):
   - Exact logic from `__init__.py` lines 124–125: `print(f"aria2 {version.version}")` + `print(f"  Features: {', '.join(version.enabled_features)}")`.

3. Extract `_try_print_global_stats(client: object) -> None` (13 lines, async):
   - Exact logic from `__init__.py` lines 128–136 (try/except block around `get_global_stat()` and speed printing). Uses `_fmt_speed` imported from config.

4. Define `async def cmd_status(args: argparse.Namespace) -> None` (13 lines):
   - Exact logic from `__init__.py` lines 109–138: SDK import guard → `Aria2Client` context manager → call `_print_version_info` and `_try_print_global_stats` → catch `ConnectionRefusedError` → catch `Exception`.

5. Verify:
   - `python -c "from cli.commands.status import cmd_status; print(type(cmd_status))"` → `<class 'function'>`
   - AST line count: all functions ≤20.

**Lines:** ~42 (all new).
**Risk:** Low — verbatim extraction, no logic changes.

---

### T6 — Rewrite `__init__.py` (entry point, `cmd_check`, argparse builders)

**File:** `apps/cli/src/cli/__init__.py` (rewrite, ~60 lines)

**Dependencies:** T1, T2, T3, T4, T5 (imports from all new modules).

**Steps:**

1. Keep the same top-of-file docstring: `"""CLI entry point for the aria2 SDK — manages bundled aria2c binary."""`

2. Imports — rewrite to:
   ```python
   from __future__ import annotations

   import argparse
   import asyncio
   import subprocess
   import sys
   from pathlib import Path

   from .config import DEFAULT_HOST, DEFAULT_PORT
   from .finder import find_binary
   from .commands import cmd_start, cmd_status
   ```

3. Remove `import os`, `import signal` (no longer needed — moved to `finder.py` and `commands/start.py`).

4. Remove the bodies of `_find_binary`, `cmd_start`, `cmd_status`, `_fmt_speed`, and the `main()` parser-build from the file (these are now in T1–T5 modules).

5. Keep `cmd_check(args: argparse.Namespace) -> None` (17 lines, unchanged):
   - Update the call from `_find_binary()` to `find_binary()` (the renamed public function).
   - All other logic identical.

6. Add three private parser-helper functions (extracted from current `main()`):

   - `_add_start_parser(sub)` (10 lines): Extract lines 155–165 (start_p = … through set_defaults(func=cmd_start)). Replace `default=6800` with `default=DEFAULT_PORT`.
   - `_add_check_parser(sub)` (5 lines): Extract lines 168–170.
   - `_add_status_parser(sub)` (7 lines): Extract lines 174–179. Replace `default="localhost"` with `default=DEFAULT_HOST` and `default=6800` with `default=DEFAULT_PORT`.

7. Rewrite `main()` (10 lines):
   ```python
   def main() -> None:
       """Entry point for the aria2 CLI."""
       parser = argparse.ArgumentParser(
           prog="aria2",
           description="aria2 download manager — CLI wrapper\n  https://github.com/Row0902/aria2",
       )
       parser.set_defaults(func=lambda _: parser.print_help())

       sub = parser.add_subparsers(title="commands")
       _add_start_parser(sub)
       _add_check_parser(sub)
       _add_status_parser(sub)

       args = parser.parse_args()
       args.func(args)
   ```

8. Keep the `if __name__ == "__main__": main()` guard at the bottom (lines 182–183, unchanged).

9. Update `apps/cli/src/cli/commands/__init__.py` if re-exports weren't added earlier:
   ```python
   """CLI command implementations."""

   from __future__ import annotations

   from .start import cmd_start
   from .status import cmd_status

   __all__ = ["cmd_start", "cmd_status"]
   ```

10. Verify:
    - `python -c "from cli import main; print(type(main))"` → `<class 'function'>`
    - `python -c "from cli.commands import cmd_start, cmd_status; print(cmd_start, cmd_status)"` → both resolve.
    - `python -c "from cli.finder import find_binary"` → resolves to public function.
    - `python -c "from cli.config import DEFAULT_PORT, DEFAULT_HOST, _fmt_speed"` → all resolve.

**Lines:** ~60 (rewrite; -113 from original, +~40 new parser helpers and imports).
**Risk:** Medium — the central integration point. All imports must resolve; all function signatures must match.
**Rollback:** `git checkout apps/cli/src/cli/__init__.py` restores the original.

---

### T7 — Smoke test all CLI entry points

**Dependencies:** T6 (everything wired together).

**Steps:**

1. **Entry point integrity:**
   ```bash
   python -m cli --help          # Prints top-level help
   python -m cli start --help    # Shows start options
   python -m cli check --help    # Shows check options (alias: version)
   python -m cli status --help   # Shows status options
   ```

2. **Binary discovery (check command):**
   ```bash
   python -m cli check           # Finds aria2c or prints error message
   python -m cli version         # Alias for check
   ```

3. **Start command arg parsing (no daemon needed):**
   ```bash
   python -m cli start --help    # Verify all args shown: port, secret, listen-all, dir, conf, daemon
   ```

4. **Status command arg parsing (no daemon needed):**
   ```bash
   python -m cli status --help   # Verify args: host, port, secret
   ```

5. **Programmatic import:**
   ```bash
   python -c "from cli import main; main()"  # Should print help (argparse error is OK)
   python -c "from cli import cmd_check; print(type(cmd_check))"  # <class 'function'>
   ```

6. **Error message parity (binary not found):**
   ```bash
   # On a system without aria2c, verify the error message is identical to pre-refactoring
   ARIA2C_PATH=/nonexistent python -m cli check 2>&1
   ```

**Lines:** 0 — manual smoke test.
**Risk:** Low if T6 passes verification. Medium if any integration issues surface.
**Verification:** All commands exit cleanly or with expected error messages.

---

### T8 — Run lint, typecheck, and wc-lint

**Dependencies:** T7 (CLI is functional).

**Steps:**

1. **ruff:**
   ```bash
   uv run ruff check apps/cli/src/cli/
   ```
   Expected: zero violations. If `commands/__init__.py` triggers `F401` (unused import) on the re-exports, add `"commands/__init__.py" = ["F401"]` to `[tool.ruff.lint.per-file-ignores]` in the workspace `pyproject.toml`.

2. **ruff format:**
   ```bash
   uv run ruff format --check apps/cli/src/cli/
   ```
   Expected: files already formatted (or apply formatting).

3. **ty (type checker):**
   ```bash
   uv run ty apps/cli/src/cli/
   ```
   Expected: zero errors. The `# type: ignore[import-untyped]` in `finder.py` suppresses the `aria2_bin` false-positive. The `# type: ignore[import-untyped]` on `from aria2 import Aria2Client` in `commands/status.py` suppresses the SDK false-positive.

4. **wc-lint:**
   ```bash
   python scripts/lint/wc-lint.py apps/cli/
   ```
   Expected: zero violations on all new files. Specifically verify:
   - `__init__.py` ≤ 80 lines (target ~60)
   - `finder.py` ≤ 40 lines (target ~25)
   - `config.py` ≤ 30 lines (target ~22)
   - `commands/__init__.py` ≤ 10 lines (target ~8)
   - `commands/start.py` ≤ 60 lines (target ~55)
   - `commands/status.py` ≤ 50 lines (target ~42)
   - All functions ≤ 20 lines (AST measurement)

5. **Build verification:**
   ```bash
   uv build
   unzip -l dist/*.whl | grep "cli/"
   ```
   Expected: wheel contains all 7 source files including `cli/commands/__init__.py`, `cli/commands/start.py`, `cli/commands/status.py`.

6. Fix any violations before marking complete.

**Lines:** 0–10 (possible ruff config adjustment).
**Risk:** Low-Medium. `ty` may surface unexpected issues; `wc-lint` should pass if line targets were met.

---

## Success Criteria (Checklist)

- [ ] `apps/cli/src/cli/config.py` exists — `DEFAULT_PORT`, `DEFAULT_HOST`, `_fmt_speed` importable
- [ ] `apps/cli/src/cli/finder.py` exists — `find_binary()` public, `except` syntax fixed, `_NOT_FOUND_MSG` constant
- [ ] `apps/cli/src/cli/commands/__init__.py` exists — re-exports `cmd_start`, `cmd_status`
- [ ] `apps/cli/src/cli/commands/start.py` exists — `cmd_start` ≤ 8 lines, `_build_start_cmd` ≤ 18, `_run_foreground` ≤ 15
- [ ] `apps/cli/src/cli/commands/status.py` exists — `cmd_status` ≤ 13 lines, `_print_version_info` ≤ 3, `_try_print_global_stats` ≤ 13
- [ ] `apps/cli/src/cli/__init__.py` ≤ 80 lines — `main()` ≤ 10, `cmd_check()` ≤ 17, three parser helpers ≤ 10 each
- [ ] `__main__.py` unchanged (3 lines)
- [ ] `from cli import main` resolves
- [ ] `from cli.finder import find_binary` resolves to public function
- [ ] `from cli.commands import cmd_start, cmd_status` resolves
- [ ] `python -m cli --help` prints top-level help
- [ ] `python -m cli check` finds binary or prints error
- [ ] `python -m cli start --help` shows start options
- [ ] `python -m cli status --help` shows status options
- [ ] `ruff check apps/cli/src/cli/` — zero violations
- [ ] `ty apps/cli/src/cli/` — zero errors
- [ ] `python scripts/lint/wc-lint.py apps/cli/` — zero violations
- [ ] `uv build` succeeds; wheel contains all 7 files

---

## Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| No existing CLI tests + `strict_tdd: true` in config | Medium | Refactoring preserves behavior verbatim; smoke tests catch regressions. Accept as technical debt noted in the design doc (§10); issue scope explicitly defers new tests. |
| `ty` may flag new import paths | Low | `# type: ignore[import-untyped]` annotations already planned. `root` config covers `apps/cli/src`. |
| `ruff` F401 on `commands/__init__.py` re-exports | Low | Add `per-file-ignores` entry if needed (design §7.2). |
| Relative import depth confusion (`from ..config` vs `from .config`) | Low | `commands/start.py` and `commands/status.py` are one level deep in `commands/`, so `..` is correct (parent = `cli`). `__init__.py` uses `.config` (same package level). |
