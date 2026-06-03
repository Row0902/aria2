#!/usr/bin/env bash
# ban-utils — reject _utils.py and _helpers.py modules
set -euo pipefail

found=false
while IFS= read -r -d '' f; do
  basename=$(basename "$f")
  if [[ "$basename" == "_utils.py" || "$basename" == "_helpers.py" ]]; then
    echo "❌ BANNED: $f — use a semantic module name instead (_key_utils, _parsing, _conversion, etc.)"
    found=true
  fi
done < <(find packages apps -name "_utils.py" -o -name "_helpers.py" -print0 2>/dev/null || true)

if $found; then
  exit 1
fi
echo "✅ ban-utils: no banned module names found."
