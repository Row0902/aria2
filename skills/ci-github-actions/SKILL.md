---
name: ci-github-actions
description: "Trigger: CI, GitHub Actions, workflow, continuous integration, test runner, build pipeline, lint CI, type check CI. CI/CD with GitHub Actions for Python projects — lint, type-check, test, build, release."
license: Apache-2.0
metadata:
  author: gentleman-programming
  version: "1.0"
---

## When to Use

- Running tests, linters, and type checkers in CI
- Building and publishing Python packages to PyPI
- Setting up caching for faster CI runs
- Defining matrix jobs (different Python versions, OS)
- Automating release workflows
- Adding status checks to GitHub PRs
- Configurar checks que validen `pyproject.toml` y `uv.lock`

## Critical Patterns

### Minimal CI: Lint + Type-Check + Test

The essential CI pipeline for this SDK:

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  quality:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
        with:
          enable-cache: true
          cache-dependency-glob: "uv.lock"
      - run: uv sync --locked
      - run: uv run ruff check src/
      - run: uv run ruff format --check src/
      - run: uv run ty check src/

  test:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
        with:
          enable-cache: true
          cache-dependency-glob: "uv.lock"
      - run: uv sync --locked
      - run: uv run pytest -v --cov=src/aria2 --cov-report=xml
      - uses: codecov/codecov-action@v5
        with:
          file: ./coverage.xml
```

### Using `astral-sh/setup-uv`

This is the official GitHub Action for setting up uv:

```yaml
- uses: astral-sh/setup-uv@v5
  with:
    enable-cache: true                    # Cache uv downloads
    cache-dependency-glob: "uv.lock"      # Cache key based on lockfile
    cache-local-path: ~/.cache/uv         # Cache path
    github-token: ${{ secrets.GITHUB_TOKEN }}  # Avoid rate limits
```

After setup-uv, `uv` is on PATH and `uv sync --locked` installs dependencies.

### Python Matrix Testing

```yaml
test:
  strategy:
    matrix:
      python-version: ["3.14"]
      os: [ubuntu-24.04, macos-14, windows-2025]
    fail-fast: false

  runs-on: ${{ matrix.os }}
  steps:
    - uses: actions/checkout@v4
    - uses: astral-sh/setup-uv@v5
      with:
        enable-cache: true
    - run: uv python install ${{ matrix.python-version }}
    - run: uv python pin ${{ matrix.python-version }}
    - run: uv sync --locked
    - run: uv run pytest -v
```

### Build + Publish to PyPI

```yaml
name: Release

on:
  release:
    types: [published]

permissions:
  id-token: write  # For PyPI trusted publishing

jobs:
  build:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
        with:
          enable-cache: true
      - run: uv sync --locked
      - run: uv build
      - uses: actions/upload-artifact@v4
        with:
          name: dist
          path: dist/

  publish:
    needs: [build]
    runs-on: ubuntu-24.04
    environment:
      name: pypi
      url: https://pypi.org/p/aria2
    permissions:
      id-token: write
    steps:
      - uses: actions/download-artifact@v4
        with:
          name: dist
          path: dist/
      - uses: astral-sh/setup-uv@v5
      - run: uv publish
```

### Caching Strategy

```yaml
- uses: astral-sh/setup-uv@v5
  with:
    enable-cache: true
    cache-dependency-glob: "uv.lock"
```

Cache keys are based on `uv.lock` hash + OS. On cache miss, uv downloads everything fresh. On hit, it restores cached `.venv` and package downloads.

### Combined Quality Workflow

```yaml
name: Quality

on:
  push:
    branches: [main]
  pull_request:

jobs:
  lint:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
        with:
          enable-cache: true
      - run: uv sync --locked
      - run: uv run ruff check src/ --output-format github
      - run: uv run ruff format --check src/

  typecheck:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
        with:
          enable-cache: true
      - run: uv sync --locked
      - run: uv run ty check src/ --output-format github

  test:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
        with:
          enable-cache: true
      - run: uv sync --locked
      - run: uv run pytest -v -q --cov=src/aria2 --cov-report=term-missing
```

### Pre-commit in CI

```yaml
- uses: pre-commit/action@v3.0.1
```

Or run manually:

```yaml
- run: uv tool install pre-commit
- run: pre-commit run --all-files --show-diff-on-failure
```

### Workflow Triggers

```yaml
on:
  push:                         # On push to these branches
    branches: [main]
  pull_request:                 # On PRs to these branches
    branches: [main]
  workflow_dispatch:            # Manual trigger (GitHub UI)
    inputs:
      version:
        description: "Version tag"
        required: false
  schedule:                     # Scheduled
    - cron: "0 6 * * 1"        # Every Monday at 6 AM
```

### Status Badges

Add to `README.md`:

```markdown
[![CI](https://github.com/Row0902/aria2/actions/workflows/quality.yml/badge.svg)](https://github.com/Row0902/aria2/actions)
[![Build](https://github.com/Row0902/aria2/actions/workflows/build-aria2.yml/badge.svg)](https://github.com/Row0902/aria2/actions/workflows/build-aria2.yml)
[![PyPI](https://img.shields.io/pypi/v/aria2.svg)](https://pypi.org/project/aria2/)
[![Python](https://img.shields.io/pypi/pyversions/aria2.svg)](https://pypi.org/project/aria2/)
```

### Workflows del proyecto

Este proyecto tiene (o debería tener) estos workflows:

#### 1. `quality.yml` — Lint + Type-check + Test

```yaml
name: Quality

on:
  push:
    branches: [main]
  pull_request:

jobs:
  quality:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
        with:
          enable-cache: true
          cache-dependency-glob: "uv.lock"
      - run: uv sync --locked
      - run: uv run ruff check src/
      - run: uv run ruff format --check src/
      - run: uv run ty check src/ --output-format github
      - run: uv run pytest -v -q --cov=src/aria2 --cov-report=term-missing
```

#### 2. `build-aria2.yml` — Build static binary (ya existe)

```yaml
# .github/workflows/build-aria2.yml
# Builds aria2c static binary from source.
# Se activa: manualmente (workflow_dispatch) o mensualmente (schedule).
# Publica el binario como artifact de GitHub.
```

Ver archivo existente en `.github/workflows/build-aria2.yml`.

#### 3. `release.yml` — Publicar a PyPI (futuro)

```yaml
name: Release

on:
  release:
    types: [published]

jobs:
  build:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - run: uv sync --locked
      - run: uv build
      - uses: actions/upload-artifact@v4
        with:
          name: dist
          path: dist/
  publish:
    needs: [build]
    runs-on: ubuntu-24.04
    environment: pypi
    permissions:
      id-token: write
    steps:
      - uses: actions/download-artifact@v4
        with:
          name: dist
          path: dist/
      - uses: astral-sh/setup-uv@v5
      - run: uv publish
```

---

### Common Pitfalls

- **`uv sync --locked` vs `--frozen`**: Use `--locked` in CI to detect stale lockfiles. `--frozen` skips the check.
- **Cache misses**: Changing `uv.lock` always causes a cache miss. That's correct behavior.
- **Matrix fail-fast**: Set `fail-fast: false` to see results across all platforms even if one fails.
- **Workflow permissions**: PyPI trusted publishing requires `permissions: id-token: write`.
- **Secrets**: Use `${{ secrets.PYPI_TOKEN }}` for token-based auth, or trusted publishing for OIDC.

## Commands

```bash
# Test CI workflow locally (using act)
act -j test                          # Run test job locally
act --list                           # List available jobs
act -s PYPI_TOKEN=xxx                # With secrets

# Validate workflow syntax
uv run python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"
```

## Resources

- GitHub Actions docs: <https://docs.github.com/en/actions>
- setup-uv: <https://github.com/astral-sh/setup-uv>
- PyPI trusted publishing: <https://docs.pypi.org/trusted-publishers/>
- Pre-commit action: <https://github.com/pre-commit/action>
- act (local CI runner): <https://github.com/nektos/act>
