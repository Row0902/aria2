# AGENTS.md — aria2

## Project Skills

See `.atl/skill-registry.md` for the full index of project-specific skills.

### Available Skills

| Skill | Description | Location |
|-------|-------------|----------|
| `ty` | Astral type checker — replaces mypy. 120+ rules, Rust-based, fast. | `skills/ty/SKILL.md` |
| `ruff` | Astral linter + formatter. Replaces flake8 + isort + black. | `skills/ruff/SKILL.md` |
| `uv` | Astral package/project manager. Replaces pip + poetry + venv + pyenv. | `skills/uv/SKILL.md` |
| `pre-commit` | Git hook framework. Automate code quality checks before commits/pushes. | `skills/pre-commit/SKILL.md` |
| `hatch` | Build backend (hatchling) + project manager. Configura builds, hooks, y packaging. | `skills/hatch/SKILL.md` |
| `pytest-asyncio` | Async testing plugin. Async fixtures, event loop management. | `skills/pytest-asyncio/SKILL.md` |
| `docstring-google` | Google-style docstrings. Reglas, ejemplos, y configuración ruff D. | `skills/docstring-google/SKILL.md` |
| `httpx` | HTTP client. AsyncClient, timeouts, connection pooling, error handling. | `skills/httpx/SKILL.md` |
| `pytest` | Testing framework. Fixtures, parametrize, coverage, conftest. | `skills/pytest/SKILL.md` |
| `respx` | HTTP mocking. Simular JSON-RPC en tests sin servidor real. | `skills/respx/SKILL.md` |
| `asyncio-patterns` | Async patterns. TaskGroup, timeouts, cancelación, graceful shutdown. | `skills/asyncio-patterns/SKILL.md` |
| `pydantic-sdk` | Pydantic para SDKs. Modelos, validación, discriminated unions. | `skills/pydantic-sdk/SKILL.md` |
| `sdk-design` | Diseño de SDKs. Transport abstraction, error wrapping, event dispatch. | `skills/sdk-design/SKILL.md` |
| `ci-github-actions` | CI/CD. Workflows de lint, type-check, test, build, publish. | `skills/ci-github-actions/SKILL.md` |
| `logging-sdk` | Logging. Niveles, machine secrets, debugging. | `skills/logging-sdk/SKILL.md` |
| `websockets-testing` | Testing WebSocket. Live server fixtures, notificaciones, reconexión. | `skills/websockets-testing/SKILL.md` |
| `conventional-commits` | Commits convencionales. Tipos, scopes, semver. | `skills/conventional-commits/SKILL.md` |
| `changelog` | Changelog. Keep a Changelog, versionado, release notes. | `skills/changelog/SKILL.md` |
| `code-review-checklist` | Code review. Checklist para PRs de SDK. | `skills/code-review-checklist/SKILL.md` |
| `aria2` | API completa de aria2. RPC methods, notificaciones, opciones, errores, BitTorrent. | `skills/aria2/SKILL.md` |
| `pytest-cov` | Cobertura de código. Reports term, HTML, XML, thresholds. | `skills/pytest-cov/SKILL.md` |
| `hatchling` | Build backend PEP 517. Custom hooks, force_include, wheel config. | `skills/hatchling/SKILL.md` |
| `direnv` | Environment variables por proyecto. .envrc, PATH_add, dotenv, secrets. | `skills/direnv/SKILL.md` |
| `semver` | Semantic Versioning. MAJOR.MINOR.PATCH, pre-release, version bump, conventional commits. | `skills/semver/SKILL.md` |
| `gh` | GitHub CLI. PRs, issues, releases, workflows, API, repos. | `skills/gh/SKILL.md` |

## Branch Strategy

See [BRANCH-STRATEGY.md](BRANCH-STRATEGY.md) for the git workflow: `main` is stable/prod, `develop` is canary, `feature/*` and `bugfix/*` branch from `develop`.

## Loading Protocol

When delegating work via subagents, read `.atl/skill-registry.md` and pass exact skill paths under `## Skills to load before work`.
