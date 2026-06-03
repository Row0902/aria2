#!/usr/bin/env bash
# changelog-lint — verify CHANGELOG.md has [Unreleased] when src/ changes
set -euo pipefail

CHANGELOG="CHANGELOG.md"

if [ ! -f "$CHANGELOG" ]; then
  echo "❌ $CHANGELOG not found."
  exit 1
fi

# Check if any staged changes touch source directories
if git diff --cached --name-only | grep -qE "^(packages/|apps/).*\.py$"; then
  if ! grep -q "\[Unreleased\]" "$CHANGELOG" 2>/dev/null; then
    echo "❌ Source files changed but $CHANGELOG has no [Unreleased] section."
    echo "   Add an [Unreleased] entry before committing."
    exit 1
  fi
  echo "✅ changelog-lint: [Unreleased] present in $CHANGELOG."
else
  echo "⏭️  changelog-lint: no source changes, skipping."
fi
