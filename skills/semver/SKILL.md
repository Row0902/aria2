---
name: semver
description: "Trigger: semver, semantic versioning, version, versioning, MAJOR MINOR PATCH, version bump, version number, semantic release. Semantic Versioning standard (SemVer 2.0.0) — MAJOR.MINOR.PATCH, pre-release, build metadata, breaking changes."
license: Apache-2.0
metadata:
  author: gentleman-programming
  version: "1.0"
---

## When to Use

- Determining the next version number for a release
- Communicating breaking changes, features, and fixes to SDK consumers
- Configuring automated version bumps via conventional commits
- Understanding pre-release identifiers (alpha, beta, rc)
- Managing version constraints in `pyproject.toml` dependencies
- Publishing to PyPI with correct version tags

## Critical Patterns

### SemVer 2.0.0 — The Spec

```
MAJOR.MINOR.PATCH[-PRERELEASE][+BUILD]
  ↑      ↑      ↑         ↑          ↑
  1      2      3         4          5

1. MAJOR: breaking changes (incompatible API changes)
2. MINOR: new features (backward-compatible)
3. PATCH: bug fixes (backward-compatible)
4. PRERELEASE: unstable release (alpha, beta, rc)
5. BUILD: build metadata (ignored in version precedence)
```

### What Each Number Means

| Bump | When | Example | User Impact |
|---|---|---|---|
| **MAJOR** | Breaking API change | `1.4.2` → `2.0.0` | Must update code |
| **MINOR** | New feature, backward-compatible | `1.4.2` → `1.5.0` | Add new code optional |
| **PATCH** | Bug fix, backward-compatible | `1.4.2` → `1.4.3` | Safe to upgrade |

### Breaking Changes (MAJOR)

A breaking change forces consumers to modify their code:

- Removing or renaming a public method/class
- Changing method signature (adding required params)
- Changing return types
- Raising new exception types in existing code paths
- Changing default behavior
- Dropping Python version support

```python
# v1.x
async def add_uri(uri: str) -> GID: ...

# v2.0 (breaking: signature changed)
async def add_uri(uris: list[str]) -> GID: ...
```

### Pre-release Identifiers

```text
1.0.0-alpha.1        # Internal testing
1.0.0-beta.1         # Public testing
1.0.0-rc.1           # Release candidate
1.0.0                # Stable release
1.0.1                # Patch after stable
```

Pip/PEP 440 sorting: `1.0.0-alpha < 1.0.0-beta < 1.0.0-rc < 1.0.0`

```diff
- 1.0.0-alpha < 1.0.0-alpha.1 < 1.0.0-alpha.beta < 1.0.0-beta
- ↑ Numeric identifiers sort numerically (alpha < alpha.1)
- ↑ Pre-release versions have LOWER precedence than the release
```

### Version in pyproject.toml

```toml
[project]
name = "aria2"
version = "0.1.0"    # Development version (pre-1.0.0)
```

For pre-release versions:

```toml
version = "1.0.0-alpha.1"
version = "1.0.0-rc.1"
```

### Conventional Commits → Version Bump

| Commit | Bump | Example |
|---|---|---|
| `fix:` | PATCH | `1.0.0` → `1.0.1` |
| `feat:` | MINOR | `1.0.0` → `1.1.0` |
| `feat: ... BREAKING CHANGE:` | MAJOR | `1.0.0` → `2.0.0` |
| `fix!:` or `feat!:` | MAJOR | `1.0.0` → `2.0.0` |
| `docs:`, `chore:`, `refactor:` | None | No bump |

### Automated Versioning with python-semantic-release

```toml
[tool.semantic_release]
version_toml = ["pyproject.toml:project.version"]  # Where to write version
build_command = "uv build"                           # Build command
commit_parser = "angular"                            # Commit message parser
tag_format = "v{version}"                            # Tag format
branch = "main"                                      # Release branch
```

```bash
semantic-release version        # Dry-run: show next version
semantic-release version --bump  # Apply version bump
semantic-release changelog      # Generate CHANGELOG.md
semantic-release publish        # Build + publish + tag + GitHub release
```

### Manual Versioning

```bash
# Using uv
uv version                      # Show current version
uv version minor                # Bump minor (0.2.0)
uv version patch                # Bump patch (0.1.1)
uv version major                # Bump major (1.0.0)
uv version "0.2.0"              # Set explicit version

# Using sed (direct pyproject.toml edit)
sed -i 's/version = "0.1.0"/version = "0.2.0"/' pyproject.toml
```

### Version Bump Checklist

1. ✅ Conventional commits from last release are correct
2. ✅ `CHANGELOG.md` has new version entry with date
3. ✅ `pyproject.toml` version is updated
4. ✅ Git tag created: `git tag v0.2.0`
5. ✅ Tag pushed: `git push --tags`
6. ✅ GitHub release created: `gh release create v0.2.0`
7. ✅ Build and publish: `uv build && uv publish`

### Python Version Specifiers

| Spec | Meaning |
|---|---|
| `>=1.0,<2.0` | Compatible with 1.x (carat: `~=1.0`) |
| `>=1.0.0` | Any version ≥ 1.0.0 |
| `~=1.0.0` | Compatible release: ≥ 1.0.0, < 1.1.0 |
| `==1.0.0` | Exact version |
| `>=3.14` | Minimum Python version |

In `pyproject.toml`:

```toml
dependencies = [
    "httpx>=0.28.1,<1.0",
    "pydantic>=2.13.4,<3.0",
]
```

### 0.x Versions (Initial Development)

**Before 1.0.0, MINOR bumps can include breaking changes.**

```text
0.1.0 → 0.2.0 (may break API, MINOR = de facto MAJOR)
0.2.0 → 0.2.1 (PATCH = backward-compatible fix)
0.2.0 → 0.3.0 (may break API again)
```

This project is at `0.1.0` — in initial development. API is not yet stable.

### Version Precedence

```
1.0.0-alpha < 1.0.0-alpha.1 < 1.0.0-alpha.beta < 1.0.0-beta
< 1.0.0-beta.2 < 1.0.0-beta.11 < 1.0.0-rc.1 < 1.0.0-rc.2
< 1.0.0 < 2.0.0 < 2.1.0 < 2.1.1
```

Rules:
- Numeric identifiers sort numerically: `2 < 11`
- Alphanumeric identifiers sort lexicographically: `alpha < beta < rc`
- Pre-release < release: `1.0.0-rc < 1.0.0`
- Build metadata IGNORED for precedence: `1.0.0+build1 == 1.0.0`

### Release Flow

```bash
# 0. Prepare
git checkout main
git pull --rebase

# 1. Bump version
uv version patch                 # 0.1.0 → 0.1.1

# 2. Update changelog
# Add [Unreleased] entries to [0.1.1]

# 3. Commit
git add pyproject.toml CHANGELOG.md
git commit -m "chore: bump to 0.1.1"

# 4. Tag
git tag v0.1.1

# 5. Push
git push --atomic origin main v0.1.1

# 6. Release
gh release create v0.1.1 \
  --title "v0.1.1" \
  --notes "Bug fixes and minor improvements"

# 7. Publish
uv build && uv publish
```

### Dependency Pinning Strategy

| Stage | Strategy | Example |
|---|---|---|
| Development | Minimum version | `httpx>=0.28.1` |
| Library (SDK) | Minimum + upper bound | `httpx>=0.28.1,<1.0` |
| Application | Exact lock | `uv.lock` (via `uv sync --locked`) |

## Best Practices for SDKs

### 1. Start at 0.x during development
`0.1.0` signals API is unstable. Move to `1.0.0` when API is stable.

### 2. Communicate breaking changes
In changelog, commit message, AND release notes. Never silently break.

### 3. Use `~=` for compatibility
`~=1.0.0` means ≥ 1.0.0 < 1.1.0 — safe for libraries.

### 4. Don't re-use version numbers
Once a version is released, it's immutable. If a release fails, bump again.

### 5. Tag in git
Every release needs an annotated git tag: `git tag -a v1.0.0 -m "Release 1.0.0"`

### 6. Pre-release before MAJOR
Use `2.0.0-alpha.1`, `2.0.0-beta.1`, `2.0.0-rc.1` before final `2.0.0`.

### 7. Document deprecations
Deprecate in MINOR version, remove in next MAJOR.

## Common Pitfalls

- **Breaking change in MINOR**: If a MINOR bump breaks API, users will have untestable failures. Always check for breaking changes.
- **0.x treated as stable**: Pre-1.0.0, MINOR can break API. Document this clearly.
- **Forgetting git tag**: Without a tag, consumers can't pin to a specific version.
- **Pre-release version precedence**: `1.0.0-rc.1 < 1.0.0` — pip won't install pre-release unless explicitly requested.
- **Bumping multiple numbers**: `1.0.0 → 2.1.0` is invalid. Bump only the highest changed segment.

## Commands

```bash
# ── Show version ────────────────────────────────────
uv version                          # Show current project version

# ── Bump version ────────────────────────────────────
uv version patch                    # 0.1.0 → 0.1.1
uv version minor                    # 0.1.0 → 0.2.0
uv version major                    # 0.1.0 → 1.0.0
uv version "1.0.0-rc.1"            # Explicit version

# ── Git tag ──────────────────────────────────────────
git tag -a v0.2.0 -m "Release 0.2.0"
git push origin v0.2.0

# ── Semantic release (if configured) ─────────────────
semantic-release version            # Preview
semantic-release publish            # Full release

# ── Publish ──────────────────────────────────────────
uv build
uv publish
```

## Resources

- SemVer 2.0.0: <https://semver.org/>
- PEP 440: <https://peps.python.org/pep-0440/>
- Conventional Commits: <https://www.conventionalcommits.org/>
- python-semantic-release: <https://python-semantic-release.readthedocs.io/>
- Keep a Changelog: <https://keepachangelog.com/>
