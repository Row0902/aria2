\---

name: docstring-google
description: "Trigger: docstring, google style, documentation, doc, pydocstyle, ruff D, napoleon, sphinx. Write Google-style Python docstrings with best practices for clarity, consistency, and tooling."
license: Apache-2.0
metadata:
author: gentleman-programming
version: "1.0"
---

## When to Use

* Writing docstrings for Python modules, classes, functions, and methods
* Enforcing consistent documentation style across a project
* Configuring ruff pydocstyle (D rules) with Google convention
* Documenting public APIs with Args, Returns, Raises, Yields, Examples sections
* Writing docstrings compatible with Sphinx Napoleon for automatic API docs
* Reviewing or fixing docstring formatting issues

## Critical Patterns

### Google Style Anatomy

A Google-style docstring has this structure:

```python
def function(param1: str, param2: int = 0) -> bool:
    """Short summary line ending in a period.

    Extended description of the function, its behavior, and what it does.
    Can span multiple paragraphs. Use blank lines between paragraphs.

    Args:
        param1 (str): Description of param1. Describe purpose and format.
        param2 (int, optional): Description of param2. Defaults to 0.

    Returns:
        bool: Description of what is returned and under what conditions.

    Raises:
        ValueError: Description of when this error is raised.
        TypeError: Description of when this error is raised.

    Examples:
        >>> function("hello", 1)
        True
    """
```

### Required Elements

|Element|When|Format|
|-|-|-|
|Summary line|**Always**|One line, imperative mood, period at end|
|Extended description|When behavior isn't obvious from signature|Free text, blank line after summary|
|`Args:`|Function has parameters|One line per param: `name (type): description`|
|`Returns:`|Function returns a value (not None)|`type: description`|
|`Raises:`|Function raises documented exceptions|One line per exception type|
|`Yields:`|Generator function|Same format as Returns|
|`Examples:`|Complex usage or edge cases|Doctest-style or code blocks|

### Imperative Mood (always)

Write the summary line as a command, not a description:

```
✅ "Download a file from the given URI."
✅ "Parse the JSON-RPC response and return the result."
✅ "Connect to the aria2 daemon."

❌ "This function downloads a file."
❌ "This method will connect to the daemon."
❌ "Used for parsing responses."
```

The summary should answer "what does it do?", not "what is it?".

### Types in Args

```python
def example(a: str, b: int | None, c: list\[str]) -> None:
    """Example.

    Args:
        a: Parameter with type annotation. Type can be omitted if annotated.
        b (int | None): Type can be repeated here for clarity.
        c (list\[str]): List of strings to process.
    """
```

**Guideline**: When the function has type annotations, the type in `Args` is optional (redundant). However, many teams prefer to include it for readability in plain-text docs (Sphinx Napoleon shows it either way). Pick one convention and stick with it.

### Optional Parameters

```python
def connect(timeout: float = 30.0, retry: bool = True) -> None:
    """Connect to the server.

    Args:
        timeout (float, optional): Connection timeout in seconds.
            Defaults to 30.0.
        retry (bool, optional): Whether to retry on failure.
            Defaults to True.
    """
```

### Returns vs Yields

```python
def get\_status() -> DownloadStatusResponse:
    """Return the current download status.

    Returns:
        DownloadStatusResponse: Object with all download fields.
    """

def read\_events() -> Generator\[Event, None, None]:
    """Yield events from the WebSocket stream.

    Yields:
        Event: Next event from the stream.
    """
```

Note: For async generators, use `Yields:` as well.

### Raises

```python
def send\_request(method: str, params: list\[Any]) -> Any:
    """Send a JSON-RPC request.

    Args:
        method (str): JSON-RPC method name (e.g. "aria2.addUri").
        params (list\[Any]): Parameters for the method.

    Returns:
        Any: Result from the RPC response.

    Raises:
        Aria2ConnectionError: If the transport is not connected.
        Aria2RpcError: If the daemon returns a JSON-RPC error.
    """
```

### Module-level Docstrings

Every public module should have a docstring at the top:

```python
"""HTTP transport for aria2 JSON-RPC using httpx.

This module provides the HTTP-based transport layer for communicating
with the aria2 daemon via JSON-RPC 2.0 over HTTP POST.
"""

from \_\_future\_\_ import annotations
...
```

The module docstring should describe what the module contains and its role in the package.

### Class Docstrings

```python
class HttpTransport(Transport):
    """JSON-RPC over HTTP via httpx.

    Connects to ``http://{host}:{port}/jsonrpc`` using a dedicated
    ``httpx.AsyncClient`` per transport instance.

    Attributes:
        host (str): The hostname of the aria2 daemon.
        port (int): The port number of the aria2 daemon.
    """
```

Include `Attributes:` section for important instance attributes that aren't obvious from `\_\_init\_\_`.

### One-liners vs Multi-line

Use a one-line docstring for simple, obvious functions:

```python
@property
def is\_connected(self) -> bool:
    """Return whether the transport is currently connected."""
```

Use multi-line for any function with parameters, returns, or non-obvious behavior.

## Ruff Configuration
## Ruff Configuration (generico)

Enable Google-style docstring checking in `pyproject.toml`:

```toml
[tool.ruff.lint]
select = ["E", "W", "F", "I", "N", "UP", "D"]

[tool.ruff.lint.pydocstyle]
convention = "google"
```

> **⚠️ En este proyecto**, `D` rules no estan activas por defecto en `[tool.ruff.lint].select`. Para habilitarlas:
> ```toml
> [tool.ruff.lint]
> extend-select = ["D"]
> 
> [tool.ruff.lint.pydocstyle]
> convention = "google"
> ```

Para anadir o quitar reglas sobre una convencion:

```toml
[tool.ruff.lint]
extend-select = ["D400"]       # Anade una regla excluida por Google
ignore = ["D417"]              # No exige Args docs para cada parametro

[tool.ruff.lint.pydocstyle]
convention = "google"
```
```

### Key Pydocstyle Rules (D)

|Rule|Description|Google convention|
|-|-|-|
|D100|Missing docstring in public module|✅|
|D101|Missing docstring in public class|✅|
|D102|Missing docstring in public method|✅|
|D103|Missing docstring in public function|✅|
|D104|Missing docstring in public package|✅|
|D105|Missing docstring in magic method|❌|
|D107|Missing docstring in `\_\_init\_\_`|❌|
|D200|One-line docstring should fit on one line|✅|
|D202|No blank lines after docstring|✅|
|D203|Blank line before class docstring|❌ (conflicts with D211)|
|D204|Blank line after class docstring|✅|
|D205|Blank line between summary and description|✅|
|D210|No whitespace around docstring quotes|✅|
|D211|No blank line before class docstring|✅|
|D212|Summary on first docstring line|❌ (conflicts with D213)|
|D213|Summary on second docstring line|✅|
|D214|Section on last line|✅|
|D215|No section underline|✅|
|D300|Use triple double quotes|✅|
|D400|First line should end with period|✅|
|D401|First line in imperative mood|✅|
|D402|First line should not be function signature|✅|
|D403|First word capitalized|✅|
|D404|First word not "This"|✅|
|D405|Section name properly capitalized|✅|
|D406|Section name ends with colon|✅|
|D407|Dashes/underlines after section|✅|
|D408|Section underline|✅|
|D409|Section should be indented|✅|
|D410|Blank line after section|✅|
|D411|Blank line before section|✅|
|D412|Blank lines between section headers and content|✅|
|D413|Blank line after last section|✅|
|D414|Non-empty section|✅|
|D415|Punctuation at end of summary|✅|
|D416|Section name ends with colon (uppercase)|✅|
|D417|Document arguments in Args section|✅|

### Google vs NumPy vs PEP 257

|Convention|Style|Best for|
|-|-|-|
|`convention = "google"`|`Args:`, `Returns:`, `Raises:`|Most projects, Sphinx Napoleon|
|`convention = "numpy"`|NumPy-style with type as comment|Scientific/data projects|
|`convention = "pep257"`|Minimal PEP 257 compliance|Minimal docs|

## Integration with Sphinx Napoleon

Sphinx Napoleon (part of `sphinx.ext.napoleon`) parses Google-style docstrings into reStructuredText for API documentation.

```python
# conf.py
extensions = \[
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon',
]
```

Napoleon renders:

* `Args:` → `:param` / `:type` entries
* `Returns:` → `:returns:` / `:rtype:` entries
* `Raises:` → `:raises:` entries
* `Examples:` → `.. code-block::` blocks
* `Attributes:` → `:ivar` entries

### Napoleon-Specific Tips

* **Type annotations are preferred**: Napoleon uses types from annotations (`def f(x: int)`) when available, falling back to `Args:` types.
* **`optional` marker**: Napoleon recognizes `(type, optional)` and renders it appropriately.
* **`\\n` for line breaks**: Use explicit indentation for continuation lines.
* **Section headers**: Must be `Args:`, `Returns:`, `Raises:`, `Yields:`, `Examples:`, `Note:`, `Warning:`, `Attributes:`.

## Best Practices

### 1\. Summary line rules

* **Imperative mood**: "Parse the response" not "This function parses"
* **End with period**: Even one-liners get a period
* **No signature in summary**: Not `"parse\_response(data) -> result"`
* **No type info in summary**: Types go in `Args:` / `Returns:`

### 2\. Keep it DRY

Don't repeat what's obvious from the type signature:

```python
# ❌ Redundant
def add(a: int, b: int) -> int:
    """Add two integers and return an integer."""

# ✅ Better — focus on behavior
def add(a: int, b: int) -> int:
    """Return the sum of two numbers."""
```

### 3\. Document behavior, not implementation

```python
# ❌ Implementation detail
def connect() -> None:
    """Create an httpx.AsyncClient and open a TCP socket."""

# ✅ Public behavior
def connect() -> None:
    """Connect to the aria2 daemon and prepare the transport."""
```

### 4\. Document what the caller needs to know

* Side effects (e.g., "Modifies the internal state")
* Preconditions (e.g., "Must be called after connect()")
* Postconditions (e.g., "Closes the connection")
* Thread safety (e.g., "Not thread-safe")

### 5\. Cross-references

Use backticks to reference other code:

```python
"""Connect to the aria2 daemon.

Uses :class:`httpx.AsyncClient` for HTTP transport.
Raises :exc:`Aria2ConnectionError` if the connection fails.
See :meth:`close` for cleanup.
"""
```

For Sphinx Napoleon, use `:class:`, `:func:`, `:meth:`, `:exc:`, `:mod:`, `:attr:`.

### 6\. Examples section

Include examples for complex APIs:

```python
def add\_uri(self, uris: list\[str], options: dict | None = None) -> GID:
    """Add a download by URI.

    Args:
        uris (list\[str]): One or more URIs for the download.
        options (dict | None): Optional aria2 options.

    Returns:
        GID: The download identifier.

    Examples:
        >>> client = Aria2Client(secret="token")
        >>> gid = await client.add\_uri(\["https://example.com/file.iso"])
        >>> print(gid)
        abc123def4567890
    """
```

### 7\. Private vs Public

* **Public API**: Always docstring (module, class, method, function, property)
* **Private (`\_` prefix)**: Docstring optional, but useful for complex internal logic
* **Dunder methods**: Docstring optional, use when non-obvious
* **`\_\_init\_\_`**: Docstring goes on the class, not `\_\_init\_\_` (by Google convention)

### 8\. Blank line rules (Ruff enforced)

```
✅ Correct:
   """Summary.
<blank line>
   Extended description.
<blank line>
   Args:
       param: Description.
"""

❌ Wrong:
   """Summary.

   Extended description.
   Args:
       param: Description.

"""

❌ Wrong (no blank after last section):
   """Summary.

   Args:
       param: Description.
   Returns:
       result: Description.
   """
```

### 9\. Quotes

Always use triple double quotes `"""`:

```python
"""..."""   # ✅ Correct
'''...'''   # ❌ Wrong
```

### 10\. One-line docstring format

```python
"""Return the current connection status."""  # ✅ Correct
""" Return the current connection status. """  # ❌ Wrong (whitespace)
"""Return the current connection status."""   # ✅ (starts and ends on same line)
```

## Code Examples

### Module-level

```python
"""HTTP transport for aria2 JSON-RPC using httpx.

This module implements the HTTP transport layer for communicating
with the aria2 daemon. It wraps httpx.AsyncClient and handles
JSON-RPC 2.0 request/response over HTTP POST.
"""
```

### Class with attributes

```python
class Transport(ABC):
    """Abstract base for aria2 JSON-RPC transports.

    Defines the interface that all transports must implement.
    Subclasses provide specific protocol implementations.

    Attributes:
        is\_connected (bool): Whether the transport is connected.
    """
```

### Method with full docs

```python
async def change\_position(
    self,
    gid: GID,
    pos: int,
    how: PositionHow,
) -> int:
    """Change the position of a download in the queue.

    The ``how`` parameter determines how ``pos`` is interpreted:
    ``POS\_SET`` sets the absolute position, ``POS\_CUR`` moves
    relative to current, ``POS\_END`` sets position from the end.

    Args:
        gid (GID): The download to reposition.
        pos (int): The position value.
        how (PositionHow): How to interpret ``pos``.

    Returns:
        int: The resulting absolute position.

    Raises:
        Aria2ConnectionError: If not connected.
        Aria2RpcError: If the daemon rejects the command.

    Examples:
        >>> await client.change\_position(gid, 0, PositionHow.SET)
        0
        >>> await client.change\_position(gid, -1, PositionHow.CUR)
        1
    """
```

### Property

```python
@property
def is\_connected(self) -> bool:
    """Return whether the transport is currently connected.

    Returns:
        bool: ``True`` if connected and ready, ``False`` otherwise.
    """
    return self.\_connected
```

### Generator

```python
async def read\_notifications(self) -> AsyncGenerator\[Notification, None]:
    """Yield incoming notifications from the daemon.

    Yields:
        Notification: Parsed JSON-RPC 2.0 notification events.
    """
```

### Simple getter/setter

```python
def get\_version(self) -> str:
    """Return the aria2 daemon version string."""
```

## Common Pitfalls

* **Missing `Args:` section**: Ruff D417 catches this when enabled.
* **Type in `Args:` conflicts with annotation**: Keep them in sync. Napoleon prefers type annotations.
* **Forgetting `Raises:`**: Document exceptions the caller must handle.
* **`\_\_init\_\_` docstring vs class docstring**: Put class docs on the class, not `\_\_init\_\_`.
* **Imperative mood violations**: "This function" (❌) → "Return"/"Parse"/"Connect" (✅).
* **Blank line after last section**: D413 enforces this automatically.
* **Section names**: Must be `Args:` not `Arguments:` or `Parameters:` for Google style.
* **Optional defaults**: Use `(type, optional)` format and mention default value.

## Commands

```bash
# ── Ruff docstring checks ────────────────────────────
uv run ruff check --select D src/         # Check all docstring rules
uv run ruff check --select D --statistics  # Summary of violations
uv run ruff check --fix --select D src/   # Auto-fix docstring issues
uv run ruff rule D213                     # Explain a specific D rule

# ── Enable Google convention ─────────────────────────
# Add to pyproject.toml:
#   \[tool.ruff.lint.pydocstyle]
#   convention = "google"

# ── Sphinx Napoleon (if using Sphinx) ─────────────────
# In conf.py:
#   extensions = \['sphinx.ext.napoleon', 'sphinx.ext.autodoc']
```

## Resources

* Google Python Style Guide (docstrings): [https://google.github.io/styleguide/pyguide.html](https://google.github.io/styleguide/pyguide.html)
* PEP 257: [https://peps.python.org/pep-0257/](https://peps.python.org/pep-0257/)
* Sphinx Napoleon: [https://www.sphinx-doc.org/en/master/usage/extensions/napoleon.html](https://www.sphinx-doc.org/en/master/usage/extensions/napoleon.html)
* Ruff pydocstyle rules: [https://docs.astral.sh/ruff/rules/#pydocstyle-d](https://docs.astral.sh/ruff/rules/#pydocstyle-d)
* Ruff Google convention: [https://docs.astral.sh/ruff/settings/#lint-pydocstyle-convention](https://docs.astral.sh/ruff/settings/#lint-pydocstyle-convention)

