from __future__ import annotations

from typing import Any


def get_nested_value(payload: Any, dotted_path: str) -> Any:
    current = payload
    for key in dotted_path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(key)
        if current is None:
            return None
    return current
