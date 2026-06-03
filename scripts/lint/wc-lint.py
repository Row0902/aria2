#!/usr/bin/env python3
"""wc-lint — enforce lines-of-code thresholds.

Checks:
  - File lines  ≤ MAX_FILE_LINES (default 200, critical 500)
  - Function lines ≤ MAX_FUNCTION_LINES (default 20)
  - Public methods per class ≤ MAX_CLASS_PUBLIC_METHODS (default 10)

Exit code: 0 if all pass, 1 if any violation (with details).
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

MAX_FILE_LINES = 200
CRITICAL_FILE_LINES = 500
MAX_FUNCTION_LINES = 20
MAX_CLASS_PUBLIC_METHODS = 10

# Directories to skip
SKIP_DIRS = {".venv", "__pycache__", ".git", ".ruff_cache", ".pytest_cache"}

errors: list[str] = []
warnings: list[str] = []


def walk_python_files(root: str) -> list[Path]:
    paths = []
    for p in Path(root).rglob("*.py"):
        if any(skip in p.parts for skip in SKIP_DIRS):
            continue
        paths.append(p)
    return paths


def check_file_lines(filepath: Path) -> None:
    with open(filepath) as f:
        lines = f.readlines()
    count = len(lines)
    rel = filepath.resolve().relative_to(Path.cwd().resolve())
    if count > CRITICAL_FILE_LINES:
        errors.append(f"[CRITICAL] {rel}: {count} lines (max {CRITICAL_FILE_LINES})")
    elif count > MAX_FILE_LINES:
        errors.append(f"[FAIL] {rel}: {count} lines (max {MAX_FILE_LINES})")
    elif count > MAX_FILE_LINES * 0.75:
        warnings.append(f"[WARN] {rel}: {count} lines (approaching limit {MAX_FILE_LINES})")


def _build_parent_map(tree: ast.AST) -> dict[int, str]:
    """Return a mapping of top-level function/method node id -> parent display name."""
    parent_map: dict[int, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    parent_map[id(item)] = node.name
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if id(node) not in parent_map:
                parent_map[id(node)] = "<module>"
    return parent_map


def check_function_lines(
    filepath: Path, node: ast.FunctionDef | ast.AsyncFunctionDef, parent_name: str
) -> None:
    """Check a single function's line count."""
    if not node.end_lineno or not node.lineno:
        return
    count = node.end_lineno - node.lineno + 1
    if count > MAX_FUNCTION_LINES:
        rel = filepath.resolve().relative_to(Path.cwd().resolve())
        errors.append(
            f"[FAIL] {rel}:{node.lineno} function `{parent_name}.{node.name}` "
            f"has {count} lines (max {MAX_FUNCTION_LINES})"
        )


def count_public_methods(class_node: ast.ClassDef) -> int:
    n = 0
    for item in class_node.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and not item.name.startswith("_"):
            n += 1
    return n


def check_file(filepath: Path) -> None:
    check_file_lines(filepath)

    try:
        with open(filepath) as f:
            source = f.read()
        tree = ast.parse(source, filename=str(filepath))
    except SyntaxError as e:
        rel = filepath.resolve().relative_to(Path.cwd().resolve())
        warnings.append(f"[SKIP] {rel}: syntax error ({e})")
        return

    parent_map = _build_parent_map(tree)

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            n = count_public_methods(node)
            if n > MAX_CLASS_PUBLIC_METHODS:
                rel = filepath.resolve().relative_to(Path.cwd().resolve())
                errors.append(
                    f"[FAIL] {rel}:{node.lineno} class `{node.name}` "
                    f"has {n} public methods (max {MAX_CLASS_PUBLIC_METHODS})"
                )
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            check_function_lines(filepath, node, parent_map.get(id(node), "<module>"))


def main() -> int:
    roots = sys.argv[1:] if len(sys.argv) > 1 else ["packages", "apps"]
    for root in roots:
        for pyfile in walk_python_files(root):
            check_file(pyfile)

    if warnings:
        for w in warnings:
            print(f"⚠️  {w}", file=sys.stderr)

    if errors:
        for e in errors:
            print(f"❌ {e}", file=sys.stderr)
        print(f"\n💥 {len(errors)} violation(s) found.", file=sys.stderr)
        return 1

    print(f"✅ wc-lint: all files within thresholds ({len(warnings)} warnings).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
