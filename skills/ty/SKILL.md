\---

name: ty
description: "Trigger: ty, type check, type checker, Astral ty, replace mypy, typing. Fast Python type checker by Astral — replacement for mypy/pyright/pyre."
license: Apache-2.0
metadata:
author: gentleman-programming
version: "1.0"
---

## When to Use

* Type-checking Python projects as part of CI, pre-commit, or local dev
* Replacing mypy with a faster Rust-based type checker
* Running the type-checker language server in editors
* Configuring type-checking rules per-project
* Explaining ty rule semantics during code review

## Critical Patterns

### CLI Usage

```bash
ty check \[PATH]...               # Check files/dirs (default: project root)
ty check --fix                   # Apply auto-fixes (ty: ignore comments)
ty check --watch                 # Watch mode for development
ty check --output-format github  # GitHub Actions annotations
ty check --python-version 3.14   # Override Python version
ty check --python-platform linux # Override target platform
ty check --add-ignore            # Add ty: ignore comments for all diagnostics
ty server                        # Start LSP language server
ty explain rule <RULE>           # Explain a specific rule
ty explain rule                  # List all rules with descriptions
```

### Configuration via `pyproject.toml`

All ty config lives under `\[tool.ty]`. No separate `ty.toml` needed by default.

```toml
\[tool.ty.environment]
python-version = "3.14"                          # Python version for stdlib types
python-platform = "linux"                        # Platform for sys.platform specialization

\[tool.ty.rules]
possibly-unresolved-reference = "warn"           # Override severity: error, warn, or ignore
unused-awaitable = "error"

\[tool.ty.src]
include = \["src"]                                # Source directories to type-check
exclude = \["tests/\*\*", "\*\*/\_\_pycache\_\_/\*\*"]

\[tool.ty]
respect-ignore-files = true                      # Respect .gitignore etc.
force-exclude = true                             # Enforce exclusions even for explicit paths
```

### Rule Severity Control

Each of ty's 120+ rules can have severity set individually:

```
ty: error | warn | ignore
```

Set in `\[tool.ty.rules]`:

```toml
\[tool.ty.rules]
# Set specific rules
invalid-argument-type = "error"
implicit-concatenated-string-type-annotation = "warn"
unresolved-import = "error"

# Or set all rules then override
# (no wildcard yet — set explicitly per rule)
```

### CLI Rule Overrides

```bash
ty check --error invalid-argument-type           # Treat rule as error
ty check --warn possibly-unresolved-reference    # Treat rule as warn
ty check --ignore unused-awaitable               # Disable rule entirely
ty check --error all --warn deprecated           # All errors, deprecated as warn
```

### Output Formats

```bash
ty check --output-format full       # Default: verbose with context and hints
ty check --output-format concise    # One diagnostic per line
ty check --output-format github     # GitHub Actions annotations
ty check --output-format gitlab     # GitLab Code Quality JSON
ty check --output-format junit      # JUnit XML report
```

### Exit Codes

```bash
ty check                     # Exit 0 = all good, 1 = errors found
ty check --error-on-warning  # Exit 1 if any warnings exist too
ty check --exit-zero         # Always exit 0 (ignore diagnostics)
```

### Python Environment Resolution

ty resolves third-party imports automatically:

* Uses `.venv` if found in project directory
* `--python <path>` to point to a specific interpreter or venv
* `--typeshed <path>` for custom stdlib stubs
* `--extra-search-path <path>` for unconventional module locations
* Also reads `.python-version` and `requires-python` from `pyproject.toml`

### Suppressing Diagnostics

```python
# Inline ignore for a specific line
x = 1  # ty: ignore

# Ignore with a specific rule code
x = 1  # ty: ignore = unused-awaitable

# File-level ignore (top of file)
# ty: ignore = unused-awaitable
```

### Migration from mypy

|mypy config|ty equivalent|
|-|-|
|`python\_version = "3.14"`|`\[tool.ty.environment] python-version = "3.14"`|
|`strict = true`|Not a single flag — enable rules individually|
|`mypy --strict`|`ty check` with per-rule error levels|
|`disable\_error\_code = \["X"]`|`\[tool.ty.rules] X = "ignore"`|
|`# type: ignore`|`# ty: ignore`|
|`# type: ignore\[arg-type]`|`# ty: ignore = invalid-argument-type`|

### Common Pitfalls

* **No `strict` mode**: Unlike mypy, ty has no blanket `strict = true`. Configure rules explicitly in `\[tool.ty.rules]`.
* **ty and mypy can coexist**: During migration, both can run. ty ignores `\[tool.mypy]` sections.
* **Inline comments use `ty: ignore`**, not `type: ignore`. mypy's `# type: ignore` is not recognized.
* **`--add-ignore`** adds `# ty: ignore` comments to suppress ALL current diagnostics — use sparingly.
* **ty 0.0.x is pre-1.0**: Rules and config may change. Pin the version in `\[dependency-groups.dev]`.

## Code Examples

### Full pyproject.toml config

```toml
\[tool.ty.environment]
python-version = "3.14"

\[tool.ty.rules]
possibly-unresolved-reference = "warn"
invalid-argument-type = "error"
unresolved-import = "error"
redundant-cast = "warn"

\[tool.ty.src]
include = \["src"]
exclude = \["tests/\*\*"]
```

### CI workflow

```yaml
steps:
  - uses: actions/checkout@v4
  - uses: astral-sh/setup-uv@v5
  - run: uv sync --locked
  - run: uv run ty check src/ --output-format github
```

### Quick migration from mypy

```bash
# 1. Add ty to dev deps
uv add --dev ty

# 2. Replace \[tool.mypy] with \[tool.ty] in pyproject.toml

# 3. Run ty to see what it catches
uv run ty check src/

# 4. Fix findings or add ignores
uv run ty check src/ --error-on-warning

# 5. Remove mypy config and dev dep
uv remove mypy
```

## Commands

```bash
# ── Type Checking ────────────────────────────────────
ty check src/                      # Type-check source directory
ty check --fix                     # Auto-apply ty: ignore comments
ty check --watch                   # Watch mode
ty check -v                        # Verbose output

# ── Rule Management ──────────────────────────────────
ty explain rule                    # List all rules
ty explain rule invalid-argument-type  # Explain specific rule
ty check --ignore unused-awaitable # Disable a rule on CLI

# ── Output Formats ──────────────────────────────────
ty check --output-format concise   # One-line diagnostics
ty check --output-format github    # GitHub annotations
ty check --output-format junit     # JUnit XML

# ── Language Server ─────────────────────────────────
ty server                          # Start LSP server

# ── Version ─────────────────────────────────────────
ty --version                       # Show version
ty check --help                    # Full CLI reference
```

## Resources

* Repository: [https://github.com/astral-sh/ty](https://github.com/astral-sh/ty)
* Documentation: [https://docs.astral.sh/ty/](https://docs.astral.sh/ty/)

