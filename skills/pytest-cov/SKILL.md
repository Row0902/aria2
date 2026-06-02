---
name: pytest-cov
description: "Trigger: pytest-cov, coverage, test coverage, code coverage, coverage report, pytest coverage, branch coverage. Coverage reporting plugin for pytest — measure, report, and enforce code coverage."
license: Apache-2.0
metadata:
  author: gentleman-programming
  version: "1.0"
---

## When to Use

- Measuring code coverage during test runs
- Generating coverage reports (terminal, HTML, XML, JSON, Markdown, LCOV)
- Enforcing minimum coverage thresholds in CI
- Tracking uncovered lines, branches, and missing paths
- Combining coverage across multiple test runs
- Excluding non-testable code from coverage (debug, repr, TYPE_CHECKING)

## Critical Patterns

### Basic Usage

```bash
uv add --dev pytest-cov
```

Then run with coverage:

```bash
uv run pytest --cov=src/aria2
```

This measures coverage of the `src/aria2` package and prints a terminal report.

### CLI Options

```bash
uv run pytest --cov=src/aria2                       # Package to measure
uv run pytest --cov=src/aria2 --cov-report=term-missing  # Show missing lines
uv run pytest --cov=src/aria2 --cov-report=html      # HTML report
uv run pytest --cov=src/aria2 --cov-report=xml       # Cobertura XML (CI)
uv run pytest --cov=src/aria2 --cov-report=json      # JSON report
uv run pytest --cov=src/aria2 --cov-report=markdown  # Markdown report
uv run pytest --cov=src/aria2 --cov-report=lcov      # LCOV report
uv run pytest --cov=src/aria2 --cov-branch           # Branch coverage
uv run pytest --cov=src/aria2 --cov-fail-under=80    # Fail if < 80%
uv run pytest --cov=src/aria2 --no-cov-on-fail       # No report on failure
uv run pytest --cov=                              # All sources (no filter)
```

### Report Types

| Type | Output | Best for |
|---|---|---|
| `term` | Console summary | Quick local check |
| `term-missing` | Console + shows uncovered lines | Development |
| `term-missing:skip-covered` | Skip files with 100% coverage | Focused review |
| `html` | `htmlcov/index.html` | Visual browsing |
| `xml` | `coverage.xml` | CI (Codecov, Sonar) |
| `json` | `coverage.json` | Tooling |
| `markdown` | Markdown table | PR comments, docs |
| `lcov` | `coverage.lcov` | Editor integration |
| `annotate` | Annotated source files | Line-by-line review |

Multiple reports at once:

```bash
uv run pytest --cov=src/aria2 \
  --cov-report=term-missing \
  --cov-report=html \
  --cov-report=xml:coverage.xml
```

### pyproject.toml Configuration

```toml
[tool.coverage.run]
source = ["src"]                       # Measure only source/
omit = [
    "src/aria2/bin/*",                 # Skip binary management
    "src/aria2/**/__main__.py",        # Skip CLI entry points
    "src/aria2/_version.py",           # Auto-generated version
]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",                # Explicit exclusion marker
    "def __repr__",                    # Magic methods rarely tested
    "def __str__",
    "raise NotImplementedError",       # Abstract methods
    "if TYPE_CHECKING:",                # Type checking only
    "@overload",                       # Overload variants
    "pass",                            # Abstract stubs
]
skip_covered = true                     # Omit 100% covered files from report
show_missing = true                     # Show line numbers of missing lines

[tool.coverage.html]
directory = "coverage_html"             # Custom HTML output dir
```

### Branch Coverage

Branch coverage measures whether each possible branch (`if/else`) was taken:

```bash
uv run pytest --cov=src/aria2 --cov-branch
```

Config in pyproject.toml:

```toml
[tool.coverage.run]
branch = true
```

**When to enable**: When you care about untested `else` branches, `except` handlers, and conditional logic. Adds ~15% more lines to report.

### Coverage in CI

```yaml
# GitHub Actions
steps:
  - uses: actions/checkout@v4
  - uses: astral-sh/setup-uv@v5
  - run: uv sync --locked
  - run: uv run pytest --cov=src/aria2 --cov-report=xml --cov-report=term-missing
  - uses: codecov/codecov-action@v5
    with:
      file: ./coverage.xml
```

### Coverage Threshold (fail if below)

```bash
uv run pytest --cov-fail-under=80
```

| Environment | Threshold | Rationale |
|---|---|---|
| Development | None | Exploratory |
| CI — new project | 70% | Minimum bar |
| CI — mature project | 80% | Standard |
| CI — critical SDK | 90% | Public API fully covered |

### Combining Coverage

When tests run in parallel (e.g., split by marker):

```bash
# First run
uv run pytest -m "unit" --cov=src/aria2 --cov-append
# Second run (appends)
uv run pytest -m "integration" --cov=src/aria2 --cov-append
# Final combined report (no --cov, just report)
uv run pytest --cov=src/aria2 --cov-report=html
```

### Excluding Code from Coverage

**In Python code**:
```python
def debug_only() -> None:  # pragma: no cover
    ...

if False:  # pragma: no cover
    ...
```

**In pyproject.toml** (pattern-based):
```toml
[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "raise NotImplementedError",
    "if TYPE_CHECKING:",
    "def __str__",
    "@overload",
]

[tool.coverage.run]
omit = [
    "tests/*",
    "**/__main__.py",
    "**/_version.py",
]
```

### Combining with pytest.ini filterwarnings

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
filterwarnings = ["error"]

[tool.coverage.run]
source = ["src"]
omit = ["src/aria2/bin/*"]
```

## Best Practices for SDKs

### 1. Target 90%+ on public API
The client, transports, and models should have >90% coverage. CLI, bin, and errors can be lower.

### 2. Use `term-missing` during development
Shows exactly which lines aren't covered — makes it actionable.

### 3. Set a CI threshold
`--cov-fail-under=80` prevents coverage regressions.

### 4. Exclude non-testable patterns
`__repr__`, `TYPE_CHECKING`, `abc` methods should be excluded.

### 5. Run coverage in CI, not just locally
Local dev runs without `--cov` for speed. CI adds it.

### 6. Generate XML for Codecov/Sonar
Upload `coverage.xml` to see trends and PR annotations.

## Common Pitfalls

- **`--cov` without package**: Without `--cov=src/aria2`, pytest-cov measures nothing. Use `--cov=` (empty) to measure everything.
- **Coverage not matching expectations**: If `omit` patterns are wrong, coverage includes library files (httpx, pydantic). Always `omit = ["*/site-packages/*"]` or set `source` explicitly.
- **`--cov-append` across test modes**: Running with `--cov-append` accumulates results. Without it, each run resets.
- **`--no-cov-on-fail`**: If tests fail, coverage report isn't generated. Use this in CI to avoid misleading reports.
- **Branch coverage penalty**: Enabling `--cov-branch` roughly doubles the number of "missed" lines. Adjust thresholds accordingly.
- **Pytest-cov vs standalone coverage**: `pytest-cov` integrates coverage into pytest. `coverage run` is standalone. Prefer pytest-cov.

## Commands

```bash
# ── Quick coverage ──────────────────────────────────
uv run pytest --cov=src/aria2
uv run pytest --cov=src/aria2 --cov-report=term-missing
uv run pytest --cov=src/aria2 --cov-branch

# ── Full reports ───────────────────────────────────
uv run pytest --cov=src/aria2 \
  --cov-report=term-missing \
  --cov-report=html \
  --cov-report=xml:coverage.xml

# ── Threshold ──────────────────────────────────────
uv run pytest --cov=src/aria2 --cov-fail-under=80

# ── CI ─────────────────────────────────────────────
uv run pytest --cov=src/aria2 --cov-report=xml --no-cov-on-fail

# ── Version ────────────────────────────────────────
uv run python -c "import pytest_cov; print(pytest_cov.__version__)"
```

## Resources

- pytest-cov: <https://github.com/pytest-dev/pytest-cov>
- Coverage.py: <https://coverage.readthedocs.io/>
- Codecov: <https://about.codecov.io/>
- Config: <https://coverage.readthedocs.io/en/latest/config.html>
