---
name: gh
description: "Trigger: gh, GitHub CLI, GitHub, PR, issue, release, repo, workflow, GitHub Actions, gh pr, gh issue, gh release, gh workflow. GitHub CLI — manage repositories, PRs, issues, releases, and workflows from the command line."
license: Apache-2.0
metadata:
  author: gentleman-programming
  version: "1.0"
---

## When to Use

- Creating, reviewing, and merging pull requests from the terminal
- Managing GitHub issues (list, view, create, close)
- Creating and managing GitHub releases
- Running and monitoring GitHub Actions workflows
- Cloning, forking, and managing repositories
- Authenticating with GitHub (SSH, token, OIDC)
- Creating and managing gists
- Browsing repos, issues, and PRs in the browser
- Triggering workflow_dispatch events

## Critical Patterns

### Authentication

```bash
# Login (interactive — browser OAuth)
gh auth login

# Login with token (CI/headless)
gh auth login --with-token < ~/.gh_token

# Login with SSH key
gh auth login --hostname github.com --git-protocol ssh

# Check status
gh auth status

# Logout
gh auth logout

# View active account
gh auth status --show-token  # Shows token (use with care!)
```

### Working with PRs

```bash
# List PRs
gh pr list                              # Open PRs
gh pr list --state merged               # Merged PRs
gh pr list --state closed               # Closed PRs
gh pr list --author @me                 # Your PRs
gh pr list --label "bug"                # By label
gh pr list --base main                  # PRs targeting main
gh pr list --limit 20                   # Limit results
gh pr list --json number,title,author,createdAt  # Custom output

# View PR
gh pr view 42                           # View PR #42
gh pr view 42 --comments                # With comments
gh pr view --web                        # Open in browser

# Create PR
gh pr create --title "feat: add tell_status" \
  --body "Add download status polling" \
  --base main \
  --assignee @me \
  --label enhancement

gh pr create --fill                     # Use commit messages as title/body
gh pr create --draft                    # Create as draft

# Checkout PR locally
gh pr checkout 42

# Review PR
gh pr review 42 --approve               # Approve
gh pr review 42 --comment --body "LGTM" # Comment
gh pr review 42 --changes-requested --body "Fix this"  # Request changes

# Merge PR
gh pr merge 42                          # Merge (default: create merge commit)
gh pr merge 42 --squash                 # Squash and merge
gh pr merge 42 --rebase                 # Rebase and merge
gh pr merge 42 --delete-branch          # Delete branch after merge

# Diff
gh pr diff 42                           # Show diff
gh pr diff 42 --name-only               # Changed files only

# Close
gh pr close 42
gh pr reopen 42
```

### Working with Issues

```bash
gh issue list                           # Open issues
gh issue list --state closed            # Closed issues
gh issue list --label "bug"             # By label
gh issue list --assignee @me            # Assigned to you
gh issue list --json number,title       # Custom output

gh issue view 42                        # View issue #42
gh issue view 42 --comments             # With comments
gh issue view --web                     # Open in browser

gh issue create --title "Bug: timeout on slow connections" \
  --body "Steps to reproduce: ..." \
  --label bug \
  --assignee @me

gh issue close 42                       # Close
gh issue reopen 42                      # Reopen
gh issue comment 42 --body "Fixed in #43"  # Add comment
```

### Working with Releases

```bash
# List releases
gh release list                         # All releases
gh release list --limit 5               # Last 5

# View release
gh release view v0.1.0                  # View specific release
gh release view --web                   # Open in browser

# Create release
gh release create v0.1.0 \
  --title "v0.1.0" \
  --notes "Initial release" \
  --target main

# Create release with assets
gh release create v0.1.0 dist/*.whl dist/*.tar.gz \
  --title "v0.1.0" \
  --notes-file CHANGELOG.md

# Create pre-release
gh release create v1.0.0-rc.1 \
  --prerelease \
  --title "v1.0.0-rc.1" \
  --notes "Release candidate"

# Create draft
gh release create v0.2.0 --draft

# Upload assets to existing release
gh release upload v0.1.0 dist/aria2-0.1.0-py3-none-any.whl

# Download assets from release
gh release download v0.1.0              # All assets
gh release download v0.1.0 --pattern "*.whl"  # Filter by pattern

# Delete release
gh release delete v0.1.0                # Also prompt to delete tag

# Verify attestation
gh release verify v0.1.0               # Verify attestation (sigstore)
```

### Working with Repos

```bash
# View repo
gh repo view                            # Current repo
gh repo view Row0902/aria2              # Specific repo
gh repo view --web                      # Open in browser
gh repo view --json name,description,url,stargazersCount  # Custom output

# Clone
gh repo clone Row0902/aria2             # Clone via SSH (preferred)
gh repo clone Row0902/aria2 -- --depth 1  # Shallow clone

# Fork
gh repo fork                            # Fork to your account
gh repo fork --clone                    # Fork and clone

# Create
gh repo create my-new-project \
  --public \
  --description "My project" \
  --clone

# Info
gh repo sync                            # Sync local with remote
gh repo --help                          # Full repo commands
```

### Working with Workflows

```bash
# List workflows
gh workflow list                        # All workflows
gh workflow list --all                  # Including disabled

# Run workflow
gh workflow run build-aria2.yml \
  --ref main \
  --field version=release-1.37.0

# View workflow runs
gh run list                             # Recent runs
gh run list --workflow=quality.yml      # Filter by workflow
gh run list --status=failure            # Failed runs

# View run details
gh run view                             # Most recent run
gh run view 1234567890                  # Specific run
gh run view --log                       # View logs

# Monitor run
gh run watch 1234567890                 # Watch in real-time

# Cancel/rerun
gh run cancel 1234567890
gh run rerun 1234567890

# Download artifacts
gh run download 1234567890              # All artifacts
gh run download 1234567890 --name dist  # Specific artifact
```

### GitHub API (gh api)

```bash
# GET
gh api repos/Row0902/aria2             # GET /repos/{owner}/{repo}
gh api repos/Row0902/aria2/releases    # List releases

# POST
gh api repos/Row0902/aria2/releases \
  --method POST \
  --field tag_name=v0.2.0 \
  --field name="v0.2.0"

# With jq filtering
gh api repos/Row0902/aria2/releases \
  --jq '.[].tag_name'                  # Extract all tag names

# DELETE
gh api repos/Row0902/aria2/releases/1234567 --method DELETE
```

### Configuration

```bash
# Set defaults
gh config set git_protocol ssh          # Use SSH for git
gh config set editor vim                # Default editor
gh config set browser firefox           # Default browser

# View config
gh config list                          # All config
gh config get git_protocol              # Specific key

# Hosts
gh config set --host github.com git_protocol ssh
```

### Shell Integration

```bash
# Shell completion
gh completion -s bash > ~/.gh_completion.bash
source ~/.gh_completion.bash

# Aliases
gh alias set prs 'pr list --state open --limit 20'
gh alias set bugs 'issue list --label bug'
gh alias set co 'pr checkout'
```

### Common Workflows for This Project

```bash
# Create PR from feature branch
git checkout -b feat/add-timeout
# ... make changes ...
git add -A && git commit -m "feat: add configurable timeout"
git push -u origin HEAD
gh pr create --fill --base main --label enhancement

# Review PR
gh pr checkout 42
gh pr diff 42
gh pr review 42 --approve

# Merge and cleanup
gh pr merge 42 --squash --delete-branch

# Create release
uv version patch
git add -A && git commit -m "chore: bump to 0.1.1"
git tag v0.1.1
git push --atomic origin main v0.1.1
gh release create v0.1.1 \
  --title "v0.1.1" \
  --notes-file CHANGELOG.md

# Run CI workflow manually
gh workflow run build-aria2.yml --field version=release-1.37.0

# Check CI status
gh run list --workflow=quality.yml --limit 3 --json status,conclusion,headBranch
```

### CI Integration

```yaml
# In GitHub Actions, gh is pre-installed and authenticated
steps:
  - run: gh pr comment ${{ github.event.pull_request.number }} \
      --body "Coverage report: see artifacts"
    env:
      GH_TOKEN: ${{ github.token }}
```

### Best Practices for SDKs

#### 1. Use `gh pr create --fill`
Fills title and body from commit messages (conventional commits). Saves time.

#### 2. Review PRs from the terminal
```bash
gh pr diff 42 | less              # Quick review without opening browser
```

#### 3. Automate releases with gh
```bash
gh release create v0.2.0 dist/* --title "v0.2.0" --notes-file CHANGELOG.md
```

#### 4. Link issues in PRs
```bash
gh pr create --fill --body "Closes #42"
```

#### 5. Use `gh run watch` for CI debugging
```bash
gh workflow run quality.yml
gh run watch
```

#### 6. Use `gh api` for complex queries
```bash
# Get all open PRs with their CI status
gh api repos/Row0902/aria2/pulls --jq '.[].number'
```

## Common Pitfalls

- **Not authenticated**: `gh auth status` fails → `gh auth login` (interactive) or token.
- **SSH vs HTTPS**: Set `gh config set git_protocol ssh` to avoid password prompts.
- **`gh pr create` without branch**: Must be on a feature branch (not main).
- **Release without tag**: `gh release create` creates the tag if it doesn't exist, but better to tag first.
- **Token permissions**: For CI, use `${{ github.token }}` with limited scope, not a PAT.
- **`gh run download` needs run ID**: Use `gh run download 1234567890` or `gh run download $(gh run list --limit 1 --json databaseId --jq '.[0].databaseId')`.
- **`gh` not in PATH**: On GitHub Actions runners, `gh` is pre-installed. Locally, install via `brew install gh`.

## Commands

```bash
# ── Auth ─────────────────────────────────────────────
gh auth login                       # Interactive login
gh auth status                      # Check auth

# ── PRs ──────────────────────────────────────────────
gh pr create --fill                 # Create PR
gh pr list                          # Open PRs
gh pr view 42                       # View PR
gh pr checkout 42                   # Checkout PR
gh pr review 42 --approve           # Approve
gh pr merge 42 --squash             # Squash and merge

# ── Issues ───────────────────────────────────────────
gh issue create                     # Create issue
gh issue list                       # Open issues
gh issue view 42                    # View issue

# ── Releases ─────────────────────────────────────────
gh release create v0.1.0 --notes "..."  # Create release
gh release list                     # List releases
gh release download v0.1.0         # Download assets

# ── Workflows ────────────────────────────────────────
gh workflow run quality.yml         # Trigger workflow
gh run list                         # Recent runs
gh run watch                        # Watch in real-time
gh run download                     # Download artifacts

# ── API ──────────────────────────────────────────────
gh api repos/Row0902/aria2         # Raw API call

# ── Info ─────────────────────────────────────────────
gh --version                        # Show version
gh <command> --help                 # Command help
```

## Resources

- GitHub CLI manual: <https://cli.github.com/manual/>
- GitHub: <https://github.com/cli/cli>
- Release notes: <https://github.com/cli/cli/releases>
- Authenticating: <https://cli.github.com/manual/gh_auth_login>
- API reference: <https://docs.github.com/en/rest>
