---
name: hatchling
description: "Trigger: hatchling, build backend, PEP 517, build system, pyproject.toml build, build hook, custom build. Hatchling build backend library — PEP 517 build backend used by uv build, with support for custom build hooks."
license: Apache-2.0
metadata:
  author: gentleman-programming
  version: "1.0"
---

## When to Use

- As the PEP 517 build backend declared in `[build-system]` in `pyproject.toml`
- Defining which Python packages to include in the wheel
- Setting include/exclude patterns for sdist and wheel
- Creating custom build hooks (binary download, code generation, asset bundling)
- Managing `force_include` for files outside the package tree

## Critical Patterns

### Role: Build Backend, NOT CLI

```
hatchling ≠ hatch CLI
```

| Tool | Role | Usage |
|---|---|---|
| **hatchling** | Build backend library | Solo en `[build-system] requires` — lo usa `uv build` internamente |
| **hatch** | CLI tool (opcional) | Proyectos que usan hatch para version/test — **este proyecto usa uv** |

**hatchling se declara en pyproject.toml:**

```toml
[build-system]
requires = ["hatchling>=1.27,<2"]
build-backend = "hatchling.build"
```

> ⚠️ hatchling **no es una dependencia del proyecto**. No va en `[project.dependencies]` ni en `[dependency-groups]`. Solo existe en el entorno de build aislado que crea `uv build`.

### Build Flow with uv

```
uv build
  → crea entorno aislado
  → instala hatchling (desde [build-system].requires)
  → hatchling.build construye sdist + wheel
  → uv escribe los archivos en dist/
```

### Wheel Configuration

Define qué paquetes Python incluir en la rueda:

```toml
[tool.hatch.build.targets.wheel]
packages = [
  "src/aria2",
  "src/aria2/bin",
  "src/aria2/client",
  "src/aria2/errors",
  "src/aria2/models",
  "src/aria2/rpc",
  "src/aria2/types",
]
```

Cada directorio debe tener `__init__.py`. Si usás `packages = ["src/aria2"]`, hatchling descubre automáticamente todos los sub-paquetes.

### Include/Exclude Patterns

```toml
[tool.hatch.build]
include = ["/src", "/aria2_bin/**"]       # Incluir src/ y binarios
exclude = ["tests/**", "**/__pycache__/**"]  # Excluir tests y caches
```

Reglas:
- `/src` → raíz del proyecto (leading `/`)
- `aria2_bin/**` → cualquier profundidad
- `**/__pycache__/**` → global

### Sdist Exclusion

```toml
[tool.hatch.build.targets.sdist]
exclude = ["/aria2_bin/**"]               # Binarios no van en source dist
```

### Custom Build Hooks

Hatchling soporta hooks personalizados via `BuildHookInterface`. El hook se ejecuta durante el build para modificar `build_data`:

```python
from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class Aria2BinaryHook(BuildHookInterface):
    PLUGIN_NAME = "aria2-binary"

    def initialize(self, version: str, build_data: dict) -> None:
        """Run before build — descarga el binario aria2c."""
```

El hook se registra en pyproject.toml:

```toml
[tool.hatch.build.targets.wheel.hooks.custom]
path = "hatch_build.py"
```

**`build_data` keys que puede modificar un hook:**

| Key | Tipo | Propósito |
|---|---|---|
| `force_include` | `dict[str, str]` | Incluir archivos fuera del árbol: `src_path → dest_in_wheel` |
| `pure_python` | `bool` | Marcar como wheel pure Python |
| `tag` | `str` | Sobreescribir tag de plataforma |
| `infer_tag` | `bool` | Auto-detectar tag de plataforma |
| `shared_libraries` | `dict[str, str]` | Incluir librerías nativas |
| `dependencies` | `list[str]` | Agregar dependencias runtime |

### Hooks: initialize vs finalize

| Método | Timing | Propósito |
|---|---|---|
| `initialize(version, build_data)` | Antes del build | Preparar archivos, descargar assets |
| `finalize(version, build_data, artifact)` | Después del build | Limpiar archivos temporales |

### force_include — Bundling Archivos Externos

El caso de uso principal del hook en este proyecto: incluir el binario aria2c descargado:

```python
def initialize(self, version: str, build_data: dict) -> None:
    # Descargar binario
    binary_path = download_binary()

    # Forzar inclusión en wheel
    force_include = build_data.setdefault("force_include", {})
    force_include[str(binary_path)] = "aria2/bin/aria2c-linux-x86_64"
```

Esto hace que el binario aparezca como `aria2/bin/aria2c-linux-x86_64` dentro del wheel, aunque esté fuera del árbol `src/`.

### Múltiples Hooks

```toml
[tool.hatch.build.targets.wheel.hooks.custom]
path = "hatch_build.py"

[tool.hatch.build.targets.wheel.hooks.license]
path = "license_hook.py"
```

Los hooks se ejecutan en orden de declaración.

### PEP 517 Compliance

hatchling implementa PEP 517, lo que significa que es compatible con cualquier builder que soporte el estándar:

- `uv build` ✅ (recomendado)
- `pip install .` ✅
- `pypa/build` (`python -m build`) ✅
- `hatch build` ✅

### Debugging Build Issues

```bash
# Build con logs (uv)
uv build -v

# Build aislado (simula CI)
uv build --no-build-logs

# Ver qué archivos incluye el wheel
python -c "
import zipfile, sys
with zipfile.ZipFile('dist/aria2-0.1.0-py3-none-any.whl') as z:
    for f in z.namelist():
        print(f)
"
```

## Best Practices for SDKs

### 1. hatchling es invisible para el usuario
Solo está en `[build-system]`. No se instala nunca en el entorno del usuario.

### 2. `force_include` para assets externos
Úsalo para bundlear binarios, schemas, assets, o carpetas fuera de `src/`.

### 3. `wheel.packages` explícito
Listar cada sub-paquete o usar `packages = ["src/aria2"]` para descubrimiento automático.

### 4. Sdist sin binarios
Excluir binarios y archivos generados del source distribution con `[tool.hatch.build.targets.sdist]`.

### 5. Hook files debe ser importable
El path del hook es relativo al proyecto. El archivo se importa dinámicamente durante el build.

## Common Pitfalls

- **hatchling ≠ hatch**: No instalar hatch CLI. hatchling es solo build backend.
- **Hook sin `force_include`**: Si el hook descarga archivos pero no los agrega a `force_include`, no aparecen en el wheel.
- **Build hooks fallan en CI**: Los hooks corren en entorno aislado. No asumir herramientas del sistema.
- **`include` y `exclude` no afectan a `packages`**: `packages` controla qué paquetes Python se incluyen; `include/exclude` controla archivos sueltos.
- **Doble build**: `uv build` construye sdist primero (sin binarios), luego wheel (con binarios via hook). El hook corre en ambos.

## Commands

```bash
uv build                              # Build sdist + wheel (usa hatchling)
uv build --sdist                      # Source distribution
uv build --wheel                      # Wheel only
uv build -v                           # Verbose build logs
python -m zipfile -l dist/*.whl       # Inspect wheel contents
```

## Resources

- Hatchling docs: <https://hatch.pypa.io/latest/config/build/>
- Build hooks: <https://hatch.pypa.io/latest/config/build/#build-hooks>
- PEP 517: <https://peps.python.org/pep-0517/>
- PyPI: <https://pypi.org/project/hatchling/>
