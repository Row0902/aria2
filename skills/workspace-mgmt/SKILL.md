---
name: workspace-mgmt
description: "Trigger: workspace, monorepo, multi-package, uv workspace, shared packages, packages/\", apps/, libs/, workspace member, cross-package dependency. Gestión de monorepos Python con uv workspaces — estructura, configuración, dependencias cruzadas, CI/CD, Docker."
license: Apache-2.0
metadata:
  author: gentleman-programming
  version: "1.0"
---

## When to Use

- Organizar múltiples paquetes Python en un solo repositorio (monorepo)
- Compartir librerías entre varios proyectos (API, worker, CLI, shared libs)
- Gestionar dependencias cruzadas entre paquetes con un solo lockfile
- Configurar workspaces uv desde cero o migrar a monorepo
- Publicar paquetes individuales desde un monorepo a PyPI
- Construir imágenes Docker para servicios dentro del monorepo

## Core Concepts

Un **workspace** (concepto inspirado en Cargo) es una colección de uno o más paquetes, llamados *workspace members*, que se gestionan juntos:

- Cada miembro tiene su propio `pyproject.toml`
- **Comparten un solo `uv.lock`** → dependencias consistentes en todo el repo
- Compraten un solo `.venv` en la raíz
- Las dependencias entre miembros se resuelven localmente (editable mode)
- `uv run`, `uv sync`, `uv add` pueden targetear un miembro específico con `--package`

## Project Structure

### Estándar recomendado

```
monorepo/
├── apps/                          # Aplicaciones (entry points, no importables)
│   └── api/
│       ├── pyproject.toml
│       ├── src/
│       │   └── api/
│       │       ├── __init__.py
│       │       └── main.py
│       └── tests/
│           └── test_api.py
├── packages/                      # Librerías compartidas (importables, sin entry points)
│   ├── shared-lib/
│   │   ├── pyproject.toml
│   │   └── src/
│   │       └── shared_lib/
│   │           └── __init__.py
│   └── cli/
│       ├── pyproject.toml
│       └── src/
│           └── cli/
│               ├── __init__.py
│               └── __main__.py
├── pyproject.toml                # Workspace root (contenedor)
├── uv.lock                       # Lockfile único
├── .venv/                        # Virtual env compartido
├── README.md
└── .gitignore
```

### Convenciones

| Directorio | Propósito | `uv init` flag | Entry points |
|-----------|-----------|----------------|--------------|
| `apps/*` | Aplicaciones (FastAPI, worker, CLI runner) | `--app` | Sí |
| `packages/*` | Librerías importables (shared utils, models, SDKs) | `--lib` | No |
| `services/*` | Microservicios (alternativa a apps/) | `--app` | Sí |
| Root | Workspace container (virtual) | `uv init` | No |

## Setup Inicial

### 1. Crear el workspace root

```bash
mkdir monorepo && cd monorepo
uv init
```

### 2. Hacerlo virtual workspace (opcional)

Si el root no tiene código propio, eliminar `[project]` y dejar solo:

```toml
[tool.uv.workspace]
members = ["packages/*", "apps/*"]
```

Un *virtual workspace* no puede tener dependencias propias ni publicarse. Todo vive en los miembros.

### 3. Agregar miembros

```bash
# Librería compartida
uv init --lib packages/shared-lib

# Aplicación
uv init --app apps/api-service

# CLI tool
uv init --app packages/cli
```

### 4. Configurar dependencias entre miembros

```bash
# api-service depende de shared-lib
uv add --package api-service shared-lib
```

Esto agrega en `apps/api-service/pyproject.toml`:

```toml
[project]
dependencies = ["shared-lib"]

[tool.uv.sources]
shared-lib = { workspace = true }
```

### 5. Lock y sync

```bash
uv lock                          # Resuelve dependencias de todos los miembros
uv sync --all-packages           # Sincroniza el .venv compartido
```

## Configuración Detallada

### `[tool.uv.workspace]` — Definición de miembros

```toml
[tool.uv.workspace]
members = [
    "packages/*",       # Glob: todos los paquetes bajo packages/
    "apps/*",           # Glob: todas las apps bajo apps/
]
exclude = [
    "packages/legacy",  # Excluir paquetes específicos
    "packages/template*",  # Glob de exclusión
]
```

Cada directorio incluido por `members` DEBE contener un `pyproject.toml`.

### `[tool.uv.sources]` — Fuentes de dependencias

```toml
# En el root pyproject.toml (aplica a TODOS los miembros)
[tool.uv.sources]
shared-lib = { workspace = true }
my-internal-pkg = { git = "https://github.com/org/my-internal-pkg.git", tag = "v0.1.0" }
private-lib = { url = "https://artifacts.example.com/private-lib-1.0.tar.gz" }
```

Las fuentes del root aplican a todos los miembros por defecto. Un miembro puede sobrescribir declarando su propio `[tool.uv.sources]`.

### Herencia de fuentes

```toml
# Root pyproject.toml — tqdm desde GitHub para TODOS los miembros
[tool.uv.sources]
shared-lib = { workspace = true }
tqdm = { git = "https://github.com/tqdm/tqdm" }

# packages/some-app/pyproject.toml — Sobrescribe tqdm solo para this member
[tool.uv.sources]
tqdm = { path = "./vendor/tqdm" }
```

## Comandos Esenciales

### Por miembro vs global

```bash
# Operan en el root por defecto
uv sync                          # Sync del root (poco útil si es virtual workspace)
uv run python -c "..."           # Corre en el root

# Operan en un miembro específico
uv sync --package api-service    # Sync solo de api-service + sus dependencias
uv run --package api-service pytest
uv run --package cli python -m cli
uv add --package api-service httpx
uv add --package shared-lib --group dev pytest
uv remove --package api-service requests
uv build --package shared-lib

# Operan en TODOS los miembros
uv sync --all-packages           # Útil después de clone
uv build --all-packages          # Buildear todos los paquetes
uv run --all-packages pytest     # Correr tests de todos
uv lock                          # Resolver dependencias globales
```

### Gestión de dependencias

```bash
# Agregar dependencia externa a un miembro
uv add --package api-service fastapi uvicorn

# Agregar dependencia de workspace
uv add --package api-service shared-lib

# Agregar dev dependency a un miembro
uv add --package api-service --group dev pytest pytest-cov

# Agregar dependencia al root (si no es virtual workspace)
uv add --group dev ruff ty

# Sincronizar solo un miembro (más rápido que --all-packages)
uv sync --package api-service
```

## Python Version Management

uv calcula la **intersección** de todos los `requires-python` de los miembros:

```toml
# packages/shared-lib/pyproject.toml
requires-python = ">=3.10"

# apps/api-service/pyproject.toml
requires-python = ">=3.12"

# Resultado: el workspace resuelve contra >=3.12
```

⚠️ Si un miembro tiene un `requires-python` muy restrictivo, ajusta el rango de todo el workspace. Considera mover ese paquete fuera del workspace si es problemático.

## CI/CD para Monorepos

### GitHub Actions — Lint y Test

```yaml
name: CI
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - run: uv sync --all-packages --locked
      - run: uv run --all-packages pytest
      - run: uv run ruff check .
      - run: uv run ruff format --check .
```

### Publicación selectiva a PyPI

```yaml
name: Publish
on:
  release:
    types: [published]
jobs:
  publish:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - run: uv sync --all-packages --locked
      - run: uv build --package shared-lib
      - run: uv publish --package shared-lib
```

### CI con matrix por miembro

```yaml
name: CI
on: [push, pull_request]
jobs:
  test:
    strategy:
      matrix:
        package: [api-service, shared-lib, cli]
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - run: uv sync --package ${{ matrix.package }} --locked
      - run: uv run --package ${{ matrix.package }} pytest
```

## Type Checking con ty en Workspaces

### Configuración centralizada en root

En un workspace uv, **ty** (el type checker de Astral) se configura desde el root `pyproject.toml` porque:
- Todos los miembros comparten el mismo `.venv`
- Las dependencias cruzadas se resuelven por editable installs
- No hay necesidad de configuraciones jerárquicas

```toml
# Root pyproject.toml
[tool.ty.environment]
python-version = "3.14"
python-platform = "linux"
root = [
  "packages/aria2-sdk/src",
  "packages/aria2-bin/src",
  "apps/cli/src",
]

[tool.ty.src]
include = [
  "packages/aria2-sdk/src",
  "packages/aria2-bin/src",
  "apps/cli/src",
  "tests",
]
```

`environment.root` le dice a ty dónde buscar módulos first-party. En workspace, todos los `src/` de los miembros deben estar listados.

### Per-directory overrides para tests

```toml
[[tool.ty.overrides]]
include = ["tests/**/*.py"]
[tool.ty.overrides.rules]
invalid-argument-type = "warn"       # Tests pueden ser menos estrictos
unused-awaitable = "warn"
```

### Cómo ty resuelve imports en workspace

Cuando `uv sync --all-packages` instala los miembros en editable mode, cada paquete queda disponible en el `.venv` compartido. ty los encuentra automáticamente porque:
1. El `.venv` está en la raíz del workspace
2. ty detecta `.venv/` automáticamente
3. Los editable installs generan `.pth` files que Python/ty usan para resolver imports

Para verificar que ty encuentra todo:

```bash
uv run ty check --show-settings  # Muestra la configuración efectiva
uv run ty check -vv              # Modo verbose: muestra qué archivos chequea
```

### Comandos útiles

```bash
# Checkar todo el workspace
uv run ty check packages/ apps/ tests/

# Checkar solo un miembro
uv run ty check packages/aria2-sdk/src

# Con --project (útil para LSP)
uv run ty check --project packages/aria2-sdk

# Omitir tests
uv run ty check packages/ apps/
```

### Limitaciones conocidas

- **ty LSP no soporta proyectos anidados completamente** ([#2410](https://github.com/astral-sh/ty/issues/2410)). La configuración del workspace root es la que se usa para todos los archivos.
- **Workaround VS Code**: usar multi-root workspace con `.code-workspace` apuntando a cada miembro.
- **Workaround CLI**: `ty check --project <member>` para checkar un miembro con su propia configuración si tiene `[tool.ty]` propio.
- Para la mayoría de los workspaces uv, una sola config en el root es suficiente.

### Ejemplo: configuración por miembro (alternativa)

Si necesitás reglas diferentes por miembro, agregá `[tool.ty]` en cada `pyproject.toml` del miembro. ty usará la configuración más cercana al archivo que está chequeando:

```toml
# packages/api/pyproject.toml
[tool.ty.rules]
unused-awaitable = "error"  # API strict
```

Pero esto **no** hereda la config del root — tenés que repetirla en cada miembro. No recomendado a menos que los miembros tengan necesidades muy diferentes.

## Docker para Monorepos

### Estrategia: build desde raíz

```dockerfile
FROM python:3.12-slim

# Copiar uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

# Copiar lockfile y pyproject (layer caching)
COPY pyproject.toml uv.lock ./
COPY packages/ ./packages/

# Instalar dependencias + miembro específico
RUN uv sync --frozen --no-dev --package api-service

# Copiar solo el código del servicio
COPY apps/api-service ./apps/api-service/

EXPOSE 8000
WORKDIR /app/apps/api-service
ENTRYPOINT ["uv", "run", "uvicorn", "api.main:app", "--host", "0.0.0.0"]
```

### Estrategia: build multi-stage con uv

```dockerfile
FROM ghcr.io/astral-sh/uv:python3.12-alpine AS builder

WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY packages/ ./packages/
COPY apps/api-service ./apps/api-service/

RUN uv sync --frozen --no-dev --package api-service

FROM python:3.12-alpine
WORKDIR /app
COPY --from=builder /app /app
ENV PATH="/app/.venv/bin:$PATH"
ENTRYPOINT ["uvicorn", "api.main:app", "--host", "0.0.0.0"]
```

## VS Code / Pylance en Monorepos

### Opción 1: Workspace virtual env compartido

```bash
uv sync --all-packages
code .
# Seleccionar .venv/ de la raíz como intérprete Python
```

### Opción 2: Pylance execution environments

```toml
# pyproject.toml (root)
[tool.pyright]
include = ["apps", "packages"]

[[tool.pyright.executionEnvironments]]
root = "apps/api-service"
extraPaths = ["../../packages/shared-lib/src"]
pythonVersion = "3.12"

[[tool.pyright.executionEnvironments]]
root = "packages/shared-lib"
pythonVersion = "3.10"
```

### Opción 3: Multi-root workspace (.code-workspace)

```json
{
  "folders": [
    { "path": "apps/api-service" },
    { "path": "packages/shared-lib" }
  ],
  "settings": {
    "python.analysis.diagnosticMode": "openFilesOnly"
  }
}
```

## Publicación de Paquetes

### Publicación individual

```bash
# Buildear solo un paquete
uv build --package shared-lib

# Publicar
uv publish --package shared-lib

# O desde dist/
uv publish dist/shared_lib-*.tar.gz
```

### Versionado independiente

Cada miembro tiene su propia versión en `pyproject.toml`. No hay restricción de versionado sincronizado — cada paquete se versiona independientemente.

### Estrategias de versionado

| Estrategia | Descripción | Cuándo usarla |
|-----------|-------------|---------------|
| **Independiente** | Cada paquete tiene su propia versión | Equipos grandes, releases frecuentes |
| **Sincronizado** | Todos los paquetes usan la misma versión | Proyecto pequeño, releases coordinadas |
| **Release Please** | Release Please + conventional commits | Automatización total |

## Buenas Prácticas

### 1. Virtual workspace para roots sin código

Si el root solo organiza paquetes, elimina `[project]`. Mantiene el root limpio y evita dependencias fantasma.

### 2. Usa `uv sync --all-packages` en CI

Garantiza que todos los miembros están instalados antes de correr tests o lint.

### 3. Dependencias compartidas en el root

```toml
# Root pyproject.toml (si NO es virtual workspace)
[dependency-groups]
dev = ["ruff", "pytest", "ty"]
```

### 4. Build backend: uv_build o hatchling

Para workspaces uv, `uv_build` tiene mejor integración:

```toml
[build-system]
requires = ["uv_build>=0.11.18,<0.12"]
build-backend = "uv_build"
```

`hatchling` también funciona, pero `uv_build` es más rápido y tiene menos edge cases con editable installs.

### 5. `.gitignore` para monorepo

```gitignore
.venv/
__pycache__/
*.pyc
dist/
*.egg-info/
.coverage
coverage.xml
.ruff_cache/
.mypy_cache/
.pytest_cache/
```

### 6. Nombres de paquetes con namespace consistente

```txt
shared-lib       → import shared_lib
api-service      → import api_service
org-models       → import org.models
org-auth         → import org.auth
```

## Cuándo NO usar workspaces

- **Versiones conflictivas**: Si `app-a` necesita `requests==2.28` y `app-b` necesita `requests==2.31`, el resolver falla. Usa path dependencies con entornos separados.
- **Aislamiento estricto**: Workspace = un `.venv`. Si necesitas entornos aislados por miembro, no es workspace.
- **Límites de importación**: Python no tiene aislamiento de dependencias. Un miembro puede importar cualquier cosa instalada en `.venv`, incluyendo dependencias de otros miembros.
- **Python versions incompatibles**: Si un miembro requiere >=3.10 y otro >=3.13, el workspace resuelve >=3.13 (intersección).

## Alternativa: Path Dependencies (sin workspace)

Para casos donde workspace es demasiado, usa path dependencies:

```toml
[project]
dependencies = ["shared-lib"]

[tool.uv.sources]
shared-lib = { path = "packages/shared-lib" }
```

Esto permite proyectos independientes con carpetas separadas, pero sin lockfile compartido ni `uv run --package`.

## Troubleshooting

### `uv sync` falla por conflicto de dependencias

```bash
# Ver el error completo
uv lock --verbose

# Aislar el miembro problemático
uv sync --package problematic-pkg

# Si es conflicto real, considera path dependency en vez de workspace
```

### Editable installs no funcionan con Pylance

Verifica que el build backend genere `.pth` files:

```bash
ls .venv/lib/python*/site-packages/__editable__*.pth
```

| Backend | Editable install | Funciona con Pylance |
|---------|-----------------|---------------------|
| `uv_build` | Path-based `.pth` | ✅ Sí |
| `hatchling` | Path-based `.pth` | ✅ Sí (default) |
| `setuptools` | Import hooks | ❌ No (usar `editable_mode=compat`) |

Para setuptools:
```toml
[tool.uv]
config-settings = { editable_mode = "compat" }
```

### `uv run --package` falla

```bash
# Verificar que el paquete es miembro del workspace
uv tree --package api-service

# Verificar pyproject.toml del miembro
cat apps/api-service/pyproject.toml

# Re-sync
uv sync --package api-service
```

### Miembro nuevo no aparece

```bash
# Si usas globs ("packages/*"), solo asegúrate de que tenga pyproject.toml
# Si usas lista explícita, agrega el path
uv lock  # Rediscover workspace members
```

## Commands Cheatsheet

```bash
uv sync --all-packages              # Instalar TODO
uv sync --package api-service       # Instalar solo un miembro
uv run --package api-service pytest # Tests de un miembro
uv run --all-packages pytest        # Tests de todos
uv add --package api-service httpx  # Agregar dep a miembro
uv build --package shared-lib       # Build de un miembro
uv publish --package shared-lib     # Publicar un miembro
uv lock                             # Resolver workspace completo
uv tree --package api-service       # Árbol de dependencias de miembro
```

## Resources

- uv workspaces docs: <https://docs.astral.sh/uv/concepts/projects/workspaces/>
- uv config: <https://docs.astral.sh/uv/concepts/projects/config/>
- uv layout: <https://docs.astral.sh/uv/concepts/projects/layout/>
- Pylance monorepo guide: <https://github.com/microsoft/pylance-release/blob/main/docs/howto/monorepo-setup.md>
- Ejemplo real: <https://github.com/bstaber/uv-monorepo-example>
- Template: <https://github.com/clintonsteiner/python-monorepo-template>
