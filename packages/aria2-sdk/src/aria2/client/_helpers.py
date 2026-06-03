"""Internal helpers for the aria2 client — key conversion utilities."""

from __future__ import annotations

from typing import Any


def to_snake_case(camel: str) -> str:
    """Convert camelCase to snake_case."""
    result = [camel[0].lower()]
    for ch in camel[1:]:
        if ch.isupper():
            result.append("_")
            result.append(ch.lower())
        else:
            result.append(ch)
    return "".join(result)


def snake_keys(d: dict[str, Any]) -> dict[str, Any]:
    """Recursively convert all dict keys in a structure to snake_case."""
    if not isinstance(d, dict):
        return d
    result: dict[str, Any] = {}
    for k, v in d.items():
        key = to_snake_case(k)
        if isinstance(v, dict):
            result[key] = snake_keys(v)
        elif isinstance(v, list):
            result[key] = [snake_keys(item) if isinstance(item, dict) else item for item in v]
        else:
            result[key] = v
    return result
