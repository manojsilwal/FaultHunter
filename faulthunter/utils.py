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


def find_first_key(payload: Any, candidate_keys: set[str], prefix: str = "") -> tuple[str | None, Any]:
    if isinstance(payload, dict):
        for key, value in payload.items():
            path = f"{prefix}.{key}" if prefix else key
            if key in candidate_keys and value is not None:
                return path, value
            found_path, found_value = find_first_key(value, candidate_keys, path)
            if found_path is not None:
                return found_path, found_value
    elif isinstance(payload, list):
        for idx, value in enumerate(payload):
            path = f"{prefix}[{idx}]" if prefix else f"[{idx}]"
            found_path, found_value = find_first_key(value, candidate_keys, path)
            if found_path is not None:
                return found_path, found_value
    return None, None
