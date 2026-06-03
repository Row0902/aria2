\---

name: typer
description: "Trigger: typer, CLI, command line, subcommands, argparse migration, Typer app. Modern CLI framework based on Python type hints — replaces argparse."
license: Apache-2.0
metadata:
author: gentleman-programming
version: "1.0"
---

## When to Use

* Building CLI applications with subcommands, options, and arguments
* Migrating from `argparse` to a type-hint-driven CLI framework
* Creating CLIs that need shell auto-completion (Bash, Zsh, Fish, PowerShell)
* CLIs that need Rich-formatted help, errors, and progress display
* Any CLI where you want type-safe parameter definitions

## Core Concepts

### Basic App with Subcommands

```python
import typer

app = typer.Typer(no\_args\_is\_help=True)

@app.command()
def start(
    port: int = typer.Option(6800, "--port", "-p", help="RPC port"),
    secret: str | None = typer.Option(None, "--secret", "-s", help="RPC secret"),
):
    """Start an aria2c daemon with RPC enabled."""
    print(f"Starting on port {port}")

@app.command()
def status(
    host: str = typer.Option("localhost", "--host", help="RPC host"),
    port: int = typer.Option(6800, "--port", "-p", help="RPC port"),
):
    """Query a running aria2 daemon."""
    print(f"Status on {host}:{port}")

if \_\_name\_\_ == "\_\_main\_\_":
    app()
```

### Typer App Parameters

```python
app = typer.Typer(
    name="aria2",                        # App name in help
    no\_args\_is\_help=True,                 # Show help when no args given
    add\_completion=True,                  # Add --install-completion / --show-completion
    pretty\_exceptions\_enable=True,        # Rich-formatted errors
    pretty\_exceptions\_show\_locals=False,  # Don't show locals in errors
    pretty\_exceptions\_short=True,         # Short traceback in errors
    rich\_markup\_mode="rich",              # Enable Rich markup in help text
    context\_settings={"help\_option\_names": \["--help", "-h"]},
    epilog="See https://aria2.github.io/ for more info.",
    suggest\_commands=True,                # Suggest typos for mistyped commands
)
```

### `@app.callback()` — Global Options

Use to add CLI options that apply to ALL subcommands (e.g., `--verbose`, `--version`):

```python
from typing import Annotated

app = typer.Typer()
state = {"verbose": False}

@app.callback()
def main(
    ctx: typer.Context,
    verbose: Annotated\[bool, typer.Option("--verbose", "-v", help="Enable verbose output")] = False,
):
    """aria2 — download manager CLI."""
    state\["verbose"] = verbose
    # Store in context for subcommands
    ctx.ensure\_object(dict)
    ctx.obj\["verbose"] = verbose
```

### `@app.command()` Parameters

```python
@app.command()
def my\_command(
    # Arguments (positional, required by default)
    name: str = typer.Argument(help="Name to greet"),
    path: pathlib.Path = typer.Argument(..., exists=True, dir\_okay=False, help="Config file"),
    count: int = typer.Argument(0, min=0, max=100, help="Count"),

    # Options (named, optional by default)
    secret: str | None = typer.Option(None, "--secret", "-s",
        envvar="ARIA2\_SECRET",           # Read from env var if not provided
        help="RPC secret token",
        show\_envvar=True,
    ),
    port: int = typer.Option(6800, "--port", "-p",
        min=1024, max=65535,
        help="RPC port",
        rich\_help\_panel="Connection",    # Group in Rich help panels
    ),
    host: str = typer.Option("localhost", "--host",
        metavar="ADDRESS",
        rich\_help\_panel="Connection",
    ),
    verbose: Annotated\[bool, typer.Option("--verbose", "-v")] = False,
    daemon: bool = typer.Option(False, "--daemon", help="Run in background"),
    listen\_all: Annotated\[bool, typer.Option("--listen-all")] = False,
    dir: Annotated\[pathlib.Path | None, typer.Option("--dir", "-d",
        dir\_okay=True, file\_okay=False,
        help="Download directory",
    )] = None,
)
```

## Feature Reference

### 1\. Parameters \& Type Annotations

|Type|Behavior|
|-|-|
|`str`|String value|
|`int`|Integer with optional `min`/`max`/`clamp`|
|`float`|Float with optional `min`/`max`/`clamp`|
|`bool`|Auto `--flag`/`--no-flag` toggle|
|`pathlib.Path`|File/dir path with exists, file\_okay, dir\_okay, resolve\_path|
|`list\[str]`|Multiple values (repeatable option: `--name a --name b`)|
|`Enum`|Choices from enum members, auto-completion|
|`datetime.datetime`|Parse with configurable `formats`|
|`typer.FileText` / `typer.FileBinary`|File read/write with auto-open|

### 2\. Typer.Option Parameters

```python
typer.Option(
    default,                            # Default value (None = optional)
    \*param\_decls,                       # Name/aliases: "--port", "-p"
    callback=None,                      # Validation/transformation callback
    metavar=None,                       # Placeholder in help: "PORT"
    expose\_value=True,                  # Show in help
    is\_eager=False,                     # Process before other params (for --version)
    envvar=None,                        # Env var fallback: "ARIA2\_PORT"
    shell\_complete=None,
    autocompletion=None,                # Custom value completion function
    default\_factory=None,               # Dynamic default generator
    parser=None,                        # Custom parser function
    click\_type=None,                    # Use a custom Click type
    show\_default=True,                  # Show default in help
    show\_choices=True,                  # Show enum choices in help
    show\_envvar=True,                   # Show env var name in help
    help=None,                          # Help text
    hidden=False,                       # Hide from help
    prompt=False,                       # Prompt user if not provided
    confirmation\_prompt=False,          # Confirm password-like inputs
    prompt\_required=True,
    hide\_input=False,                   # Hide input (passwords)
    is\_flag=None,                       # Force flag behavior (no value)
    flag\_value=None,
    count=False,                        # Counter: -vvv = 3
    allow\_from\_autoenv=True,
    case\_sensitive=True,                # For enum choices
    min=None, max=None, clamp=False,    # Numeric validation
    formats=None,                       # Datetime formats
    mode=None, encoding=None,           # File options
    errors="strict", lazy=None, atomic=False,  # File options
    exists=False, file\_okay=True,       # Path validation
    dir\_okay=True, writable=False,
    readable=True, resolve\_path=False,
    allow\_dash=False, path\_type=None,
    rich\_help\_panel=None,               # Panel grouping in Rich help
)
```

### 3\. Typer.Argument Parameters

Same as Option minus `prompt`, `confirmation\_prompt`, `hide\_input`, `is\_flag`, `flag\_value`, `count`, `allow\_from\_autoenv`. Arguments are positional (no `param\_decls`).

```python
typer.Argument(
    default=...,
    callback=None, metavar=None, expose\_value=True,
    is\_eager=False, envvar=None,
    shell\_complete=None, autocompletion=None,
    default\_factory=None, parser=None, click\_type=None,
    show\_default=True, show\_choices=True, show\_envvar=True,
    help=None, hidden=False,
    case\_sensitive=True,
    min=None, max=None, clamp=False,
    formats=None,
    mode=None, encoding=None, errors="strict",
    lazy=None, atomic=False,
    exists=False, file\_okay=True, dir\_okay=True,
    writable=False, readable=True, resolve\_path=False,
    allow\_dash=False, path\_type=None,
    rich\_help\_panel=None,
)
```

### 4\. Callbacks — Validation \& Transformation

```python
def port\_callback(ctx: typer.Context, param: typer.CallbackParam, value: int) -> int:
    """Validate port before the command runs."""
    if ctx.resilient\_parsing:       # <-- MUST check for completion to work
        return value
    if value < 1024 and value != 6800:
        raise typer.BadParameter(f"Port {value} requires root. Use --port 6800 or >1023")
    if value == 0:
        raise typer.BadParameter("Port cannot be 0")
    return value

@app.command()
def start(
    port: Annotated\[int, typer.Option(callback=port\_callback)] = 6800,
):
    ...
```

**Callback signatures (Typer auto-detects by type):**

* `callback(value: str)` — just the value
* `callback(ctx: typer.Context, value: str)` — with context
* `callback(ctx: typer.Context, param: typer.CallbackParam, value: str)` — with context + param info
* `callback(value: str) -> str` — return transformed value

Always check `ctx.resilient\_parsing` to avoid breaking tab completion.

### 5\. Async Commands

Typer does NOT natively support `async def` commands. Use a wrapper:

```python
import asyncio
import typer

app = typer.Typer()

@app.command()
def status(
    host: str = typer.Option("localhost", "--host"),
    port: int = typer.Option(6800, "--port", "-p"),
    secret: str | None = typer.Option(None, "--secret", "-s"),
):
    """Query a running aria2 daemon."""
    asyncio.run(\_async\_status(host, port, secret))

async def \_async\_status(host: str, port: int, secret: str | None) -> None:
    """Async implementation."""
    from aria2 import Aria2Client
    async with Aria2Client(host=host, port=port, secret=secret, timeout=5.0) as client:
        version = await client.system.get\_version()
        print(f"aria2 {version.version}")
```

For a reusable pattern with `AsyncTyper` (requires `asyncer`):

```python
import inspect
from functools import partial, wraps
import typer
from typer.core import TyperCommand
from typer.models import CommandFunctionType, Default

class AsyncTyper(typer.Typer):
    @staticmethod
    def \_maybe\_run\_async(decorator, f):
        if inspect.iscoroutinefunction(f):
            @wraps(f)
            def runner(\*args, \*\*kwargs):
                import asyncer
                return asyncer.runnify(f)(\*args, \*\*kwargs)
            decorator(runner)
        else:
            decorator(f)
        return f

    def callback(self, \*args, \*\*kwargs):
        decorator = super().callback(\*args, \*\*kwargs)
        return partial(self.\_maybe\_run\_async, decorator)

    def command(self, \*args, \*\*kwargs):
        decorator = super().command(\*args, \*\*kwargs)
        return partial(self.\_maybe\_run\_async, decorator)
```

### 6\. Shell Auto-Completion

Built-in via `--install-completion` (auto-detects shell via `shellingham`).

**Custom value completion:**

```python
def complete\_gid(incomplete: str):
    """Provide GID completions."""
    gids = \["2089b05ecca3d829", "cd2a5a8e5d3f1b7c", "45e7c2fa9b1d3a8f"]
    for gid in gids:
        if gid.startswith(incomplete):
            yield gid

@app.command()
def tell\_status(
    gid: Annotated\[str, typer.Argument(help="Download GID", autocompletion=complete\_gid)],
):
    ...
```

**Completion with help text:**

```python
def complete\_name(incomplete: str):
    names = \[
        ("Camila", "The reader of books"),
        ("Carlos", "The writer of code"),
        ("Sebastian", "The designer of UIs"),
    ]
    for name, help\_text in names:
        if name.startswith(incomplete):
            yield (name, help\_text)
```

**Completion with Context (filter already-used values):**

```python
def complete\_name(ctx: typer.Context, incomplete: str):
    used = ctx.params.get("name") or \[]
    for name, help\_text in names:
        if name.startswith(incomplete) and name not in used:
            yield (name, help\_text)
```

### 7\. Nested Subcommands with `app.add\_typer()`

Split CLIs across modules:

```python
# src/aria2/cli/start.py
import typer
app = typer.Typer()

@app.command()
def daemon():
    """Start aria2c as background daemon."""
    ...

@app.command()
def foreground():
    """Start aria2c in foreground."""
    ...

# src/aria2/cli/\_\_init\_\_.py
import typer
from aria2.cli.start import app as start\_app
from aria2.cli.status import app as status\_app

app = typer.Typer()
app.add\_typer(start\_app, name="start", help="Start aria2c daemon")
app.add\_typer(status\_app, name="status", help="Query daemon status")
```

**Help text precedence (lowest → highest):**

1. Inferred from `typer.Typer(callback=fn)`
2. Inferred from `@app.callback()` docstring
3. Inferred from `app.add\_typer(sub, callback=fn)`
4. Explicit `typer.Typer(help="...")`
5. Explicit `app.add\_typer(sub, help="...")`

### 8\. Rich Help Panels

Group related options in the help output:

```python
@app.command()
def start(
    host: str = typer.Option("localhost", "--host",
        rich\_help\_panel="Connection Settings"),
    port: int = typer.Option(6800, "--port", "-p",
        rich\_help\_panel="Connection Settings"),
    secret: str | None = typer.Option(None, "--secret", "-s",
        rich\_help\_panel="Connection Settings"),
    dir: pathlib.Path | None = typer.Option(None, "--dir", "-d",
        rich\_help\_panel="Download Settings"),
    daemon: bool = typer.Option(False, "--daemon",
        rich\_help\_panel="Runtime Options"),
):
    ...
```

### 9\. Progress Bars \& Spinners

```python
from rich.progress import Progress, SpinnerColumn, TextColumn

# Spinner (unknown duration)
with Progress(
    SpinnerColumn(),
    TextColumn("\[progress.description]{task.description}"),
    transient=True,
) as progress:
    progress.add\_task(description="Connecting...", total=None)
    ...  # async work

# Progress bar (known steps)
from rich.progress import track

for \_ in track(range(100), description="Downloading..."):
    await asyncio.sleep(0.01)
```

Or use `typer.progressbar()` as a lightweight alternative:

```python
with typer.progressbar(range(100), length=100) as progress:
    for value in progress:
        ...
```

### 10\. Environment Variables

```python
secret: str | None = typer.Option(
    None, "--secret", "-s",
    envvar="ARIA2\_SECRET",           # Fallback to env var
    show\_envvar=True,                # Show in help: \[env: ARIA2\_SECRET]
    help="RPC secret token",
)
```

### 11\. Version Option

```python
from typing import Annotated
import sys

\_\_version\_\_ = "0.1.0"

def version\_callback(value: bool):
    if value:
        print(f"aria2-sdk v{\_\_version\_\_}")
        raise typer.Exit()

@app.callback()
def main(
    version: Annotated\[bool, typer.Option(
        "--version", "-V",
        is\_eager=True,
        callback=version\_callback,
        help="Show version and exit.",
    )] = False,
):
    ...
```

### 12\. Error Handling

```python
# Built-in Rich error formatting (auto)
typer.echo("Something went wrong", err=True)

# Exit with code
raise typer.Exit(code=1)

# Bad parameter (formatted error)
raise typer.BadParameter("Port must be between 1024 and 65535")

# Abort
typer.Abort()
```

### 13\. Prompt \& Confirmation

```python
@app.command()
def delete(
    gid: str = typer.Argument(help="Download GID"),
    force: bool = typer.Option(False, "--force", "-f",
        prompt="Are you sure?",
        confirmation\_prompt=True,
        help="Force without confirmation"),
):
    ...
```

## CLI Patterns for aria2 SDK

### Sync Command Pattern

```python
@app.command()
def check():
    """Check if aria2c binary is available."""
    try:
        binary = \_find\_binary()
        result = subprocess.run(\[str(binary), "--version"],
            capture\_output=True, text=True, check=False)
        if result.returncode == 0:
            typer.echo(f"✓ aria2c found: {binary}")
            typer.echo(result.stdout.splitlines()\[0])
        else:
            typer.echo(f"✗ aria2c at {binary} but execution failed", err=True)
            raise typer.Exit(code=1)
    except typer.Exit:
        raise
    except Exception as e:
        typer.echo(f"✗ {e}", err=True)
        raise typer.Exit(code=1)
```

### Async Command Pattern (via asyncio.run)

```python
@app.command()
def status(
    host: str = typer.Option("localhost", "--host", help="RPC host"),
    port: int = typer.Option(6800, "--port", "-p",
        min=1024, max=65535, help="RPC port"),
    secret: str | None = typer.Option(None, "--secret", "-s",
        envvar="ARIA2\_SECRET", help="RPC secret"),
):
    """Query a running aria2 daemon for version and stats."""
    import asyncio
    asyncio.run(\_status\_impl(host, port, secret))

async def \_status\_impl(host: str, port: int, secret: str | None) -> None:
    try:
        from aria2 import Aria2Client
        async with Aria2Client(host=host, port=port, secret=secret, timeout=5.0) as client:
            version = await client.system.get\_version()
            typer.echo(f"aria2 {version.version}")
            typer.echo(f"  Features: {', '.join(version.enabled\_features)}")
            try:
                stat = await client.status.get\_global\_stat()
                typer.echo(f"  Active: {stat.num\_active}  Waiting: {stat.num\_waiting}  Stopped: {stat.num\_stopped}")
                typer.echo(f"  Speed: ↓ {\_fmt\_speed(int(stat.download\_speed))}  ↑ {\_fmt\_speed(int(stat.upload\_speed))}")
            except Exception:
                pass
    except ConnectionRefusedError:
        typer.echo(f"✗ aria2 not running on {host}:{port}. Start it: aria2 start", err=True)
        raise typer.Exit(code=1)
    except Exception as e:
        typer.echo(f"✗ Error: {e}", err=True)
        raise typer.Exit(code=1)
```

### Subprocess Command (foreground daemon)

```python
@app.command()
def start(
    port: int = typer.Option(6800, "--port", "-p", min=1024, max=65535),
    secret: str | None = typer.Option(None, "--secret", "-s"),
    listen\_all: bool = typer.Option(False, "--listen-all"),
    dir: Annotated\[pathlib.Path | None, typer.Option("--dir", "-d")] = None,
    conf: Annotated\[pathlib.Path | None, typer.Option("--conf", "-c",
        exists=True, dir\_okay=False)] = None,
    daemon: bool = typer.Option(False, "--daemon"),
):
    """Start an aria2c daemon with RPC enabled."""
    binary = \_find\_binary()
    cmd = \[str(binary), "--enable-rpc", f"--rpc-listen-port={port}"]
    cmd.append("--rpc-listen-all=true" if listen\_all else "--rpc-listen-all=false")
    if secret:
        cmd.append(f"--rpc-secret={secret}")
    if dir:
        cmd.append(f"--dir={dir}")
    if conf:
        cmd.extend(\["--conf-path", str(conf)])

    if daemon:
        cmd.append("--daemon=true")
        typer.echo(f"🍃 aria2c daemon started on port {port}")
        subprocess.run(cmd, check=False)
    else:
        typer.echo(f"🍃 Starting aria2c on port {port} …")
        typer.echo("   Press Ctrl+C to stop")
        proc = subprocess.Popen(cmd, stdout=sys.stdout, stderr=sys.stderr)
        def \_shutdown(\*\_):
            proc.terminate()
        signal.signal(signal.SIGINT, \_shutdown)
        signal.signal(signal.SIGTERM, \_shutdown)
        proc.wait()
```

## Common Pitfalls

* **Async not supported natively**: Wrap `async def` commands with `asyncio.run()`. Don't use `async def` directly in `@app.command()`.
* **Callback breaks completion**: Always check `ctx.resilient\_parsing` in callbacks before printing or raising.
* **`--help` conflicts**: If you define a `--help` option manually, it will conflict with Typer's built-in. Use `context\_settings={"help\_option\_names": \["-h"]}` to customize.
* **`typer.echo()` vs `print()`**: `typer.echo()` handles encoding and is testable with `CliRunner`. Use it instead of `print()`.
* **Required Options**: Use `Annotated\[str, typer.Option()]` without default to make an option required.
* **`envvar` prefix**: Typer auto-prefixes envvar with the app name unless you set it explicitly.
* **`--version` with subcommands**: `is\_eager=True` + `raise typer.Exit()` in callback pattern needed for `--version` to work before other args.

## Testing with CliRunner

```python
from typer.testing import CliRunner
from aria2.cli import app

runner = CliRunner()

def test\_start\_help():
    result = runner.invoke(app, \["start", "--help"])
    assert result.exit\_code == 0
    assert "Start an aria2c daemon" in result.stdout

def test\_check\_no\_binary():
    result = runner.invoke(app, \["check"])
    assert result.exit\_code == 1
    assert "aria2c not found" in result.stdout
```

## Commands

```bash
uv run python -c "import typer; print(typer.\_\_version\_\_)"  # 0.26.5
uv run pytest -k "cli"                                       # Run CLI tests
uv run aria2 --help                                          # Test CLI
```

## Resources

* Documentation: [https://typer.tiangolo.com/](https://typer.tiangolo.com/)
* GitHub: [https://github.com/fastapi/typer](https://github.com/fastapi/typer)
* API Reference: [https://typer.tiangolo.com/reference/](https://typer.tiangolo.com/reference/)
* Tutorial: [https://typer.tiangolo.com/tutorial/](https://typer.tiangolo.com/tutorial/)
* Rich Integration: [https://typer.tiangolo.com/tutorial/progressbar/](https://typer.tiangolo.com/tutorial/progressbar/)

