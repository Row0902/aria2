---
name: hatch
description: "Trigger: hatch, hatchling, build backend, build hook, Python build, packaging. **Este proyecto usa uv build, no hatch CLI**. hatchling es solo el backend."
license: Apache-2.0
metadata:
  author: gentleman-programming
  version: "1.0"
---

## ⚠️ Este proyecto usa uv, no hatch CLI

```diff
- hatch build      # ❌ No se usa
+ uv build         # ✅ Se usa uv
- hatch version    # ❌ No se usa
+ uv version       # ✅ Se usa uv
- hatch test       # ❌ No se usa
+ uv run pytest    # ✅ Se usa uv
```

**hatchling** (el backend de build) sigue siendo necesario como PEP 517 backend en `[build-system]`, pero se invoca automáticamente a través de `uv build`. No se instala hatch CLI.

→ Ver: `skills/hatchling/SKILL.md` para el backend hatchling.
→ Ver: `skills/uv/SKILL.md` para build, publish, y version management con uv.

---

## When to Use (original content below)
- Setting up custom build hooks (binary download, code generation, assets)
- Managing `[tool.hatch.build]` configuration in `pyproject.toml`
- Building source distributions and wheels
- Running tests with hatch's test runner (when using the full hatch CLI)
- Understanding build isolation, wheel packages, and sdist exclusion

## Critical Patterns

### Hatch vs Hatchling

| Tool | Role |
|---|---|
| **hatchling** | Build backend library (installed as build dependency, NOT a project dependency) |
| **hatch** | CLI tool for project management (build, test, publish, version) — optional |

This project uses **hatchling** as the build backend (`build-backend = "hatchling.build"`), which is required in `[build-system]`. The full `hatch` CLI is not required for building — `uv build` or `pip install` will invoke hatchling automatically.

### Build System Declaration

```toml
[build-system]
requires = ["hatchling>=1.27,<2"]
build-backend = "hatchling.build"
```

Hatchling is installed temporarily in an isolated build environment by uv/pip. It does NOT need to be in `[project.dependencies]` or `[dependency-groups]`.

### Build Configuration

All hatchling config lives under `[tool.hatch.build]` in `pyproject.toml`:

```toml
[tool.hatch.build]
include = ["/src", "/aria2_bin/**"]       # Glob patterns to include
exclude = ["tests/**", "**/__pycache__/**"]  # Glob patterns to exclude

[tool.hatch.build.targets.wheel]
packages = ["src/aria2"]                   # Python packages to ship

[tool.hatch.build.targets.sdist]
exclude = ["/aria2_bin/**"]                # Exclude binaries from source dist
```

### Build Targets

| Target | Description |
|---|---|
| `wheel` | Binary distribution (`.whl`) — installed by pip |
| `sdist` | Source distribution (`.tar.gz`) — used for publishing |
| `wheel.packages` | List of package directories to include in the wheel |
| `wheel.only-include` | Force-include patterns (overrides exclude) |
| `wheel.dev-mode-exact` | Exact paths for dev installs |

### Build Hook Interface

Hatchling supports custom build hooks via `BuildHookInterface`. Hooks run at specific points during the build:

```python
from hatchling.builders.hooks.plugin.interface import BuildHookInterface

class MyHook(BuildHookInterface):
    PLUGIN_NAME = "my-hook"

    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        """Run before build starts — use to prepare files."""
        pass

    def finalize(self, version: str, build_data: dict[str, Any], artifact: str) -> None:
        """Run after build completes — use for cleanup."""
        pass
```

**Key `build_data` fields hooks can modify:**

| Field | Type | Purpose |
|---|---|---|
| `build_data["force_include"]` | `dict[str, str]` | Force file → path in wheel mapping |
| `build_data["infer_tag"]` | `bool` | Auto-detect wheel platform tag |
| `build_data["pure_python"]` | `bool` | Mark as pure Python wheel |
| `build_data["shared_libraries"]` | `dict[str, str]` | Include native libs |
| `build_data["tag"]` | `str` | Override wheel platform tag |
| `build_data["dependencies"]` | `list[str]` | Add runtime dependencies |
| `build_data["requires_app_dirs"]` | `bool` | Flag for app data dirs |

**Hook registration in pyproject.toml:**

```toml
[tool.hatch.build.targets.wheel.hooks.custom]
path = "hatch_build.py"
```

The `path` points to the file containing the hook class. Hatchling auto-discovers subclasses of `BuildHookInterface`.

### Example: Binary Download Hook

This project has a custom build hook (see `hatch_build.py`) that:

1. Detects the target platform from `sys.platform` + `platform.machine()`
2. Downloads a pre-built aria2c binary from GitHub releases
3. Includes it in the wheel via `force_include`
4. Writes a VERSION file

```python
class Aria2BinaryHook(BuildHookInterface):
    PLUGIN_NAME = "aria2-binary"

    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        # Determine target binary name
        # Download binary and write to cache dir
        # Set force_include to bundle in wheel
        force_include = build_data.setdefault("force_include", {})
        force_include[str(binary_path)] = "aria2/bin/{artifact}"
```

### Include/Exclude Pattern Rules

Patterns use gitignore-style syntax:

- `src/` → matches `src` at any level
- `/src/` → matches `src` only at project root (leading `/`)
- `**/__pycache__/**` → any `__pycache__` directory at any depth
- `aria2_bin/**` → all files in that directory
- `*.pyc` → any `.pyc` file

### Wheel Packages

`wheel.packages` tells hatchling which directories contain Python packages:

```toml
[tool.hatch.build.targets.wheel]
packages = [
  "src/aria2",
  "src/aria2/bin",
  "src/aria2/cli",
  "src/aria2/client",
  "src/aria2/client/transport",
  "src/aria2/errors",
  "src/aria2/models",
  "src/aria2/rpc",
  "src/aria2/types",
]
```

Each directory must contain an `__init__.py`. Directories NOT listed here won't be included.

Alternatively, use `where`:

```toml
[tool.hatch.build.targets.wheel]
packages = ["src/aria2"]
```

This automatically discovers all sub-packages under `src/aria2/`.

### Multiple Build Hooks

Multiple hooks run in order of declaration:

```toml
[tool.hatch.build.targets.wheel.hooks.custom]
path = "hatch_build.py"

[tool.hatch.build.targets.wheel.hooks.another-hook]
path = "another_hook.py"
```

### Build Command Invocation

```bash
# Via uv (recommended for this project)
uv build                              # Build sdist + wheel into dist/
uv build --sdist                      # Source distribution only
uv build --wheel                      # Wheel only
uv build -o custom-dist/              # Output to custom directory

# Via hatch CLI (if installed)
uv tool install hatch                 # Install hatch CLI
hatch build                           # Build sdist + wheel
hatch build --hooks-only              # Only run hooks

# Via pip
pip install .                         # Install from source (invokes hatchling)
```

### Version Management (via hatch CLI)

```bash
hatch version                         # Show current version
hatch version minor                   # Bump minor (0.2.0)
hatch version patch                   # Bump patch (0.1.1)
hatch version "0.2.0"                 # Set explicit version
```

Version is read from `[project].version` in `pyproject.toml`.

### Test Runner (via hatch CLI)

```bash
hatch test                            # Run tests (uses pytest by default)
hatch test --cover                    # With coverage
hatch test --all                      # Test all Python versions in matrix
```

Configure in `pyproject.toml`:

```toml
[tool.hatch.envs.default]
features = ["test"]                   # Dependency features to include

[tool.hatch.envs.test]
dependencies = ["pytest", "pytest-cov"]
scripts = {test = "pytest {args}"}
```

### Common Pitfalls

- **hatchling is NOT a project dependency**: It only goes in `[build-system] requires`. Installing it manually is unnecessary.
- **Build hooks run during build**: They execute in an isolated build environment. System dependencies may not be available.
- **`force_include` paths**: Keys are source paths, values are destination paths inside the wheel. Use forward slashes.
- **`wheel.packages` vs `include`**: `packages` controls which Python packages are included; `include` controls generic file matching.
- **No `pyproject.toml` changes needed for hooks**: Hook files are imported dynamically from the paths you specify.
- **Hooks run for sdist AND wheel by default**: Use `version` parameter to conditionalize behavior per target.

## Code Examples

### Minimal pyproject.toml build config
```toml
[build-system]
requires = ["hatchling>=1.27,<2"]
build-backend = "hatchling.build"

[tool.hatch.build]
include = ["src/**"]
exclude = ["tests/**"]

[tool.hatch.build.targets.wheel]
packages = ["src/my_pkg"]
```

### Custom build hook (generate version file)
```python
# build_hook.py
from hatchling.builders.hooks.plugin.interface import BuildHookInterface

class VersionFileHook(BuildHookInterface):
    PLUGIN_NAME = "version-file"

    def initialize(self, version: str, build_data: dict) -> None:
        force_include = build_data.setdefault("force_include", {})
        import tempfile
        f = tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt")
        f.write(f"VERSION={version}\nBUILD_TIME={__import__('time').time()}\n")
        f.close()
        force_include[f.name] = "my_pkg/_build_info.txt"
```

### Multi-hook build config
```toml
[tool.hatch.build.targets.wheel.hooks.custom]
path = "build_hook.py"
```

### Platform-specific wheels
```toml
[tool.hatch.build.targets.wheel]
packages = ["src/aria2"]

[tool.hatch.build.targets.wheel.hooks.custom]
path = "hatch_build.py"
```

## Commands

```bash
# ── Build (via uv) ───────────────────────────────────
uv build                           # Build sdist + wheel
uv build --sdist                   # Source distribution only
uv build --wheel                   # Wheel only
uv build -o dist/                  # Custom output dir

# ── Build (via hatch CLI) ────────────────────────────
uv tool install hatch              # Install hatch CLI
hatch build                        # Build sdist + wheel
hatch build --hooks-only           # Run build hooks only
hatch version                      # Show version
hatch version patch                # Bump version
hatch clean                        # Remove build artifacts
hatch test                         # Run tests

# ── Info ─────────────────────────────────────────────
uv run python -c "import hatchling; print(hatchling.__version__)"
```

## Resources

- Documentation: <https://hatch.pypa.io/>
- Hatchling docs: <https://hatch.pypa.io/latest/config/build/>
- Build hooks: <https://hatch.pypa.io/latest/config/build/#build-hooks>
- GitHub: <https://github.com/pypa/hatch>
- PyPI: <https://pypi.org/project/hatchling/>
