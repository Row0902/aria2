# Delta for CLI

## MODIFIED Requirements

### Requirement: Package Structure

The CLI SHALL be implemented as a modular package using `typer` (building on Click) as the
CLI framework, replacing `argparse`. Each file SHALL respect the project quality thresholds
in `openspec/config.yaml` (max 200 lines per file, max 20 lines per function body).

| File | Purpose | Framework |
|---|---|---|
| `apps/cli/src/cli/__init__.py` | Root typer app — `app = typer.Typer()`, `@app.callback()` with `main()`, `@app.command()` for `check`, `app.add_typer()` for start/status | typer |
| `apps/cli/src/cli/__main__.py` | `python -m cli` trampoline (unchanged) | — |
| `apps/cli/src/cli/finder.py` | `find_binary()` — locate aria2c binary (unchanged) | — |
| `apps/cli/src/cli/config.py` | `DEFAULT_PORT`, `DEFAULT_HOST`, `_fmt_speed()` (unchanged) | — |
| `apps/cli/src/cli/commands/__init__.py` | Re-exports `start_app`, `status_app` (typer apps) | typer |
| `apps/cli/src/cli/commands/start.py` | `app = typer.Typer()`, `@app.command()` `start()`, helpers | typer |
| `apps/cli/src/cli/commands/status.py` | `app = typer.Typer()`, `@app.command()` `status()`, helpers | typer |
| `apps/cli/tests/test_cli.py` | Test suite using `typer.testing.CliRunner` | typer |

The dependency graph SHALL contain no circular imports:

```
__main__.py ──► __init__.py ──► finder.py
                         ├──► config.py
                         └──► commands/__init__.py
                                ├──► commands/start.py ──► finder.py, config.py
                                └──► commands/status.py ──► config.py, aria2-sdk
```

(Previously: argparse builders in `__init__.py`, argparse-based commands, no test file.)

#### Scenario: Package installable by hatchling

- GIVEN a build with `packages = ["src/cli"]` in `pyproject.toml`
- WHEN `uv build` is executed
- THEN the resulting wheel MUST contain all source files including `test_cli.py`
- AND `commands/` MUST be auto-discovered as a subpackage

#### Scenario: typer import consumed

- GIVEN `typer>=0.26.5` is declared in `apps/cli/pyproject.toml`
- WHEN the CLI is imported
- THEN the `typer` dependency MUST be actively used (not a dead dependency)
- AND no `argparse` imports SHALL remain in the CLI source files

---

### Requirement: Entry Point

The entry point `main()` SHALL remain accessible through the following paths, all of which MUST
resolve to the same callable:

- `from cli import main` (package root)
- `python -m cli` (via `__main__.py`)
- The `aria2` console script (if registered in `pyproject.toml` `[project.scripts]`)

The `main()` function SHALL invoke the root `typer.Typer()` app, which auto-dispatches to
subcommands. The `@app.callback()` on `main()` SHALL store a `ctx.ensure_object(dict)` for
context passing.

(Previously: `main()` built `argparse.ArgumentParser`, registered subparsers, called `parse_args()`, then dispatched via `args.func(args)`.)

#### Scenario: Programmatic import

- GIVEN the CLI package is installed
- WHEN user code executes `from cli import main`
- THEN `main` resolves to a callable function in `cli/__init__.py`
- AND `main()` with no arguments or `["--help"]` prints the top-level help text via typer

#### Scenario: Python -m invocation

- GIVEN the CLI package is installed
- WHEN the command `python -m cli --help` is executed in a shell
- THEN the CLI prints the top-level typer help text listing `start`, `status`, `check`
- AND exits with code 0

#### Scenario: Console script entry point

- GIVEN the CLI wheel is installed
- WHEN the `aria2` command is invoked with `--help`
- THEN the CLI prints the top-level typer help text
- AND exits with code 0

---

### Requirement: Start Command

The function `start()` in `commands/start.py` SHALL be a `@app.command()` on a `typer.Typer()`
named `app`. It SHALL spawn an aria2c daemon process with RPC enabled on the specified port.

It MUST support two modes:

- **Daemon mode** (`--daemon`): launches aria2c with `--daemon=true`, prints a confirmation via
  `typer.echo()`, and returns immediately.
- **Foreground mode** (default): launches aria2c as a subprocess, registers SIGINT/SIGTERM handlers,
  and waits for the child to exit.

It SHALL accept the following typed options via `typer.Option()` annotations:

| Parameter | Type | Option | Default | Validation |
|---|---|---|---|---|
| `port` | `int` | `--port` / `-p` | `DEFAULT_PORT` (6800) | `min=1024, max=65535` |
| `secret` | `str \| None` | `--secret` / `-s` | `None` | — |
| `listen_all` | `bool` | `--listen-all` | `False` | — |
| `dir` | `pathlib.Path \| None` | `--dir` / `-d` | `None` | `dir_okay=True, file_okay=False` |
| `conf` | `pathlib.Path \| None` | `--conf` / `-c` | `None` | `exists=True, dir_okay=False` |
| `daemon` | `bool` | `--daemon` | `False` | — |

The helper functions `_build_start_cmd()` and `_run_foreground()` SHALL accept individual typed
parameters instead of `args: argparse.Namespace`. All output SHALL use `typer.echo()` instead of
`print()`.

(Previously: `cmd_start(args: argparse.Namespace)` with helpers accepting `argparse.Namespace`, `print()` for output, no range/path validation, `conf` as raw string.)

#### Scenario: Foreground start

- GIVEN aria2c binary is available
- WHEN `start()` is invoked with `--daemon` falsy (default)
- THEN aria2c is spawned via `subprocess.Popen` with `--enable-rpc` and `--rpc-listen-port={port}`
- AND `SIGINT` and `SIGTERM` handlers are registered that call `proc.terminate()`
- AND the process blocks on `proc.wait()`
- AND startup messages are emitted via `typer.echo()`

#### Scenario: Daemon start

- GIVEN aria2c binary is available
- WHEN `start()` is invoked with `--daemon`
- THEN aria2c is launched via `subprocess.run` with `--daemon=true`
- AND a confirmation message is printed via `typer.echo()` including the port
- AND if `--secret` is set, the secret is printed
- AND the function returns without blocking

#### Scenario: Start with all optional arguments

- GIVEN aria2c binary is available
- WHEN `start()` is called with `--secret`, `--dir`, `--conf`, and `--listen-all` all set
- THEN the subprocess command includes `--rpc-secret`, `--dir`, `--conf-path`, and `--rpc-listen-all=true`
- AND `--conf` validates that the file exists before the command is built

#### Scenario: Port range validation

- GIVEN the start command is invoked
- WHEN `--port` is set to a value below 1024 or above 65535
- THEN typer SHALL reject the value with a validation error before the command runs
- AND the exit code SHALL be nonzero

#### Scenario: Config path validation

- GIVEN the start command is invoked with `--conf /nonexistent/path`
- WHEN typer resolves the path
- THEN typer SHALL reject the value because the file does not exist
- AND the exit code SHALL be nonzero

#### Scenario: Binary not found during start

- GIVEN aria2c binary is not available
- WHEN `start()` is called
- THEN `find_binary()` SHALL exit the process with an error message
- AND `start()` never reaches the subprocess launch

---

### Requirement: Check Command

The function `check()` in `__init__.py` SHALL be a `@app.command()` on the root `typer.Typer()` app.
It SHALL verify that the aria2c binary exists and can execute `--version`. All output SHALL use
`typer.echo()` instead of `print()`.

The `version` alias SHALL be removed — `aria2 version` no longer works. Users SHALL use
`aria2 --version` for CLI version or `aria2 check` for binary verification.

(Previously: `cmd_check(args: argparse.Namespace)` registered via `sub.add_parser("check", aliases=["version"])` with `print()` output.)

#### Scenario: Binary found and working

- GIVEN aria2c binary is available
- WHEN `check()` is called
- THEN `find_binary()` locates the binary
- AND `aria2c --version` is executed
- AND the first line of stdout is printed after a checkmark message via `typer.echo()`
- AND the function returns normally (exit code 0)

#### Scenario: Binary found but broken

- GIVEN aria2c binary exists at a path but fails to execute `--version`
- WHEN `check()` is called
- THEN an error message is printed via `typer.echo(..., err=True)`
- AND `typer.Exit(code=1)` is raised

#### Scenario: Binary not found

- GIVEN aria2c binary is not available
- WHEN `check()` is called
- THEN `find_binary()` SHALL call `sys.exit()` with a descriptive message
- AND the process exits with a nonzero code

---

### Requirement: Status Command

The function `status()` in `commands/status.py` SHALL be a synchronous `@app.command()` on a
`typer.Typer()` named `app`. It SHALL query a running aria2 daemon for version information and
global download statistics via the aria2 SDK.

The function body SHALL immediately call `asyncio.run(_status_impl(…))` to wrap the async
implementation. The async implementation `_status_impl()` SHALL be a private coroutine function
that performs the actual RPC calls.

It SHALL accept the following typed options:

| Parameter | Type | Option | Default | Validation |
|---|---|---|---|---|
| `host` | `str` | `--host` | `DEFAULT_HOST` ("localhost") | — |
| `port` | `int` | `--port` / `-p` | `DEFAULT_PORT` (6800) | `min=1024, max=65535` |
| `secret` | `str \| None` | `--secret` / `-s` | `None` | — |

All output SHALL use `typer.echo()` instead of `print()`. Error exits SHALL use
`typer.echo(..., err=True)` followed by `raise typer.Exit(code=1)` instead of `sys.exit("msg")`.

(Previously: `async def cmd_status(args: argparse.Namespace)` dispatched via `lambda a: asyncio.run(cmd_status(a))`, `print()` for output, `sys.exit("msg")` for errors.)

#### Scenario: Successful status query

- GIVEN an aria2c daemon is running on the specified host and port
- WHEN `status()` is called
- THEN `asyncio.run()` executes `_status_impl(host, port, secret)`
- AND an `Aria2Client` is created with the provided host/port/secret and 5-second timeout
- AND `client.system.get_version()` is called
- AND the aria2 version and enabled features are printed via `typer.echo()`
- AND `client.status.get_global_stat()` is called
- AND active, waiting, and stopped download counts are printed
- AND download/upload speeds are formatted via `_fmt_speed` and printed
- AND the client context manager cleans up the connection

#### Scenario: Daemon not running

- GIVEN no service is listening on the specified host and port
- WHEN `status()` is called
- THEN `ConnectionRefusedError` is caught
- AND a message is printed via `typer.echo(..., err=True)` indicating aria2 is not running on that host:port
- AND a hint to run `aria2 start` is shown
- AND `typer.Exit(code=1)` is raised

#### Scenario: SDK not installed

- GIVEN the `aria2` SDK package is not importable
- WHEN `status()` is called
- THEN an error message is printed via `typer.echo(..., err=True)`
- AND `typer.Exit(code=1)` is raised

#### Scenario: Global stats not supported

- GIVEN an aria2c daemon is running but `get_global_stat()` raises an exception
- WHEN `status()` is called
- THEN version info is still printed
- AND the stats section is silently skipped (no crash)

#### Scenario: Unexpected error during status

- GIVEN an unexpected exception is raised during the status query
- WHEN `status()` is called
- THEN the exception is caught and the error message is printed with an ✗ prefix via `typer.echo(..., err=True)`
- AND `typer.Exit(code=1)` is raised

#### Scenario: Nested event loop protection

- GIVEN the status command is invoked
- WHEN `asyncio.run(_status_impl(…))` is called from a synchronous context (typical CLI invocation)
- THEN no `RuntimeError` about running event loops SHALL occur
- AND the async implementation executes to completion

---

### Requirement: Typer Behavioral Contract

This requirement replaces "Zero Behavioral Change" from the argparse-based CLI.

The typer-based CLI SHALL intentionally differ from the argparse-based CLI in the following ways.
All deviations are documented and accepted:

| Aspect | argparse | typer | Accepted |
|---|---|---|---|
| Output | `print()` | `typer.echo()` | Yes — testable, encoding-safe |
| Error exit | `sys.exit("msg")` | `typer.echo("msg", err=True)` + `raise typer.Exit(code=1)` | Yes — same user effect, testable |
| Help format | Manual `help=` strings | Auto-generated from docstrings + type hints + `show_default` | Yes — richer, more consistent |
| `--version` flag | Not present | Added via `@app.callback()` | Yes — new feature |
| Shell completion | Not available | Built-in via `--install-completion` | Yes — new feature |
| Error display | Raw traceback | Rich-formatted (short, contextual) | Yes — cleaner UX |
| Type validation | Basic `type=int` | Auto from type hints + `min`/`max`/`exists`/`dir_okay`/`file_okay` | Yes — stricter validation |
| Subcommand dispatch | `args.func(args)` | Typer auto-dispatches | Yes — internally cleaner |
| Defaults in help | Not shown | `show_default=True` on `typer.Option()` | Yes — better discoverability |
| `check` alias `version` | Supported | Removed | Yes — `aria2 --version` replaces it |

#### Scenario: Help text shows defaults

- GIVEN the typer-based CLI
- WHEN `aria2 start --help` is invoked
- THEN default values for `--port` (6800) and other options SHALL be visible in the help output

#### Scenario: User-visible error behavior preserved

- GIVEN an error condition (e.g., daemon not running)
- WHEN the CLI encounters the error
- THEN the error message text SHALL be functionally equivalent to the argparse version
- AND the exit code SHALL be identical

#### Scenario: Check command output equivalent

- GIVEN the same aria2c binary
- WHEN `aria2 check` is executed with both old (argparse) and new (typer) CLI
- THEN the checkmark message and binary path are printed
- AND the exit codes are identical

#### Scenario: Start command output equivalent

- GIVEN the same aria2c binary
- WHEN `aria2 start --daemon --port 6801` is executed
- THEN the daemon confirmation message is printed
- AND the subprocess is launched with identical command-line arguments

---

### Requirement: Import Compatibility

The CLI package SHALL maintain import paths for public symbols suitable for the typer architecture.

The `commands/__init__.py` SHALL re-export the typer app instances:

```python
from .start import app as start_app
from .status import app as status_app

__all__ = ["start_app", "status_app"]
```

The `cli/__init__.py` SHALL expose the root `app` and `main`:

```python
from cli import app, main
```

`finder.py` and `config.py` imports SHALL remain unchanged.

Symbols from the argparse era (`cmd_start`, `cmd_status`) SHALL be removed from `__all__` and
the public API. They SHALL NOT be re-exported.

(Previously: `commands/__init__.py` re-exported `cmd_start` and `cmd_status` functions with `__all__ = ["cmd_start", "cmd_status"]`.)

#### Scenario: Typer apps re-exported from commands

- GIVEN the typer-based CLI package
- WHEN `from cli.commands import start_app, status_app` is executed
- THEN both names resolve to `typer.Typer()` instances from `commands/start.py` and `commands/status.py`
- AND `cli.commands.__all__` contains `["start_app", "status_app"]`

#### Scenario: Root app accessible

- GIVEN the typer-based CLI package
- WHEN `from cli import app` is executed
- THEN `app` resolves to the root `typer.Typer()` instance in `cli/__init__.py`

#### Scenario: find_binary accessible

- GIVEN the typer-based CLI package
- WHEN `from cli.finder import find_binary` is executed
- THEN `find_binary` resolves to the public function in `finder.py`

#### Scenario: Configuration accessible

- GIVEN the typer-based CLI package
- WHEN `from cli.config import DEFAULT_PORT, DEFAULT_HOST, _fmt_speed` is executed
- THEN all three symbols resolve to the definitions in `config.py`

#### Scenario: argparse-era symbols removed

- GIVEN the typer-based CLI package
- WHEN `from cli.commands import cmd_start` is attempted
- THEN the import SHALL fail with `ImportError`

---

## ADDED Requirements

### Requirement: Global Version Flag

The root `@app.callback()` SHALL accept a `--version` / `-V` flag that prints the CLI version and
exits. The flag SHALL be `is_eager=True` so it works before any subcommand is processed.

```python
__version__ = "0.1.0"

def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"aria2-cli v{__version__}")
        raise typer.Exit()

@app.callback()
def main(
    ctx: typer.Context,
    version: Annotated[bool, typer.Option(
        "--version", "-V",
        is_eager=True,
        callback=_version_callback,
        help="Show version and exit.",
    )] = False,
) -> None:
    ...
```

#### Scenario: --version flag works

- GIVEN the CLI is installed
- WHEN `aria2 --version` is executed
- THEN the output SHALL contain `aria2-cli v` followed by the version string
- AND the exit code SHALL be 0

#### Scenario: -V short flag works

- GIVEN the CLI is installed
- WHEN `aria2 -V` is executed
- THEN the behavior SHALL be identical to `aria2 --version`

#### Scenario: --version works before subcommands

- GIVEN the CLI is installed
- WHEN `aria2 --version start --port 6800` is executed
- THEN the version SHALL be printed and exit
- AND the `start` subcommand SHALL NOT execute

#### Scenario: --version appears in help

- GIVEN the CLI is installed
- WHEN `aria2 --help` is executed
- THEN `--version` / `-V` SHALL appear in the global options section of the help output

---

### Requirement: Shell Completion

The root `typer.Typer()` app SHALL be created with `add_completion=True`, providing built-in
shell completion commands.

#### Scenario: --install-completion available

- GIVEN the CLI is installed
- WHEN `aria2 --install-completion` is executed
- THEN the CLI SHALL output shell-specific completion installation instructions
- AND the exit code SHALL be 0

#### Scenario: --show-completion available

- GIVEN the CLI is installed
- WHEN `aria2 --show-completion` is executed
- THEN the CLI SHALL output the completion script for the detected shell
- AND the exit code SHALL be 0

#### Scenario: Completion commands appear in help

- GIVEN the CLI is installed
- WHEN `aria2 --help` is executed
- THEN `--install-completion` and `--show-completion` SHALL appear in the help output

---

### Requirement: Type Validation on Options

Typer SHALL automatically validate option values based on Python type annotations and
`typer.Option()` constraint parameters. Invalid values SHALL be rejected before the command
function executes.

#### Scenario: Port range validated on start

- GIVEN the start command
- WHEN `aria2 start --port 80` is executed
- THEN typer SHALL reject the value because it is below the minimum of 1024
- AND a formatted error message SHALL be displayed

#### Scenario: Port range validated on status

- GIVEN the status command
- WHEN `aria2 status --port 99999` is executed
- THEN typer SHALL reject the value because it exceeds the maximum of 65535
- AND a formatted error message SHALL be displayed

#### Scenario: Config file existence validated

- GIVEN the start command
- WHEN `aria2 start --conf /tmp/nonexistent.conf` is executed
- THEN typer SHALL reject the value because the file does not exist
- AND an error message SHALL indicate the path validation failure

#### Scenario: Dir type validated

- GIVEN the start command
- WHEN `aria2 start --dir /etc/hosts` is executed (a file, not a directory)
- THEN typer SHALL reject the value because `file_okay=False` on the `--dir` option
- AND an error message SHALL indicate the type mismatch

---

### Requirement: Output Standardization

All CLI output SHALL use `typer.echo()` instead of `print()`. Error output SHALL use
`typer.echo(..., err=True)`. Fatal errors SHALL use `raise typer.Exit(code=N)` instead of
`sys.exit(N)` or `sys.exit("msg")`.

#### Scenario: stdout output testable

- GIVEN a `CliRunner` test invokes a command
- WHEN the command writes output via `typer.echo()`
- THEN the output SHALL be captured in `result.stdout`

#### Scenario: stderr output testable

- GIVEN a `CliRunner` test invokes a command that encounters an error
- WHEN the command writes error output via `typer.echo(..., err=True)`
- THEN the error output SHALL be captured in `result.stderr`

#### Scenario: Exit code testable

- GIVEN a `CliRunner` test invokes a command that fails
- WHEN the command raises `typer.Exit(code=1)`
- THEN `result.exit_code` SHALL be 1

---

### Requirement: Help Text Generation

Help text SHALL be auto-generated by typer from command docstrings, option `help=` strings,
and type annotations. Default values SHALL be displayed via `show_default=True`.

The root app SHALL be created with `no_args_is_help=True` so invoking `aria2` with no arguments
displays help instead of silently exiting.

#### Scenario: Root help shows subcommands

- GIVEN the typer-based CLI
- WHEN `aria2 --help` is invoked
- THEN the help output SHALL list `start`, `status`, and `check` as available commands
- AND each command SHALL show its docstring-derived description

#### Scenario: Subcommand help shows options

- GIVEN the typer-based CLI
- WHEN `aria2 start --help` is invoked
- THEN the help output SHALL show all six options with their help text and defaults
- AND `--port` SHALL show `[default: 6800]`

#### Scenario: No args shows help

- GIVEN the typer-based CLI
- WHEN `aria2` is invoked with no arguments
- THEN the CLI SHALL display help text (equivalent to `aria2 --help`)
- AND the exit code SHALL be 0

---

### Requirement: CliRunner Test Suite

A test suite SHALL exist at `apps/cli/tests/test_cli.py` using `typer.testing.CliRunner` to
validate CLI behavior. The test suite SHALL achieve at least 80% line coverage on
`apps/cli/src/cli/` source files.

#### Scenario: Help output tested

- GIVEN the test suite
- WHEN `pytest apps/cli/tests/test_cli.py -v` is run
- THEN tests SHALL verify `--help` output for root app and each subcommand
- AND tests SHALL verify `--version` flag output

#### Scenario: Error paths tested

- GIVEN the test suite
- WHEN tests execute with mocking
- THEN tests SHALL verify binary-not-found (check exits 1)
- AND tests SHALL verify daemon-not-running (status exits 1)
- AND tests SHALL verify SDK-not-installed (status exits 1)
- AND tests SHALL verify config-path-not-found (start validation error)

#### Scenario: Success paths tested

- GIVEN the test suite
- WHEN tests execute with mocking
- THEN tests SHALL verify binary-found (check exits 0)
- AND tests SHALL verify daemon-running (status prints version and stats)
- AND tests SHALL verify daemon mode (start runs subprocess)
- AND tests SHALL verify foreground mode (start spawns Popen)

#### Scenario: Coverage threshold met

- GIVEN the test suite
- WHEN `pytest --cov=apps/cli/src/cli --cov-report=term` is run
- THEN line coverage SHALL be at least 80%

---

## REMOVED Requirements

### Requirement: Check Command Version Alias

**Reason**: The argparse `check` subcommand accepted `aliases=["version"]`, making `aria2 version`
equivalent to `aria2 check`. Typer does not natively support subcommand aliases (a Click
limitation). The `--version` global flag (`aria2 --version`) provides a better, more standard
mechanism for version queries. The `version` alias was undocumented in argparse-era help output
and is presumed unused. This removal is documented as a BREAKING CHANGE in the CHANGELOG.
