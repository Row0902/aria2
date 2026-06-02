---
name: conventional-commits
description: "Trigger: commit, conventional commit, git commit, commit message, semantic versioning, semver, changelog, git log. Structured commit message convention for automatic versioning and changelog generation."
license: Apache-2.0
metadata:
  author: gentleman-programming
  version: "1.0"
---

## When to Use

- Writing commit messages with consistent structure
- Preparing for automated changelog generation
- Driving semantic versioning from commit history
- Enabling tools like `python-semantic-release` or `commitizen`
- Enforcing commit conventions in CI or pre-commit hooks
- Making git history searchable and scannable

## Critical Patterns

### Commit Message Structure

```
<type>(<scope>): <subject>

<body>

<footer>
```

Each part has specific rules:

| Part | Required | Max length | Rules |
|---|---|---|---|
| `type` | ✅ | — | Lowercase, one of the defined types |
| `scope` | ❌ | — | Lowercase, noun describing the module |
| `subject` | ✅ | 72 chars | Imperative mood, no period |
| `body` | ❌ | 72 chars per line | Explains what and why, not how |
| `footer` | ❌ | — | BREAKING CHANGE, issue references |

### Types

| Type | Description | Version bump |
|---|---|---|
| `feat` | A new feature | MINOR |
| `fix` | A bug fix | PATCH |
| `docs` | Documentation only | PATCH |
| `style` | Code style (formatting, no logic change) | — |
| `refactor` | Code change that neither fixes nor adds | — |
| `perf` | Performance improvement | PATCH |
| `test` | Adding or fixing tests | — |
| `build` | Build system or dependencies | — |
| `ci` | CI configuration or scripts | — |
| `chore` | Other changes (no production code change) | — |

### Examples

```text
feat(client): add download status polling with keys filter

Add `tell_status()` with optional `keys` parameter to reduce
response payload size for large downloads.

Closes #42
```

```text
fix(http): handle connection refused during transport init

Wrap httpx.ConnectError in Aria2ConnectionError so users
get SDK exceptions instead of raw httpx errors.
```

```text
feat(ws): implement exponential backoff for reconnection

Reconnect with 1s, 2s, 4s, 8s, 16s, 30s backoff.
Reset to 1s on successful connection.
```

```text
BREAKING CHANGE: remove sync client interface

The synchronous Aria2Client class has been removed.
All operations are now async-only.

Migration: use `async with Aria2Client(...)` instead.
```

### Breaking Changes

Breaking changes can be indicated with:

1. `BREAKING CHANGE:` in the footer:
```text
feat(rpc)!: change response format to snake_case

BREAKING CHANGE: All RPC response field names are now
snake_case instead of camelCase.
```

2. A `!` after type/scope (Conventional Commits 1.0+):
```text
feat(api)!: remove deprecated `addUri` method
```

Breaking changes trigger a MAJOR version bump.

### Scope Examples

For this SDK:

| Scope | Module |
|---|---|
| `client` | `Aria2Client` |
| `http` | `HttpTransport` |
| `ws` | `WebSocketTransport` |
| `rpc` | RPC builder/parser |
| `models` | Data models |
| `errors` | Error hierarchy |
| `types` | GID, enums |
| `cli` | CLI entry point |
| `bin` | Binary discovery |
| `build` | Build hook, packaging |
| `docs` | Documentation, README |
| `ci` | GitHub Actions |
| `deps` | Dependencies |

### Imperative Mood

Write the subject as a command:

```text
✅ feat: add tell_status method
✅ fix: handle connection timeout
✅ docs: update README with examples

❌ feat: added tell_status method
❌ fix: handling connection timeout
❌ docs: updated README
```

### Subject Rules

- Max 72 characters
- No trailing period
- Imperative present tense
- Lowercase after type/scope
- Don't repeat the module name in the subject

### Body Rules

- Blank line after subject
- Wrap at 72 characters
- Explain **what** and **why**, not **how**
- Connect to the user's perspective, not implementation details

### Footer Rules

- `BREAKING CHANGE:` for breaking changes
- `Closes #N` or `Fixes #N` for issue references
- Multiple footers separated by blank lines
- `Reviewed-by:` for reviewer attribution

### Automation

```yaml
# pre-commit hook for commit messages
- repo: https://github.com/compilerla/conventional-pre-commit
  rev: v3.6.0
  hooks:
    - id: conventional-pre-commit
      stages: [commit-msg]
      args: []
```

### Semantic Release

`python-semantic-release` can parse conventional commits to:

```bash
semantic-release version     # Bump version based on commits
semantic-release publish     # Build, publish, create GitHub release
semantic-release changelog   # Generate CHANGELOG.md
```

Configuration in `pyproject.toml`:

```toml
[tool.semantic_release]
version_toml = ["pyproject.toml:project.version"]
commit_parser = "angular"
build_command = "uv build"
```

## Best Practices for SDKs

### 1. Scope every commit
Always include the scope — it makes history scannable and changelogs useful.

### 2. One logical change per commit
Don't mix `feat` + `fix` in the same commit. Use `git add -p` to stage selectively.

### 3. Reference issues
Link commits to GitHub issues with `Closes #N` for auto-closing.

### 4. Document breaking changes explicitly
Breaking changes must be obvious in the commit message body.

### 5. Rebase before merging
Keep history clean with `git rebase main` and fixup/squash WIP commits.

## Common Pitfalls

- **Subject too long**: Over 72 chars gets truncated in many git tools.
- **Trailing period**: "Add feature." → "Add feature" (no period).
- **Past tense**: "Added" → "Add". Imperative mood is the rule.
- **Vague scope**: `chore: fix stuff` → useless. Be specific.
- **No body for complex changes**: If the subject isn't enough, write a body.
- **Breaking change not marked**: Missing `BREAKING CHANGE:` or `!` — version won't bump correctly.

## Commands

```bash
# Check commit message
echo "feat: add tell_status" | npx commitlint

# View current commit log
git log --oneline

# Amend last commit message
git commit --amend -m "fix: correct timeout handling"

# Squash commits
git rebase -i HEAD~3

# Generate changelog from conventional commits
npx conventional-changelog -p angular -i CHANGELOG.md -s
```

## Resources

- Conventional Commits: <https://www.conventionalcommits.org/>
- Angular commit convention: <https://github.com/angular/angular/blob/main/CONTRIBUTING.md#commit>
- semantic-release: <https://python-semantic-release.readthedocs.io/>
- commitlint: <https://commitlint.js.org/>
- conventional-pre-commit: <https://github.com/compilerla/conventional-pre-commit>
