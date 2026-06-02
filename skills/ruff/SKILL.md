---
name: ruff
description: "Trigger: ruff, lint, format, linter, formatter, Astral ruff, Python linting, Python formatting. Extremely fast Python linter and code formatter by Astral."
license: Apache-2.0
metadata:
  author: gentleman-programming
  version: "1.0"
---

## When to Use

- Linting Python code with autofix support
- Formatting Python code (replaces black, autopep8, yapf)
- Running the language server in editors
- Configuring per-project lint rules and formatting options
- CI integration for code quality checks
- Explaining rule semantics during code review

## Critical Patterns

### Two Commands: `check` and `format`

ruff has two independent subcommands:

```bash
ruff check [FILES]...    # Lint: find and fix violations
ruff format [FILES]...   # Format: auto-format code (replaces black)
```

Both read config from the same `[tool.ruff]` section in `pyproject.toml`.

### CLI Usage

```bash
ruff check src/                        # Lint source directory
ruff check --fix src/                  # Apply safe autofixes
ruff check --fix --unsafe-fixes src/   # Apply unsafe autofixes too
ruff check --diff src/                 # Show diff without applying
ruff check --watch src/                # Watch mode
ruff check --output-format github      # GitHub Actions annotations
ruff check --output-format json        # JSON output

ruff format src/                       # Format source directory
ruff format --check src/               # Check formatting without changing
ruff format --diff src/                # Show format diff
```

### Configuration via `pyproject.toml`

```toml
[tool.ruff]
target-version = "py314"        # Python target version
line-length = 100               # Line length (default 88)
indent-width = 4                # Indentation width
exclude = ["tests/**"]          # Exclude patterns
respect-ignore-files = true     # Respect .gitignore

[tool.ruff.lint]
select = ["E", "W", "F", "I", "N", "UP"]   # Rule categories to enable
ignore = ["E501"]                            # Rules to disable
per-file-ignores = {"tests/**" = ["N802"]}   # Per-file overrides
```

### Rule Selection

Enable by prefix (category). The full list:

| Prefix | Linter | Scope |
|---|---|---|
| `E`/`W` | pycodestyle | PEP 8 errors/warnings |
| `F` | Pyflakes | Logic errors, undefined names |
| `I` | isort | Import ordering |
| `N` | pep8-naming | Naming conventions |
| `UP` | pyupgrade | Modern Python syntax |
| `B` | flake8-bugbear | Bug-prone patterns |
| `SIM` | flake8-simplify | Code simplification |
| `C4` | flake8-comprehensions | Comprehensions/iterators |
| `RUF` | Ruff-specific | Ruff's own rules |
| `ANN` | flake8-annotations | Type annotations |
| `D` | pydocstyle | Docstring conventions |
| `PL` | Pylint | Ported Pylint rules |
| `TRY` | tryceratops | Exception handling |
| `FURB` | refurb | Modernization suggestions |
| `PERF` | Perflint | Performance checks |
| `PT` | flake8-pytest-style | pytest conventions |
| `T20` | flake8-print | Print statements |
| `S` | flake8-bandit | Security issues |
| `FAST` | FastAPI | FastAPI-specific |
| `AIR` | Airflow | Airflow-specific |

List all available linters: `ruff linter`

### Autofix Levels

```bash
ruff check --fix                    # Apply safe fixes only (default)
ruff check --fix --unsafe-fixes     # Include unsafe (may change semantics)
ruff check --fix-only               # Apply fixes but don't report remaining violations
ruff check --show-fixes             # Print fixed violations
ruff check --diff                   # Show diff instead of applying
```

### Format Options

```toml
[tool.ruff.format]
quote-style = "double"             # double, single, preserve
indent-style = "space"             # space, tab
line-ending = "lf"                 # lf, crlf, native, auto
docstring-code-format = true       # Format code in docstrings
docstring-code-line-length = "dynamic"  # Line length for docstring code
preview = false                    # Enable unstable formatting
skip-magic-trailing-comma = false  # Skip magic trailing comma
```

### Per-Rule Configuration

```toml
[tool.ruff.lint.per-file-ignores]
"__init__.py" = ["F401"]           # Allow unused imports in __init__
"tests/**" = ["D", "ANN"]          # Disable docs/annotations in tests

[tool.ruff.lint.flake8-pytest-style]
fixture-parentheses = true
parametrize-names-type = "csv"

[tool.ruff.lint.isort]
known-first-party = ["aria2"]
known-third-party = ["pydantic", "httpx", "websockets"]
```

### Output Formats

```bash
ruff check --output-format concise   # One violation per line
ruff check --output-format full      # Default: verbose with context
ruff check --output-format json      # JSON (useful for tooling)
ruff check --output-format github    # GitHub Actions annotations
ruff check --output-format gitlab    # GitLab Code Quality
ruff check --output-format junit     # JUnit XML
ruff check --output-format grouped   # Grouped by file
```

### Common Pitfalls

- **`select` overrides defaults**: Setting `select = [...]` replaces, not extends, defaults. Include all desired categories.
- **`ruff format` does NOT lint**: It only formats. Run `ruff check` separately for linting.
- **`ruff check --fix` only applies safe fixes**: Use `--unsafe-fixes` for fixes that may change semantics.
- **Line length mismatch**: `ruff format` and `ruff check E501` can disagree. Set both consistently via `line-length` at the `[tool.ruff]` level.
- **`.gitignore` is respected by default**: Files in `.gitignore` are excluded from ruff runs unless `--no-respect-ignore-files`.

## Code Examples

### Minimal project config
```toml
[tool.ruff]
target-version = "py314"
line-length = 100

[tool.ruff.lint]
select = ["E", "W", "F", "I", "N", "UP"]
```

### Full project config with format
```toml
[tool.ruff]
target-version = "py314"
line-length = 100
exclude = ["tests/**"]

[tool.ruff.lint]
select = ["E", "W", "F", "I", "N", "UP", "B", "SIM"]
ignore = ["E501"]
per-file-ignores = {"__init__.py" = ["F401"]}

[tool.ruff.format]
quote-style = "double"
docstring-code-format = true
```

### CI workflow
```yaml
steps:
  - uses: actions/checkout@v4
  - uses: astral-sh/setup-uv@v5
  - run: uv sync --locked
  - run: uv run ruff check src/ --output-format github
  - run: uv run ruff format --check src/
```

### Pre-commit hook
```yaml
- repo: https://github.com/astral-sh/ruff-pre-commit
  rev: v0.15.15
  hooks:
    - id: ruff
      args: [--fix]
    - id: ruff-format
```

### Quick fixes
```bash
# Auto-fix import ordering + other safe fixes
uv run ruff check --fix --select I .

# Just count violations without fixing
uv run ruff check --statistics .

# Check a single file
uv run ruff check src/aria2/client.py
```

## Commands

```bash
# ── Lint ────────────────────────────────────────────
ruff check src/                    # Lint directory
ruff check --fix src/              # Lint + autofix
ruff check --fix --unsafe-fixes    # Include unsafe fixes
ruff check --diff                  # Show fix diff only
ruff check --watch                 # Watch mode
ruff check --statistics            # Show violation counts

# ── Format ──────────────────────────────────────────
ruff format src/                   # Format directory
ruff format --check src/           # Check without changing
ruff format --diff                 # Show format diff
ruff format --preview              # Enable unstable formatting

# ── Rule Management ─────────────────────────────────
ruff rule E501                     # Explain a specific rule
ruff linter                        # List all supported linters
ruff config line-length            # Show config option docs

# ── Language Server ─────────────────────────────────
ruff server                        # Start LSP server

# ── Cache ───────────────────────────────────────────
ruff clean                         # Clear ruff cache

# ── Info ────────────────────────────────────────────
ruff --version                     # Show version
ruff check --help                  # Full CLI reference
ruff format --help                 # Format CLI reference
```

## Resources

- Repository: <https://github.com/astral-sh/ruff>
- Documentation: <https://docs.astral.sh/ruff/>
- Rules: <https://docs.astral.sh/ruff/rules/>
- Pre-commit: <https://github.com/astral-sh/ruff-pre-commit>
