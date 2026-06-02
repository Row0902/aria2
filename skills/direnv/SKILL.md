---
name: direnv
description: "Trigger: direnv, .envrc, .env, environment variables, project env, shell env, direnv allow, direnv edit, env vars per directory. Environment variable manager for your shell — load/unload project-specific env vars on directory change."
license: Apache-2.0
metadata:
  author: gentleman-programming
  version: "1.0"
---

## When to Use

- Setting project-specific environment variables (API keys, tokens, paths)
- Automatically activating the project's Python venv when entering the directory
- Adding `src/` to `PYTHONPATH` for development imports
- Loading secrets or config from `.env` files without committing them
- Ensuring consistent environment across team members (via `.envrc` in git)
- Replacing `source venv/bin/activate` / `conda activate` with automatic env management

## Critical Patterns

### How direnv Works

```
Shell prompt → direnv hook checks for .envrc in current/parent dir
  → If found and allowed: load exported vars into shell
  → If found and NOT allowed: prompt "direnv: .envrc is not allowed"
  → cd out of dir: unload vars, restore previous environment
```

direnv is a **static binary** (~2MB) that hooks into your shell (bash, zsh, fish). It's fast enough to run on every prompt without noticeable delay.

### Setup

```bash
# Install via brew (already installed)
brew install direnv

# Add to shell config (~/.bashrc, ~/.zshrc)
eval "$(direnv hook bash)"    # for bash
eval "$(direnv hook zsh)"     # for zsh

# Or with uv (for CI/scripts)
uv tool install direnv
```

### Basic Usage

```bash
# Create .envrc
echo 'export FOO=bar' > .envrc

# Allow it (first time only; changes require re-allow)
direnv allow .

# On next cd, FOO=bar is set
cd .
# direnv: loading .envrc
# direnv: export +FOO

# cd out — FOO is unloaded
cd ..
# direnv: unloading
# direnv: export ~FOO
```

### .envrc File Language

.envrc files are **bash scripts** with a restricted set of functions provided by direnv's stdlib:

```bash
# Export variables
export SECRET_TOKEN="abc123"
export MY_VAR="value"

# Modify PATH
PATH_add "src/"

# Load .env file
dotenv

# Include another .envrc
source_env ../shared/.envrc
```

### Key direnv Stdlib Functions

| Function | Purpose |
|---|---|
| `PATH_add <dir>` | Prepend to `$PATH` (deduped) |
| `path_add <var> <dir>` | Add `dir` to any colon-separated variable |
| `dotenv` | Load `.env` file (key=value format, no exports) |
| `dotenv_if_exists` | Load `.env` only if it exists (safe) |
| `source_env <path>` | Include another `.envrc` |
| `source_up` | Include parent directory's `.envrc` |
| `layout python3` | Activate Python venv (legacy) |
| `layout uv` | **Not built-in** — handled manually below |
| `watch_file <path>` | Reload .envrc when `path` changes |
| `watch_dir <dir>` | Reload when files in `dir` change |
| `strict_env` | Enable `set -euo pipefail` mode |
| `unstrict_env` | Revert to normal mode |
| `env_vars_required <vars>` | Fail if required vars are missing |
| `has <cmd>` | Check if command exists in PATH |
| `user_rel_path <path>` | Convert to `~`-relative path for display |

### .envrc for This Project

```bash
# .envrc — aria2 Python SDK

# ── Strict mode ──────────────────────────────────────
strict_env

# ── UV-managed Python ────────────────────────────────
# uv detecta automáticamente .python-version y .venv
# No se necesita source_env .venv/bin/activate

# ── PYTHONPATH para imports en desarrollo ────────────
PATH_add "src/"
export PYTHONPATH="${PWD}/src${PYTHONPATH:+:$PYTHONPATH}"

# ── Configuración del SDK (opcional) ─────────────────
# export ARIA2_HOST="localhost"
# export ARIA2_PORT="6800"
# export ARIA2_SECRET="token"
# export ARIA2_DEBUG="1"

# ── Cargar secrets locales (no versionados) ──────────
dotenv_if_exists

# ── Layout para UV ────────────────────────────────────
# Sin venv: uv maneja el entorno automáticamente
log_status "aria2 SDK — uv managed"
```

### .env (local secrets, no versionado)

```bash
# .env — NO versionar. Secrets locales para desarrollo.
# Agregar ".env" a .gitignore.

ARIA2_SECRET="mi-token-local"
ARIA2_HOST="192.168.1.100"
ARIA2_DEBUG="1"
```

### .gitignore

Asegurarse de que `.env` esté en `.gitignore`:

```gitignore
# Environment
.env
.env.local
*.env
```

Pero `.envrc` SÍ se versiona (es compartido):

```gitignore
# No ignorar .envrc
!.envrc
```

### Commands Reference

```bash
direnv allow .                  # Allow .envrc in current dir
direnv deny .                   # Deny/block .envrc
direnv edit .                   # Open .envrc in $EDITOR + auto-allow
direnv reload                   # Reload .envrc (after manual edit)
direnv revoke                   # Revoke all allowed .envrcs
direnv prune                    # Remove stale allowed files
direnv status                   # Show status of current .envrc
direnv export bash              # Print env diff as bash exports
direnv hook bash                # Print hook script for bash
direnv version                  # Show version
direnv stdlib                   # Print all stdlib functions
direnv exec . <cmd>             # Run command with env loaded
direnv fetchurl <url>           # Fetch URL into direnv CAS
```

### Security Model

direnv has a whitelist-based security model:

```
1. Create .envrc → "direnv: .envrc is not allowed"
2. Run `direnv allow .` → hash stored in ~/.local/share/direnv/allow/
3. Edit .envrc → hash changes → "loading .envrc (change detected)"
4. Must re-allow: `direnv allow .`
```

This prevents malicious `.envrc` files from cloning repos and auto-executing.

### Integration with UV

UV-managed projects don't need a venv activation — `uv run` handles it automatically:

```bash
# Without direnv
uv run pytest

# With direnv (env vars loaded automatically)
uv run pytest                    # Still need uv run
```

But direnv can still set `PATH_add` and env vars that uv uses:

```bash
# UV env vars
export UV_MANAGED_PYTHON="never"  # Don't auto-download Python
export UV_PYTHON_DOWNLOADS="never"
export UV_NO_CACHE="1"
```

### dotenv Integration

direnv can load a standard `.env` file (no exports, just `KEY=VALUE`):

```bash
# .env
DATABASE_URL=postgres://localhost/db
ARIA2_SECRET=dev-token

# .envrc
dotenv_if_exists
```

This separates **secrets** (`.env`, gitignored) from **config** (`.envrc`, versioned).

### Strict Mode

```bash
# .envrc
strict_env       # Same as: set -euo pipefail
```

Benefits:
- `set -e`: exit on error
- `set -u`: error on undefined variables
- `set -o pipefail`: fail if any command in pipeline fails

This catches errors early in .envrc evaluation.

### Layout pkg with Workspace Projects

For monorepos with uv workspaces:

```bash
# Root .envrc
strict_env
source_up

. ../../.envrc
```

### Debugging

```bash
# Check if direnv is hooked
direnv status

# Force reload
direnv reload

# See what would be exported (without loading)
direnv export bash

# Run a command with env loaded
direnv exec . python -c "import os; print(os.environ.get('PYTHONPATH'))"

# Verbose output (set before cd)
export DIRENV_LOG_FORMAT="direnv: [%s] %s"
```

### CI Integration

direnv is useful in CI to test the same env setup:

```yaml
steps:
  - uses: actions/checkout@v4
  - run: brew install direnv                         # Install
  - run: direnv allow .                              # Allow .envrc
  - run: direnv exec . uv run pytest -v              # Run with env
```

Or just source the .envrc directly:

```yaml
- run: source .envrc && uv run pytest
```

### Common Pitfalls

- **`.envrc` not allowed**: Always `direnv allow .` after creating or editing.
- **Secretes in `.envrc`**: Don't put secrets in version-controlled `.envrc`. Use `.env` + `dotenv_if_exists`.
- **`strict_env` breaks with unset vars**: If your `.envrc` uses vars that might be unset, check with `has` or `strict_env` carefully.
- **Slow shell startup**: If direnv is slow, check `direnv status` for issues. Usually fast (~10ms).
- **`builtin cd` vs alias**: direnv hooks `cd` in bash/zsh. If you use a custom `cd` alias, make sure it calls `builtin cd`.
- **Fish shell**: Set `set -g direnv_fish_mode eval_on_arrow` for best UX.
- **Layout python**: Don't use `layout python3` in uv projects. uv manages its own venv.

## Best Practices

### 1. Version `.envrc`, ignore `.env`
`.envrc` goes in git (project config). `.env` stays local (secrets).

### 2. One `.envrc` per project root
Don't nest `.envrc` files. Use `source_up` if you need parent config.

### 3. Use `strict_env`
Catches typos and missing deps early. Essential for team-shared `.envrc`.

### 4. Prefer `dotenv_if_exists` over `export` in `.envrc`
Secrets stay in `.env`, config stays in `.envrc`.

### 5. Use `log_status` for UX feedback
```bash
log_status "Starting aria2 development environment"
```

### 6. PATH_add, not export PATH=
```bash
PATH_add "src/"          # ✅ deduped, prepended
export PATH="src/:$PATH"  # ❌ may duplicate on reload
```

## Commands

```bash
# ── Setup ────────────────────────────────────────────
brew install direnv
echo 'eval "$(direnv hook bash)"' >> ~/.bashrc

# ── Project ──────────────────────────────────────────
echo 'strict_env
PATH_add "src/"
dotenv_if_exists' > .envrc
direnv allow .

# ── Management ───────────────────────────────────────
direnv allow .               # Approve .envrc
direnv deny .                # Block .envrc
direnv edit .                # Edit + auto-allow
direnv reload                # Force reload
direnv status                # Show status

# ── Information ──────────────────────────────────────
direnv version
direnv stdlib                # All available functions
direnv export bash           # Show env diff
```

## Resources

- Documentation: <https://direnv.net/>
- GitHub: <https://github.com/direnv/direnv>
- Stdlib reference: `direnv stdlib`
- Man page: `man direnv`
- Wiki: <https://github.com/direnv/direnv/wiki>
