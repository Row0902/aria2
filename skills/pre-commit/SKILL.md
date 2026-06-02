---
name: pre-commit
description: "Trigger: pre-commit, git hooks, pre-commit hooks, lint on commit, commit hooks. Framework for managing and maintaining multi-language git hooks."
license: Apache-2.0
metadata:
  author: gentleman-programming
  version: "1.0"
---

## When to Use

- Setting up automated linting/formatting before every git commit
- Enforcing code quality checks across a team
- Running type checkers, linters, formatters, and security scans on staged files
- Automating fix-on-commit for trailing whitespace, EOF newlines, etc.
- Running CI-style checks locally before pushing
- Ensuring no commit bypasses project conventions

## Critical Patterns

### Configuration file: `.pre-commit-config.yaml`

pre-commit reads configuration from `.pre-commit-config.yaml` at the project root. It defines repos, hooks, and top-level options.

### Minimal Setup

```bash
# Install pre-commit (via uv)
uv tool install pre-commit
# or: uvx pre-commit

# Install git hooks in current repo
pre-commit install

# Run against all files (first run — slow, downloads hooks)
pre-commit run --all-files
```

### Basic Config

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-toml
      - id: check-added-large-files
      - id: check-merge-conflict
```

### Full Config with Python tools

```yaml
# .pre-commit-config.yaml
repos:
  # Built-in file checks
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-toml
      - id: check-json
      - id: check-added-large-files
        args: [--maxkb=500]
      - id: check-merge-conflict
      - id: detect-private-key
      - id: mixed-line-ending
        args: [--fix=lf]

  # Ruff lint + format (Astral)
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.15.15
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  # ty type checker (Astral)
  - repo: https://github.com/astral-sh/ty-pre-commit
    rev: v0.0.42
    hooks:
      - id: ty
        args: [--]

  # Local hooks for project-specific checks
  - repo: local
    hooks:
      - id: pytest
        name: pytest
        entry: uv run pytest
        language: system
        types: [python]
        pass_filenames: false
        always_run: true
        stages: [pre-push]
```

### Config Top-Level Options

| Option | Description |
|---|---|
| `repos` | List of hook repositories (required) |
| `default_install_hook_types` | Hook types to install by default, e.g. `[pre-commit, pre-push]` |
| `default_language_version` | Language → version mapping, e.g. `python: python3.14` |
| `default_stages` | Default stages for all hooks, e.g. `[pre-commit]` |
| `files` | Global include pattern |
| `exclude` | Global exclude pattern |
| `fail_fast` | Stop on first hook failure |
| `minimum_pre_commit_version` | Minimum required pre-commit version |

### Hook Options (per hook)

| Option | Description |
|---|---|
| `id` | Hook identifier from the repo (required) |
| `alias` | Alternative name for the hook |
| `name` | Display name (overrides default) |
| `args` | List of CLI arguments |
| `files` | Include pattern for files to check |
| `exclude` | Exclude pattern |
| `types` | File type filters, e.g. `[python]` |
| `types_or` | OR-combined type filters |
| `language_version` | Override language version for this hook |
| `additional_dependencies` | Extra pip dependencies |
| `stages` | Git hook stages: `pre-commit`, `pre-push`, `pre-merge-commit`, `manual`, `post-checkout`, `post-commit`, `post-merge`, `post-rewrite` |
| `always_run` | Run even if no matching files changed |
| `verbose` | Always show output |
| `log_file` | Write output to a file |
| `pass_filenames` | Whether to pass filenames to the entry (default true) |

### Common Stages

| Stage | When it runs |
|---|---|
| `pre-commit` | Before each commit (default) |
| `pre-push` | Before each push |
| `pre-merge-commit` | Before merge commit |
| `manual` | Only when explicitly invoked with `pre-commit run --hook-stage manual` |
| `post-checkout` | After git checkout |
| `commit-msg` | On commit message |
| `post-commit` | After commit |
| `post-merge` | After merge |

### Running Hooks

```bash
pre-commit run                  # Run all hooks on staged files
pre-commit run ruff             # Run a specific hook
pre-commit run --all-files      # Run on all files (not just staged)
pre-commit run --files src/main.py  # Run on specific files
pre-commit run --hook-stage pre-push  # Run pre-push hooks
pre-commit run --verbose        # Show output even for passing hooks

# Skip hooks on commit
git commit --no-verify          # Skip all hooks
SKIP=ruff,ruff-format git commit  # Skip specific hooks
```

### Local Hooks

Define hooks from the local repo without external dependencies:

```yaml
- repo: local
  hooks:
    - id: my-check
      name: My Custom Check
      entry: python scripts/check.py
      language: python
      types: [python]
      additional_dependencies: []  # pip deps for the hook env
```

Language options for local hooks: `python`, `system`, `script`, `docker`, `pygrep`, `node`, `ruby`, `rust`, `swift`.

- `language: system` — runs the entry directly in the system PATH
- `language: python` — creates an isolated venv and `pip install`s the hook
- `language: script` — runs as a shell script
- `language: pygrep` — runs a Python regex pattern against file contents

### CI Integration

```yaml
# GitHub Actions — run hooks in CI
steps:
  - uses: actions/checkout@v4
  - uses: actions/setup-python@v5
  - run: pip install pre-commit
  - run: pre-commit run --all-files --show-diff-on-failure
  # Or use the pre-commit action
  - uses: pre-commit/action@v3.0.1
```

### Updating Hooks

```bash
pre-commit autoupdate            # Update all hooks to latest versions
pre-commit autoupdate --repo https://github.com/astral-sh/ruff-pre-commit  # Single repo
pre-commit autoupdate --freeze   # Pin to commit SHAs instead of tags
```

### Managing pre-commit

```bash
pre-commit install               # Install git hooks
pre-commit install --hook-type pre-push  # Install additional hook type
pre-commit install-hooks         # Install hook environments (download/install)
pre-commit clean                 # Clean cached hook environments
pre-commit gc                    # Garbage collect unused environments
pre-commit uninstall             # Remove git hooks
pre-commit validate-config       # Validate .pre-commit-config.yaml
pre-commit validate-manifest     # Validate .pre-commit-hooks.yaml
pre-commit sample-config         # Generate sample config
pre-commit init-templatedir      # Use as a git template directory
```

### Cache Management

```
~/.cache/pre-commit/             # Linux cache directory
```

- Cache stores hook repositories and environments
- `pre-commit clean` removes stale environments
- CI caching: key on `hashFiles('.pre-commit-config.yaml')` + Python version

### Common Pitfalls

- **First run is slow**: pre-commit clones repos and creates environments on first run. Subsequent runs are fast.
- **`git commit --no-verify` is available to anyone**: pre-commit is a guard, not a security barrier. CI should enforce the same checks.
- **Hooks only run on staged files**: `ruff` or `ty` only see staged changes. Use `--all-files` in CI.
- **`pass_filenames: false`**: Some hooks (like formatters) expect filenames; others (like linters with their own discovery) don't. Set appropriately.
- **`language: system` hooks**: These use whatever is on PATH. Not reproducible across machines unless tooling is managed (e.g., via uv).
- **Merge conflicts with `.pre-commit-config.yaml`**: Keep `rev` tags explicit. Use `pre-commit autoupdate` to bump versions.

## Code Examples

### Config del proyecto (`.pre-commit-config.yaml`)

Este proyecto usa `pre-commit` con ruff, ty, y pytest:

```yaml
# .pre-commit-config.yaml — aria2 Python SDK
default_language_version:
  python: python3.14

repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-toml
      - id: check-added-large-files
        args: [--maxkb=500]
      - id: check-merge-conflict
      - id: detect-private-key

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.15.15
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/astral-sh/ty-pre-commit
    rev: v0.0.42
    hooks:
      - id: ty
        args: [--]

  - repo: local
    hooks:
      - id: pytest
        name: pytest
        entry: uv run pytest -q
        language: system
        types: [python]
        pass_filenames: false
        always_run: true
        stages: [pre-push]
```

### Instalación en este proyecto

```bash
uv tool install pre-commit
pre-commit install
pre-commit install --hook-type pre-push    # Para el hook pytest
pre-commit run --all-files                 # Verificar que funciona
pre-commit run --hook-stage pre-push       # Probar el hook pre-push
```

### Python project with Astral tools (genérico)
```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-toml
      - id: check-added-large-files
      - id: check-merge-conflict

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.15.15
    hooks:
      - id: ruff
        args: [--fix, --select, I]
      - id: ruff-format

  - repo: https://github.com/astral-sh/ty-pre-commit
    rev: v0.0.42
    hooks:
      - id: ty

  - repo: local
    hooks:
      - id: pytest
        name: pytest
        entry: uv run pytest
        language: system
        types: [python]
        pass_filenames: false
        always_run: true
        stages: [pre-push]
```

### Python project without uv
```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml

  - repo: https://github.com/psf/black
    rev: 24.10.0
    hooks:
      - id: black

  - repo: https://github.com/pycqa/isort
    rev: 5.13.2
    hooks:
      - id: isort

  - repo: https://github.com/pycqa/flake8
    rev: 7.1.1
    hooks:
      - id: flake8
```

### CI workflow
```yaml
steps:
  - uses: actions/checkout@v4
  - uses: actions/setup-python@v5
    with:
      python-version: "3.14"
  - uses: pre-commit/action@v3.0.1
```

## Commands

```bash
# ── Setup ─────────────────────────────────────────────
uv tool install pre-commit       # Install via uv
pre-commit install                # Install git hooks
pre-commit install --hook-type pre-push  # Install pre-push hooks too
pre-commit install-hooks          # Download/install hook environments

# ── Run ───────────────────────────────────────────────
pre-commit run                    # Run on staged files
pre-commit run --all-files        # Run on all files
pre-commit run <hook-id>          # Run specific hook
pre-commit run --hook-stage pre-push  # Run for specific stage
pre-commit run --files path/to/file  # Run on specific files
pre-commit run --verbose          # Show all output

# ── Maintenance ───────────────────────────────────────
pre-commit autoupdate             # Update hooks to latest
pre-commit clean                  # Clean cached environments
pre-commit gc                     # Garbage collect unused envs

# ── Validation ────────────────────────────────────────
pre-commit validate-config        # Check .pre-commit-config.yaml
pre-commit validate-manifest      # Check .pre-commit-hooks.yaml
pre-commit sample-config          # Generate sample config

# ── Uninstall ─────────────────────────────────────────
pre-commit uninstall              # Remove hooks
pre-commit uninstall --hook-type pre-push  # Remove specific type

# ── Info ──────────────────────────────────────────────
pre-commit --version              # Show version
pre-commit --help                 # Full help
```

## Resources

- Documentation: <https://pre-commit.com/>
- Hooks: <https://pre-commit.com/hooks.html>
- GitHub: <https://github.com/pre-commit/pre-commit>
- pre-commit hooks (official): <https://github.com/pre-commit/pre-commit-hooks>
- Ruff pre-commit: <https://github.com/astral-sh/ruff-pre-commit>
- ty pre-commit: <https://github.com/astral-sh/ty-pre-commit>
- Pre-commit action (CI): <https://github.com/pre-commit/action>
