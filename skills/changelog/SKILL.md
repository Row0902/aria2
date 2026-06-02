---
name: changelog
description: "Trigger: changelog, CHANGELOG.md, keep a changelog, release notes, version history, changelog entry. Changelog management following Keep a Changelog convention — version entries, categories, and release process."
license: Apache-2.0
metadata:
  author: gentleman-programming
  version: "1.0"
---

## When to Use

- Creating or updating CHANGELOG.md for releases
- Adding entries for new features, fixes, and breaking changes
- Preparing release notes for GitHub releases
- Structuring version history for SDK consumers
- Automating changelog generation from conventional commits

## Critical Patterns

### Format (Keep a Changelog)

Changelog follows [Keep a Changelog](https://keepachangelog.com/) with versioned sections:

```markdown
# Changelog

All notable changes to this project will be documented in this file.

## [0.2.0] - 2026-06-15

### Added
- `tell_status()` with optional `keys` parameter for selective field queries
- `get_files()` method to retrieve file information for downloads
- Python 3.14 type hints to all public methods

### Changed
- Response fields are now snake_case (was camelCase)
- `Aria2Client.connect()` no longer raises on WS failure — degrades to HTTP

### Fixed
- `Aria2RpcError` now includes the error code in string representation
- WebSocket reconnection backoff resets after successful connect

### Removed
- Deprecated `addUri` method — use `add_uri()` instead

### Security
- Secrets are masked in debug log output

## [0.1.0] - 2026-06-01

### Added
- Initial release
- Async HTTP and WebSocket transport
- Full aria2 method API coverage
- Binary discovery and CLI entry point
- Pydantic models with discriminated union support
```

### Section Categories

| Section | When to use |
|---|---|
| `Added` | New features, methods, modules |
| `Changed` | Behavior changes, API modifications |
| `Deprecated` | Features that will be removed in future |
| `Fixed` | Bug fixes |
| `Removed` | Features removed in this release |
| `Security` | Security fixes or improvements |
| `Documentation` | Docs updates, README changes |
| `Internal` | Build system, CI, refactoring (no user impact) |

### Version Header

```markdown
## [0.2.0] - 2026-06-15
```

- Format: `## [MAJOR.MINOR.PATCH] - YYYY-MM-DD`
- Date is the release date in ISO format
- Unreleased section at top for in-progress work:

```markdown
## [Unreleased]

### Added
- (list unreleased changes here)

### Fixed
- (list unreleased fixes here)
```

### Link References

At the bottom of the file, link each version to its GitHub diff:

```markdown
[unreleased]: https://github.com/Row0902/aria2/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/Row0902/aria2/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/Row0902/aria2/releases/tag/v0.1.0
```

### Initial Changelog

```markdown
# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- (empty — no unreleased changes yet)
```

### Entry Style

```markdown
### Added
- `add_uri(uris, options=None, position=None)` — new method for download addition
- `on_download_start(callback)` — event registration for WS notifications

### Fixed
- `Aria2RpcError` now includes error code in string representation (#23)
- WebSocket reconnection backoff now resets after successful reconnect (#19)
```

Each entry:
- Starts with a capital letter
- Uses backticks for code/method names
- References issue numbers when applicable (`(#23)`)
- Is one line unless more detail is needed
- Describes the change from the **user's perspective**

### Automated Generation

With `python-semantic-release` and conventional commits:

```bash
semantic-release changelog      # Generate CHANGELOG.md from git log
semantic-release version --print  # Preview next version
```

Or manually from git log:

```bash
git log --oneline --no-merges v0.1.0..HEAD | grep -E '^feat' | sed 's/^/### Added\n- /'
```

### Release Workflow

1. Update version in `pyproject.toml`
2. Move `[Unreleased]` entries to a new version section
3. Add the date
4. Update link references
5. Commit: `chore: bump to 0.2.0`
6. Tag: `git tag v0.2.0`
7. Push: `git push --tags`
8. Create GitHub release with changelog content

## Best Practices for SDKs

### 1. Keep `[Unreleased]` updated
Every PR should add an entry to the Unreleased section. Don't batch them at release time.

### 2. Write for users
Describe what changed from the user's perspective, not implementation details.

### 3. Reference issues
Link to GitHub issues and PRs so users can find more context.

### 4. Call out breaking changes
Put `### ⚠️ BREAKING CHANGES` section when there are breaking changes.

### 5. Use consistent tense
Past tense for entries: "Added", "Fixed", "Changed". Not "Adds", "Fixes".

### 6. Separate internal changes
Use `### Internal` for build, CI, refactoring with no user impact.

## Common Pitfalls

- **Missing `[Unreleased]`**: Without it, there's no place for PRs to add entries.
- **Entries too vague**: "Bug fixes" → be specific about what was fixed.
- **No dates**: Every version needs a release date.
- **Broken links**: Keep version diff links updated at the bottom.
- **Mixed user/internal changes**: Separate public API changes from internal refactors.

## Commands

```bash
# Preview changelog from git log
git log --oneline --no-merges v0.1.0..HEAD

# Generate from conventional commits (requires npx)
npx conventional-changelog -p angular -i CHANGELOG.md -s

# Tag a release
git tag -a v0.2.0 -m "Release 0.2.0"
git push origin v0.2.0
```

## Resources

- Keep a Changelog: <https://keepachangelog.com/>
- Semantic Versioning: <https://semver.org/>
- python-semantic-release: <https://python-semantic-release.readthedocs.io/>
- GitHub Releases: <https://docs.github.com/en/repositories/releasing-projects-on-github/>
