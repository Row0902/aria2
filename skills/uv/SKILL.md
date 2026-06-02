---
name: uv
description: "Trigger: uv, package manager, dependencies, sync, lockfile, add dep, remove dep, venv, Python version, build, publish, pip. Fast Python package and project manager by Astral — replacement for pip + pip-tools + virtualenv + poetry + pyenv."
license: Apache-2.0
metadata:
  author: gentleman-programming
  version: "1.0"
---

## When to Use

- Adding, removing, or updating Python dependencies
- Syncing virtual environments with lockfile (`uv sync`)
- Running scripts within the project environment (`uv run`)
- Managing Python versions (`uv python install`, `uv python pin`)
- Installing and running CLI tools (`uv tool install`, `uvx`)
- Building and publishing packages (`uv build`, `uv publish`)
- Troubleshooting lockfile drift (`uv lock`, `--locked`, `--frozen`)
- Managing dependency groups (dev, test, docs, etc.)
- Replacing pip, pip-tools, virtualenv, poetry, pyenv workflows

## Critical Patterns

### Lockfile is the source of truth

- `uv.lock` is the **canonical lockfile**. Always commit it to version control.
- `uv sync` reads `uv.lock` (not `pyproject.toml`) to install deps.
- After ANY change to `pyproject.toml` deps, run `uv lock` or `uv sync` to update `uv.lock`.
- Without a `uv.lock`, `uv sync` resolves from `pyproject.toml` and generates one.
- Lockfile format is cross-platform — same lockfile works on Linux, macOS, Windows.

### `--locked` vs `--frozen` vs neither

| Flag | Behavior | When to use |
|------|----------|-------------|
| _(none)_ | Updates `uv.lock` if `pyproject.toml` changed, then syncs | Local dev |
| `--locked` | Fails if `uv.lock` is stale vs `pyproject.toml` | CI — ensures lockfile is committed |
| `--frozen` | Skips lockfile update entirely (syncs from existing `uv.lock`) | When lockfile is already correct; faster |

### Dependency Groups

uv uses `[dependency-groups]` in `pyproject.toml`:

```bash
uv add <pkg>                       # → [project.dependencies] (runtime)
uv add --dev <pkg>                 # → [dependency-groups.dev] (deprecated alias)
uv add --group test <pkg>          # → [dependency-groups.test]
uv remove <pkg>                    # Removes from whatever group it's in
```

```toml
[dependency-groups]
dev = ["pytest>=9.0.3", "ruff>=0.15.15"]
test = ["coverage"]
```

Sync modes:

```bash
uv sync                           # Includes default groups (dev is default)
uv sync --no-dev                  # Excludes dev deps (production install)
uv sync --only-dev                # Only dev deps
uv sync --group test              # Include test group too
uv sync --no-default-groups       # Exclude all default groups
uv sync --all-groups              # Include all groups
```

### Python Version Management

uv manages Python versions independently of system Python:

```bash
uv python install 3.14            # Install Python 3.14
uv python install 3.12.8          # Install specific patch version
uv python pin 3.13                # Pin project Python (writes .python-version)
uv python list                    # Show installed and available versions
uv python find                    # Find current Python
uv python uninstall 3.12          # Remove installed version
```

Python installation via `uv python install` uses the `astral-sh/python-build-standalone` project — no compilation, fast downloads.

uv determines which Python to use by checking (in order):
1. `.python-version` file in project root
2. `requires-python` in `pyproject.toml`
3. `.venv` if it already exists
4. Any Python on PATH
5. `UV_MANAGED_PYTHON` env var

### Running Scripts & Commands

```bash
uv run python src/main.py          # Run in project env
uv run pytest -v                   # Run tests with project deps
uv run --with flask flask run      # Run with extra deps (not installed permanently)
uv run --module aria2              # Run as python -m
uv run --no-dev node script.js     # Run production-like (no dev deps)
```

### Tools (uvx)

```bash
uvx ruff check src/                # Run ruff without installing
uvx ty check src/                  # Run ty without installing
uv tool install ty                 # Install globally via uv
uv tool list                       # List globally installed tools
uv tool upgrade --all              # Upgrade all tools
uv tool uninstall ty               # Remove tool
```

Use `uvx` instead of `pipx` or `npx`. Faster, no global state pollution.

### Workspace Support

```toml
# Root pyproject.toml
[tool.uv.workspace]
members = ["packages/*", "libs/*"]
```

- Root `pyproject.toml` has `[tool.uv.workspace]`, no `[project]` (or minimal).
- Each member has its own `pyproject.toml` with full `[project]`.
- `uv sync` at root syncs ALL members into a single virtual env.
- `uv add --package pkg-name <dep>` adds dep to a specific member.
- `uv run --package pkg-name <cmd>` runs in a specific member's context.

### Build & Publish

uv build usa el build backend declarado en `[build-system]` de `pyproject.toml`. Este proyecto usa **hatchling** como backend, que `uv build` invoca automáticamente en un entorno aislado.

#### Build Backend Declaration

```toml
[build-system]
requires = ["hatchling>=1.27,<2"]      # Dependencias del build (aisladas)
build-backend = "hatchling.build"        # PEP 517 backend
```

> ⚠️ Las dependencias de `[build-system]` se instalan en un entorno aislado para el build. No afectan al proyecto ni se mezclan con las dependencias runtime.

#### Build Command Reference

```bash
uv build                          # Build sdist + wheel en dist/
uv build --sdist                  # Source distribution only
uv build --wheel                  # Wheel only
uv build -o custom-dist/          # Output directory
uv build --no-build-logs          # Silent build
uv build --force-pep517           # Force PEP 517 (no fast path)
uv build --clear                  # Limpiar dist/ antes de build
```

#### Build Flow

```
uv build
  → 1. Crea entorno Python aislado
  → 2. Instala hatchling (de [build-system].requires)
  → 3. Construye sdist (archivo .tar.gz en dist/)
  → 4. Construye wheel desde sdist (archivo .whl en dist/)
  → 5. Ejecuta hooks (hatch_build.py: descarga binario)
```

El hook custom de hatchling (`hatch_build.py`) se ejecuta durante el build para descargar el binario aria2c y bundlarlo via `force_include`.

#### Inspeccionar el Wheel

```bash
ls dist/                          # Ver archivos generados
unzip -l dist/aria2-0.1.0-py3-none-any.whl  # Listar contenido
python -m zipfile -l dist/*.whl   # Alternativa
```

#### Build Constraints

Para restringir versiones de dependencias de build:

```bash
uv build --build-constraints constraints.txt
```

O en ambiente:

```bash
export UV_BUILD_CONSTRAINT=constraints.txt
```

#### Publicar a PyPI

```bash
uv publish                        # Publica dist/* a PyPI
uv publish dist/aria2-0.1.0.tar.gz  # Archivo específico

# Con token (PyPI API token)
uv publish --token pypi-xxxxx

# A índice personalizado
uv publish --publish-url https://example.com/pypi/

# Trusted publishing (OIDC — recomendado para GitHub Actions)
uv publish --trusted-publishing always

# Dry run
uv publish --dry-run
```

#### Trusted Publishing (OIDC)

Recomendado para CI. No necesita token — GitHub Actions se autentica con OIDC:

```yaml
# .github/workflows/release.yml
jobs:
  publish:
    permissions:
      id-token: write               # ← Necesario para OIDC
    environment: pypi
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - run: uv sync --locked
      - run: uv build
      - run: uv publish
```

#### Entornos de Build

Variables de entorno clave:

| Variable | Propósito |
|---|---|
| `UV_BUILD_CONSTRAINT` | Restricciones de build |
| `UV_PUBLISH_TOKEN` | Token PyPI |
| `UV_PUBLISH_URL` | URL de subida |
| `UV_PUBLISH_USERNAME` | Usuario para índice |
| `UV_PUBLISH_PASSWORD` | Password para índice |
| `UV_PUBLISH_INDEX` | Nombre del índice configurado |

#### CI Workflow Completo

```yaml
name: Release

on:
  release:
    types: [published]

jobs:
  build-and-publish:
    runs-on: ubuntu-24.04
    permissions:
      id-token: write
    environment: pypi
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
        with:
          enable-cache: true
      - run: uv sync --locked
      - run: uv build
      - run: uv publish
```

### Script Support (PEP 723)

uv runs standalone scripts with inline metadata:

```python
# /// script
# requires-python = ">=3.14"
# dependencies = [
#   "httpx",
#   "rich",
# ]
# ///
import httpx
print("Hello")
```

```bash
uv run script.py                  # Auto-creates env with deps
uv add --script script.py httpx   # Add dep to script
uv lock --script script.py        # Lock script deps
```

### Cache Management

```bash
uv cache clean                    # Nuke entire cache
uv cache prune                    # Remove stale entries only
uv cache prune --ci               # More aggressive CI cleanup
```

Cache is never required for correctness. Deleting it only slows the next sync.

### Environment Variables

| Variable | Effect |
|---|---|
| `UV_NO_CACHE=1` | Skip cache entirely |
| `UV_NO_DEV=1` | Exclude dev deps |
| `UV_FROZEN=1` | Don't update lockfile |
| `UV_LOCKED=1` | Fail if lockfile is stale |
| `UV_MANAGED_PYTHON=never` | Don't auto-download Python |
| `UV_SYSTEM_PYTHON=1` | Use system Python instead of venv |
| `UV_PYTHON_DOWNLOADS=never` | Disable automatic Python downloads |
| `UV_PYTHON=<version>` | Set Python version |
| `UV_EXTRA_INDEX_URL` | Additional package index |
| `UV_INDEX_URL` | Default package index |
| `UV_CACHE_DIR` | Custom cache location |
| `UV_TOOL_DIR` | Custom tool install location |

### Common Pitfalls

- **Lockfile drift in CI**: Always use `uv sync --locked` in CI. If it fails, run `uv lock` locally and commit the updated `uv.lock`.
- **Missing `.python-version`**: Without it, uv uses the first Python on PATH. Pin explicitly with `uv python pin`.
- **`uv add` modifies `pyproject.toml` AND `uv.lock`**: Always review both files after adding deps.
- **Dev deps in wrong group**: Double-check `--dev` flag. Runtime dep in dev group → import error in production.
- **`uv sync` with stale `.python-version`**: If version not installed, sync fails. Fix: `uv python install` the version.
- **`uv.lock` merge conflicts**: `uv lock` regenerates from `pyproject.toml`. After resolving conflict, run `uv lock` to produce a clean lockfile.
- **Different Python patch versions**: uv's standalone builds may not have every patch version available for every platform.

## Code Examples

### Full project workflow
```bash
# Create
uv init my-project
cd my-project

# Add deps
uv add fastapi httpx pydantic
uv add --dev pytest pytest-cov ruff ty

# Sync & verify
uv sync
uv run pytest

# Build
uv build

# Publish
uv publish
```

### CI workflow
```yaml
steps:
  - uses: actions/checkout@v4
  - uses: astral-sh/setup-uv@v5
    with:
      enable-cache: true
      cache-dependency-glob: "uv.lock"
  - run: uv sync --locked
  - run: uv run ruff check src/
  - run: uv run ty check src/
  - run: uv run pytest -v
```

### Production install
```yaml
steps:
  - uses: astral-sh/setup-uv@v5
  - run: uv sync --no-dev --locked --frozen
```

### Troubleshooting lockfile
```bash
# Lockfile out of date
uv lock                              # Force regenerate from pyproject.toml

# Lockfile merge conflict
git mergetool                        # Resolve pyproject.toml
uv lock                              # Regenerate clean lockfile

# Package resolution failure
uv lock --upgrade-package <pkg>      # Re-resolve a single package

# Full refresh
uv cache clean && uv sync            # Start completely fresh

# Check lockfile health
uv lock --check                      # Verify lockfile is up to date
```

## Commands

```bash
# ── Project ─────────────────────────────────────────
uv init <name>                     # Create new project
uv add <pkg>                       # Add runtime dependency
uv add --dev <pkg>                 # Add dev dependency
uv add --group <name> <pkg>        # Add to named group
uv remove <pkg>                    # Remove dependency
uv sync                            # Sync env with lockfile
uv sync --locked                   # Sync (fail if stale)
uv sync --frozen                   # Sync (skip lockfile update)
uv lock                            # Regenerate lockfile
uv lock --check                    # Verify lockfile is up to date
uv export --format requirements-txt > requirements.txt

# ── Running ─────────────────────────────────────────
uv run <cmd>                       # Run in project env
uv run --with <pkg> <cmd>          # Run with extra packages
uv run --module <mod>              # Run as python -m
uvx <pkg>                          # Run tool without installing
uv run <script.py>                 # Run PEP 723 script

# ── Python versions ─────────────────────────────────
uv python install <version>        # Install Python version
uv python list                     # List installed versions
uv python pin <version>            # Pin project Python (writes .python-version)
uv python find                     # Find current Python
uv python uninstall <version>      # Remove version

# ── Tools ───────────────────────────────────────────
uv tool install <pkg>              # Install globally
uv tool run <pkg> [args]           # Alias: uvx
uv tool list                       # List installed tools
uv tool upgrade --all              # Upgrade all tools
uv tool uninstall <pkg>            # Remove tool

# ── Cache ───────────────────────────────────────────
uv cache clean                     # Clear entire cache
uv cache prune                     # Remove stale entries

# ── Build / Publish ─────────────────────────────────
uv build                           # Build sdist + wheel
uv publish                         # Publish to PyPI

# ── Info ────────────────────────────────────────────
uv --help                          # General help
uv <command> --help                # Command help
uv version                         # Show version
```

## Resources

- Repository: <https://github.com/astral-sh/uv>
- Documentation: <https://docs.astral.sh/uv/>
- GitHub Action: <https://github.com/astral-sh/setup-uv>
- Guides: <https://docs.astral.sh/uv/guides/>
- CLI reference: <https://docs.astral.sh/uv/reference/cli/>
- Configuration: <https://docs.astral.sh/uv/configuration/>
- Scripts (PEP 723): <https://docs.astral.sh/uv/guides/scripts/>
- Workspaces: <https://docs.astral.sh/uv/guides/workspaces/>
