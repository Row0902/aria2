# SDD Tasks: CLI Migration — argparse → typer

**Change ID:** `2026-06-03-cli-typer-migration`
**Date:** 2026-06-03
**Status:** Ready

---

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~400-450 (additions + deletions across 5 files) |
| 400-line budget risk | Medium |
| Chained PRs recommended | No |
| Suggested split | Single PR |
| Delivery strategy | single-pr |
| Chain strategy | not-applicable |

Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: not-applicable
400-line budget risk: Medium

### Rationale

- All 5 files are tightly coupled — splitting into multiple PRs breaks the import graph (e.g., root app can't import Typer sub-apps until they exist).
- Total review burden (~400-450 lines) sits at the boundary of the 400-line budget but is acceptable because:
  - 3 of 5 files (start.py, status.py, commands/__init__.py) are self-contained leaf rewrites with zero side effects.
  - The design doc provides exact source code for all files, so the reviewer compares against a known blueprint.
  - The test file is additive (new, no existing code modified).
- The chained PR overhead (3+ PRs for ~80-line files) is more review friction than a single cohesive review.

---

## Task Preconditions

Before any implementation task, verify:

```bash
# Check typer is installed and importable
uv run python -c "import typer; print(typer.__version__)"

# Run existing test suite to establish baseline
uv run pytest apps/cli/tests/ -v 2>&1 || true   # tests dir may be empty

# Lint baseline
uv run ruff check apps/cli/src/cli/
```

---

## Phase 1 — commands/status.py (leaf, zero intra-cli deps)

### Task 1.1: Write `app` and `@app.command() status()`

**File:** `apps/cli/src/cli/commands/status.py`
**Type:** Rewrite (replace entire file)
**Lines:** ~65 total (all functions ≤20 body lines)
**Dependencies:** None (only imports typer, asyncio, and ..config)

**What to do:**

Replace the entire contents of `commands/status.py` with the typer-based implementation from [design.md §2.4](design.md#24-clicommandsstatuspy--status-subcommand). Key changes from current argparse version:

1. Create `app = typer.Typer(name="status", no_args_is_help=True, rich_markup_mode="rich")`
2. Write synchronous `@app.command() def status(host, port, secret)` with `Annotated[T, typer.Option(...)]` parameters
3. Body is 2 lines: `asyncio.run(_status_impl(host, port, secret))`
4. Rename `async def cmd_status(args)` → `async def _status_impl(host, port, secret)` — accepts individual params, not `Namespace`
5. Keep `_print_version_info()` and `_try_print_global_stats()` — change `print()` → `typer.echo()`
6. Replace `sys.exit("msg")` → `typer.echo("msg", err=True)` + `raise typer.Exit(code=1)`
7. Remove `import argparse`, `import sys` — add `import asyncio`, `from typing import Annotated`, `import typer`

**Verification:**

```bash
# Type check passes
uv run ty --strict apps/cli/src/cli/commands/status.py

# Lint passes
uv run ruff check apps/cli/src/cli/commands/status.py

# Import works (app is a Typer instance)
uv run python -c "from cli.commands.status import app; print(type(app).__name__)"
# Expected: Typer
```

**Rollback:** `git checkout HEAD -- apps/cli/src/cli/commands/status.py`

---

### Task 1.2: Verify status.py file quality thresholds

**Prerequisite:** Task 1.1 complete

**What to do:**

1. Verify file is ≤200 lines: `wc -l apps/cli/src/cli/commands/status.py`
2. Verify no function body exceeds 20 lines (check `status()`, `_status_impl()`, `_print_version_info()`, `_try_print_global_stats()`)
3. Confirm zero `print()` calls (all `typer.echo()`)
4. Confirm zero `sys.exit()` calls (all `raise typer.Exit()`)
5. Confirm zero `argparse` imports
6. Confirm `Annotated` is used for all typed options

**Verification:**

```bash
# Line count
wc -l apps/cli/src/cli/commands/status.py
# Expected: ≤65

# No print() left
grep -n 'print(' apps/cli/src/cli/commands/status.py || echo "PASS: no print()"

# No sys.exit left
grep -n 'sys.exit' apps/cli/src/cli/commands/status.py || echo "PASS: no sys.exit"

# No argparse left
grep -n 'argparse' apps/cli/src/cli/commands/status.py || echo "PASS: no argparse"
```

---

## Phase 2 — commands/start.py (leaf, zero intra-cli deps)

### Task 2.1: Write `app` and `@app.command() start()`

**File:** `apps/cli/src/cli/commands/start.py`
**Type:** Rewrite (replace entire file)
**Lines:** ~80 total (all functions ≤20 body lines)
**Dependencies:** None (only imports typer, pathlib, signal, subprocess, sys, ..finder, ..config)

**What to do:**

Replace the entire contents of `commands/start.py` with the typer-based implementation from [design.md §2.3](design.md#23-clicommandsstartpy--start-subcommand). Key changes from current argparse version:

1. Create `app = typer.Typer(name="start", no_args_is_help=True, rich_markup_mode="rich")`
2. Write `@app.command() def start()` with `Annotated[T, typer.Option(...)]` parameters including validation:
   - `port: int` with `min=1024, max=65535` and `show_default=True`
   - `secret: str | None`
   - `listen_all: bool`
   - `dir: pathlib.Path | None` with `dir_okay=True, file_okay=False`
   - `conf: pathlib.Path | None` with `exists=True, dir_okay=False`
   - `daemon: bool`
3. Body calls `_build_start_cmd()` and then either `subprocess.run` (daemon) or `_run_foreground()` (foreground)
4. Refactor `_build_start_cmd(binary, args)` → `_build_start_cmd(binary, port, secret, listen_all, dir, conf)` — accepts individual params
5. Refactor `_run_foreground(cmd, args)` → `_run_foreground(cmd, port)` — accepts only needed value
6. Replace all `print()` → `typer.echo()`
7. Remove `import argparse` — add `from typing import Annotated`, `import typer`, `import pathlib`
8. Add `from ..config import DEFAULT_PORT` import

**Verification:**

```bash
# Type check passes
uv run ty --strict apps/cli/src/cli/commands/start.py

# Lint passes
uv run ruff check apps/cli/src/cli/commands/start.py

# Import works (app is a Typer instance)
uv run python -c "from cli.commands.start import app; print(type(app).__name__)"
# Expected: Typer
```

**Rollback:** `git checkout HEAD -- apps/cli/src/cli/commands/start.py`

---

### Task 2.2: Verify start.py file quality thresholds

**Prerequisite:** Task 2.1 complete

**What to do:**

Same checks as Task 1.2 but for start.py.

**Verification:**

```bash
# Line count
wc -l apps/cli/src/cli/commands/start.py
# Expected: ≤80

# No print() left (only typer.echo)
grep -n 'print(' apps/cli/src/cli/commands/start.py || echo "PASS: no print()"

# No argparse left
grep -n 'argparse' apps/cli/src/cli/commands/start.py || echo "PASS: no argparse"

# Function body line count (spot check the longest: _build_start_cmd)
# All functions should be ≤20 body lines
```

---

## Phase 3 — commands/__init__.py (re-exports)

### Task 3.1: Update exports from functions to Typer apps

**File:** `apps/cli/src/cli/commands/__init__.py`
**Type:** Update
**Lines:** ~6
**Dependencies:** Tasks 1.1 and 2.1 complete (start.py and status.py apps exist)

**What to do:**

Replace the current exports with the typer app re-exports from [design.md §2.2](design.md#22-clicommands__init__py--export-change):

```python
"""CLI subcommand Typer apps."""

from __future__ import annotations

from .start import app as start_app
from .status import app as status_app

__all__ = [
    "start_app",
    "status_app",
]
```

Key changes:
- `from .start import cmd_start` → `from .start import app as start_app`
- `from .status import cmd_status` → `from .status import app as status_app`
- `__all__` changes from `["cmd_start", "cmd_status"]` to `["start_app", "status_app"]`

**Verification:**

```bash
# Lint passes
uv run ruff check apps/cli/src/cli/commands/__init__.py

# Imports resolve
uv run python -c "from cli.commands import start_app, status_app; print(start_app, status_app)"
```

**Rollback:** `git checkout HEAD -- apps/cli/src/cli/commands/__init__.py`

---

## Phase 4 — __init__.py (root Typer app)

### Task 4.1: Write root Typer app with callback, check command, and sub-typer wiring

**File:** `apps/cli/src/cli/__init__.py`
**Type:** Rewrite (replace entire file)
**Lines:** ~55
**Dependencies:** Task 3.1 complete (commands/__init__.py exports start_app, status_app)

**What to do:**

Replace the entire contents of `__init__.py` with the root typer app from [design.md §2.1](design.md#21-cli__init__py--root-typer-app). Key changes:

1. Remove all argparse imports and parser builder functions (`_add_start_parser`, `_add_check_parser`, `_add_status_parser`)
2. Add `import typer`, `from typing import Annotated`
3. Add `__version__ = "0.1.0"` and `_version_callback(value)` function
4. Create `app = typer.Typer(...)` with all config (name, no_args_is_help, add_completion, pretty_exceptions_*, rich_markup_mode, context_settings, epilog)
5. Write `@app.callback() def main(ctx, version)` with `is_eager=True` callback for `--version` / `-V`
6. Write `@app.command() def check()` — move `cmd_check()` logic but use `typer.echo()` instead of `print()`, `raise typer.Exit(code=1)` instead of `sys.exit(1)`, keep `try/except typer.Exit: raise` guard
7. Wire subcommands: `app.add_typer(start_app, name="start", help="...")` and `app.add_typer(status_app, name="status", help="...")`
8. Remove the `version` alias (was `aliases=["version"]` on check parser) — BREAKING, documented

**Verification:**

```bash
# Type check passes
uv run ty --strict apps/cli/src/cli/__init__.py

# Lint passes
uv run ruff check apps/cli/src/cli/__init__.py

# App is a Typer instance with commands registered
uv run python -c "
from cli import app
cmds = [c.name for c in app.registered_commands]
print(cmds)
assert 'check' in cmds
"

# Sub-typers are registered
uv run python -c "
from cli import app
groups = [g.name for g in app.registered_groups]
print(groups)
assert 'start' in groups
assert 'status' in groups
"

# --help works (no crash)
uv run python -c "from cli import app; app(['--help'])"
```

**Rollback:** `git checkout HEAD -- apps/cli/src/cli/__init__.py`

---

### Task 4.2: Verify no dead code or broken imports

**Prerequisite:** Task 4.1 complete

**What to do:**

1. Confirm `__main__.py` still works unmodified: it imports `from cli import main` which now resolves to the `@app.callback()` function
2. Confirm `pyproject.toml` `[project.scripts] aria2 = "cli.__main__:main"` still valid
3. Confirm no argparse imports remain in any CLI source file
4. Confirm no `cmd_start` / `cmd_status` references remain in `__init__.py`

**Verification:**

```bash
# __main__.py import still works
uv run python -c "from cli import main; print(type(main).__name__)"

# No argparse anywhere in cli/src
grep -rn 'import argparse' apps/cli/src/cli/ || echo "PASS: no argparse"

# No old export names in root __init__.py
grep -n 'cmd_start\|cmd_status' apps/cli/src/cli/__init__.py || echo "PASS: no old names"
```

---

## Phase 5 — tests/test_cli.py (CliRunner test suite)

**Strict TDD:** Each test group follows RED → GREEN → TRIANGULATE → REFACTOR.

### Task 5.1: Create test file skeleton and runner fixture

**File:** `apps/cli/tests/test_cli.py` (new file)
**Type:** New
**Dependencies:** Phase 4 complete (all source files exist)

**What to do:**

Create the test file with the CliRunner fixture and import:

```python
"""CLI tests using typer.testing.CliRunner."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from cli import app


@pytest.fixture
def runner() -> CliRunner:
    """Provide a CliRunner instance for CLI testing."""
    return CliRunner()
```

**Verification:**

```bash
# File imports without error
uv run python -c "from cli import app; from typer.testing import CliRunner; print('OK')"

# Test file is syntactically valid
uv run python -m py_compile apps/cli/tests/test_cli.py
```

---

### Task 5.2: RED — Write help and version tests (expected to fail until source is verified)

**Prerequisite:** Task 5.1 complete
**File:** `apps/cli/tests/test_cli.py` (append)

**What to do:**

Add the following test functions (these use CliRunner without mocking, so they test real CLI behavior):

```python
def test_root_help(runner: CliRunner) -> None:
    """Root --help shows subcommands: start, status, check."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "start" in result.stdout
    assert "status" in result.stdout
    assert "check" in result.stdout


def test_no_args_shows_help(runner: CliRunner) -> None:
    """No args shows help (no_args_is_help=True)."""
    result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert "start" in result.stdout


def test_version_flag(runner: CliRunner) -> None:
    """--version prints version and exits 0."""
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "aria2-cli v" in result.stdout


def test_version_short_flag(runner: CliRunner) -> None:
    """-V prints version and exits 0."""
    result = runner.invoke(app, ["-V"])
    assert result.exit_code == 0
    assert "aria2-cli v" in result.stdout


def test_version_before_subcommand(runner: CliRunner) -> None:
    """--version before subcommand prints version, subcommand not executed."""
    result = runner.invoke(app, ["--version", "start", "--port", "6800"])
    assert result.exit_code == 0
    assert "aria2-cli v" in result.stdout
    # start subcommand output should NOT appear
    assert "aria2c" not in result.stdout.lower()


def test_start_help(runner: CliRunner) -> None:
    """start --help shows options with defaults."""
    result = runner.invoke(app, ["start", "--help"])
    assert result.exit_code == 0
    assert "Start an aria2c daemon" in result.stdout
    assert "--port" in result.stdout
    assert "--secret" in result.stdout
    assert "--daemon" in result.stdout


def test_status_help(runner: CliRunner) -> None:
    """status --help shows options."""
    result = runner.invoke(app, ["status", "--help"])
    assert result.exit_code == 0
    assert "Query a running" in result.stdout
    assert "--host" in result.stdout
    assert "--port" in result.stdout
    assert "--secret" in result.stdout
```

**Verification (RED — expected to fail some if source has bugs):**

```bash
uv run pytest apps/cli/tests/test_cli.py -v -k "help or version"
```

---

### Task 5.3: GREEN — Fix any help/version test failures in source

**Prerequisite:** Task 5.2 complete

**What to do:**

If any help/version tests fail, fix the source files. Common issues:
- Typer help text not matching expected strings — adjust assertions to match actual output
- `no_args_is_help` not set — verify `app = typer.Typer(no_args_is_help=True)`
- `--version` not eager — verify `is_eager=True` on version option

**Verification:**

```bash
uv run pytest apps/cli/tests/test_cli.py -v -k "help or version"
# All 7 help/version tests pass
```

---

### Task 5.4: RED — Write test_check tests (with subprocess mocking)

**Prerequisite:** Task 5.3 complete
**File:** `apps/cli/tests/test_cli.py` (append)

**What to do:**

Add tests for the `check` command using `unittest.mock.patch` for `subprocess.run` and `find_binary`:

```python
from unittest.mock import MagicMock, patch


def test_check_binary_found(runner: CliRunner) -> None:
    """check finds aria2c and prints version line."""
    with (
        patch("cli.finder.find_binary", return_value="/usr/bin/aria2c") as mock_find,
        patch("subprocess.run") as mock_run,
    ):
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = "aria2 version 1.36.0\nOther line\n"
        mock_run.return_value = mock_proc

        result = runner.invoke(app, ["check"])

        assert result.exit_code == 0
        assert "aria2c found" in result.stdout
        mock_find.assert_called_once()
        mock_run.assert_called_once()


def test_check_binary_broken(runner: CliRunner) -> None:
    """check finds binary but --version fails."""
    with (
        patch("cli.finder.find_binary", return_value="/usr/bin/aria2c"),
        patch("subprocess.run") as mock_run,
    ):
        mock_proc = MagicMock()
        mock_proc.returncode = 1
        mock_run.return_value = mock_proc

        result = runner.invoke(app, ["check"])

        assert result.exit_code == 1
        assert "execution failed" in result.stderr
```

Note: The `check` command in `__init__.py` uses `import subprocess` inside the function. The mock must target the module where `subprocess` is used — verify the patch path.

**Verification (RED):**

```bash
uv run pytest apps/cli/tests/test_cli.py -v -k "check"
```

---

### Task 5.5: GREEN — Fix check test failures (patch path adjustment)

**Prerequisite:** Task 5.4 complete

**What to do:**

If `test_check_*` tests fail, the most likely issue is the `subprocess` patch path. Since `check()` does `import subprocess` inside the function body, the mock target may need to be `cli.__init__.subprocess` when patching. Adjust patch paths as needed.

Also verify the `try/except typer.Exit: raise` guard works correctly in the `check()` function — a broken binary should raise `typer.Exit(code=1)` not `sys.exit(1)`.

**Verification:**

```bash
uv run pytest apps/cli/tests/test_cli.py -v -k "check"
# Both check tests pass
```

---

### Task 5.6: RED — Write test_start tests (with subprocess/finder mocking)

**Prerequisite:** Task 5.5 complete
**File:** `apps/cli/tests/test_cli.py` (append)

**What to do:**

Add tests for the `start` command:

```python
def test_start_daemon_mode(runner: CliRunner) -> None:
    """start --daemon runs subprocess and prints confirmation."""
    with (
        patch("cli.commands.start.find_binary", return_value="/usr/bin/aria2c") as mock_find,
        patch("subprocess.run") as mock_run,
    ):
        result = runner.invoke(app, ["start", "--daemon", "--port", "6801", "--secret", "test"])

        assert result.exit_code == 0
        assert "daemon started" in result.stdout
        assert "6801" in result.stdout
        mock_find.assert_called_once()
        mock_run.assert_called_once()


def test_start_foreground_mode(runner: CliRunner) -> None:
    """start (no --daemon) spawns Popen and registers signal handlers."""
    with (
        patch("cli.commands.start.find_binary", return_value="/usr/bin/aria2c") as mock_find,
        patch("subprocess.Popen") as mock_popen,
        patch("signal.signal") as mock_signal,
    ):
        mock_proc = MagicMock()
        mock_popen.return_value = mock_proc

        result = runner.invoke(app, ["start", "--port", "6801"])

        assert result.exit_code == 0
        assert "Starting aria2c" in result.stdout
        mock_find.assert_called_once()
        mock_popen.assert_called_once()
        # signal handlers registered for SIGINT and SIGTERM
        assert mock_signal.call_count >= 2


def test_start_port_out_of_range(runner: CliRunner) -> None:
    """start with port < 1024 fails with validation error."""
    result = runner.invoke(app, ["start", "--port", "80"])
    assert result.exit_code != 0


def test_start_port_out_of_range_high(runner: CliRunner) -> None:
    """start with port > 65535 fails with validation error."""
    result = runner.invoke(app, ["start", "--port", "99999"])
    assert result.exit_code != 0


def test_start_conf_not_found(runner: CliRunner) -> None:
    """start --conf with nonexistent file fails with validation error."""
    result = runner.invoke(app, ["start", "--conf", "/nonexistent/path/aria2.conf"])
    assert result.exit_code != 0
```

**Verification (RED):**

```bash
uv run pytest apps/cli/tests/test_cli.py -v -k "start"
```

---

### Task 5.7: GREEN — Fix start test failures

**Prerequisite:** Task 5.6 complete

**What to do:**

Common issues to fix:
- Patch path for `find_binary`: verify it targets `cli.commands.start.find_binary` (not `cli.finder.find_binary`)
- `signal.signal` registration: verify both `SIGINT` and `SIGTERM` are registered
- Port validation: typer rejects before the function runs, so `result.stdout` may be empty for validation errors — check `result.stderr` or adjust assertions
- `conf` validation: same — typer rejects before function, check exit code only

**Verification:**

```bash
uv run pytest apps/cli/tests/test_cli.py -v -k "start"
# All start tests pass
```

---

### Task 5.8: RED — Write test_status tests (with Aria2Client mocking)

**Prerequisite:** Task 5.7 complete
**File:** `apps/cli/tests/test_cli.py` (append)

**What to do:**

Add tests for the `status` command. These need careful mocking of `Aria2Client`:

```python
class FakeVersion:
    version = "1.36.0"
    enabled_features = ["Async DNS", "BitTorrent", "Metalink"]


class FakeStat:
    num_active = 3
    num_waiting = 1
    num_stopped = 0
    download_speed = 1_500_000
    upload_speed = 500_000


def test_status_success(runner: CliRunner) -> None:
    """status query succeeds — prints version and stats."""
    fake_client = MagicMock()
    fake_client.__aenter__.return_value = fake_client
    fake_client.__aexit__.return_value = False
    fake_client.system.get_version = MagicMock(return_value=FakeVersion())
    fake_client.status.get_global_stat = MagicMock(return_value=FakeStat())

    with patch("cli.commands.status.Aria2Client", return_value=fake_client):
        result = runner.invoke(app, ["status", "--host", "localhost", "--port", "6800"])

        assert result.exit_code == 0
        assert "aria2 1.36.0" in result.stdout
        assert "Async DNS" in result.stdout
        assert "Downloading: 3" in result.stdout
        assert "Waiting: 1" in result.stdout


def test_status_connection_refused(runner: CliRunner) -> None:
    """status exits 1 when daemon not running."""
    fake_client = MagicMock()
    fake_client.__aenter__.side_effect = ConnectionRefusedError("Connection refused")

    with patch("cli.commands.status.Aria2Client", return_value=fake_client):
        result = runner.invoke(app, ["status"])

        assert result.exit_code == 1
        assert "not running" in result.stderr


def test_status_sdk_not_installed(runner: CliRunner) -> None:
    """status exits 1 when aria2 SDK import fails."""
    with patch("cli.commands.status.Aria2Client", side_effect=ImportError("No module named 'aria2'")):
        result = runner.invoke(app, ["status"])

        assert result.exit_code == 1
        assert "SDK not installed" in result.stderr


def test_status_stats_unavailable(runner: CliRunner) -> None:
    """status prints version even when stats fail."""
    fake_client = MagicMock()
    fake_client.__aenter__.return_value = fake_client
    fake_client.__aexit__.return_value = False
    fake_client.system.get_version = MagicMock(return_value=FakeVersion())
    fake_client.status.get_global_stat = MagicMock(side_effect=Exception("Unsupported"))

    with patch("cli.commands.status.Aria2Client", return_value=fake_client):
        result = runner.invoke(app, ["status"])

        assert result.exit_code == 0
        assert "aria2 1.36.0" in result.stdout
        # Stats section silently skipped — no crash


def test_status_unexpected_error(runner: CliRunner) -> None:
    """status exits 1 on unexpected exception."""
    fake_client = MagicMock()
    fake_client.__aenter__.side_effect = RuntimeError("Unexpected failure")

    with patch("cli.commands.status.Aria2Client", return_value=fake_client):
        result = runner.invoke(app, ["status"])

        assert result.exit_code == 1
        assert "Error:" in result.stderr


def test_status_port_out_of_range(runner: CliRunner) -> None:
    """status with invalid port fails validation."""
    result = runner.invoke(app, ["status", "--port", "99999"])
    assert result.exit_code != 0
```

**Verification (RED):**

```bash
uv run pytest apps/cli/tests/test_cli.py -v -k "status"
```

---

### Task 5.9: GREEN — Fix status test failures

**Prerequisite:** Task 5.8 complete

**What to do:**

Common issues:
- `Aria2Client` is imported inside `_status_impl()` with `from aria2 import Aria2Client`. The patch path must be `cli.commands.status.Aria2Client` (since the lazy import creates a local name in `_status_impl`). If this doesn't work, try patching `builtins.__import__` or `sys.modules['aria2']`.
- The `import` is in a try/except block — if the mock fails, the ImportError handler catches it and prints "SDK not installed".
- `_try_print_global_stats()` catches generic `Exception` — verify stats failure is silently skipped.
- `typer.echo(err=True)` output appears in `result.stderr`, not `result.stdout`.

**Verification:**

```bash
uv run pytest apps/cli/tests/test_cli.py -v -k "status"
# All status tests pass
```

---

### Task 5.10: Complete test suite — coverage verification

**Prerequisite:** Task 5.9 complete (all tests green)
**File:** `apps/cli/tests/test_cli.py` — verify coverage

**What to do:**

Run the full test suite with coverage and verify ≥80% on CLI source:

```bash
# Full suite
uv run pytest apps/cli/tests/test_cli.py -v

# Coverage report
uv run pytest --cov=apps/cli/src/cli --cov-report=term --cov-fail-under=80 apps/cli/tests/test_cli.py
```

If coverage is below 80%, identify uncovered lines and add targeted tests. Common gaps:
- `_run_foreground()` signal handler paths (the shutdown callback)
- `_build_start_cmd()` edge cases (all params None vs all set)
- `_version_callback(value=False)` path (the callback is called even when value is False — it just returns early)
- `check()` exception paths beyond `typer.Exit`

**Verification:**

```bash
uv run pytest --cov=apps/cli/src/cli --cov-report=term --cov-fail-under=80 apps/cli/tests/test_cli.py
# Expected: PASSED with coverage ≥80%
```

---

## Phase 6 — Integration Verification

### Task 6.1: Full quality gate

**Prerequisite:** Phase 5 complete (all tests green, coverage ≥80%)

**What to do:**

Run all quality checks across the entire CLI source and tests:

```bash
# 1. Lint all CLI source (zero errors)
uv run ruff check apps/cli/src/cli/

# 2. Lint test file (zero errors)
uv run ruff check apps/cli/tests/

# 3. Type check all CLI source (zero errors, strict)
uv run ty --strict apps/cli/src/cli/

# 4. Full test suite
uv run pytest apps/cli/tests/test_cli.py -v

# 5. Coverage with threshold
uv run pytest --cov=apps/cli/src/cli --cov-report=term --cov-fail-under=80 apps/cli/tests/test_cli.py
```

All five commands must pass with zero errors.

---

### Task 6.2: Manual smoke test (optional, requires aria2c)

**Prerequisite:** Task 6.1 complete

**What to do (if aria2c is available):**

```bash
# Help output
uv run aria2 --help

# Version
uv run aria2 --version

# Check binary
uv run aria2 check

# Start help
uv run aria2 start --help

# Status help
uv run aria2 status --help
```

---

## Dependency Graph

```
Phase 0 (preflight)
 │
 ├─► Phase 1: status.py       (leaf — no intra-cli deps)
 │        │
 │        └─► Task 1.1 → Task 1.2
 │
 ├─► Phase 2: start.py        (leaf — no intra-cli deps)
 │        │
 │        └─► Task 2.1 → Task 2.2
 │
 ├─► Phase 3: commands/__init__.py   (depends on Phase 1 + 2)
 │        │
 │        └─► Task 3.1
 │
 ├─► Phase 4: __init__.py     (depends on Phase 3)
 │        │
 │        ├─► Task 4.1 → Task 4.2
 │
 ├─► Phase 5: test_cli.py     (depends on Phase 4)
 │        │
 │        ├─► Task 5.1  (skeleton)
 │        ├─► Task 5.2  RED   help/version tests
 │        ├─► Task 5.3  GREEN fix source
 │        ├─► Task 5.4  RED   check tests
 │        ├─► Task 5.5  GREEN fix source
 │        ├─► Task 5.6  RED   start tests
 │        ├─► Task 5.7  GREEN fix source
 │        ├─► Task 5.8  RED   status tests
 │        ├─► Task 5.9  GREEN fix source
 │        └─► Task 5.10 coverage verification
 │
 └─► Phase 6: Integration
          ├─► Task 6.1 quality gate
          └─► Task 6.2 smoke test
```

---

## Summary

| Metric | Value |
|---|---|
| Total tasks | 16 |
| Files changed | 5 (4 rewrites, 1 new) |
| Estimated lines | ~400-450 changed |
| Test coverage target | ≥80% on `apps/cli/src/cli/` |
| Breaking changes | 1 (`version` alias removed) |
| Can be parallelized | Phases 1 and 2 |

## Rollback (full)

```bash
git checkout HEAD -- \
    apps/cli/src/cli/__init__.py \
    apps/cli/src/cli/commands/__init__.py \
    apps/cli/src/cli/commands/start.py \
    apps/cli/src/cli/commands/status.py
rm -f apps/cli/tests/test_cli.py
```
