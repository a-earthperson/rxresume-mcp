"""JSON pointer parsing shared by patch and schema helpers."""

from __future__ import annotations

from typing import List

from jsonpointer import JsonPointer, JsonPointerException


def _parse_json_pointer(path: str) -> List[str]:
    """Parse RFC 6901 pointers into decoded path segments."""
    if not isinstance(path, str) or not path.startswith("/"):
        return []
    try:
        return list(JsonPointer(path).parts)
    except JsonPointerException:
        # Keep callers robust: treat invalid pointers as non-pointers.
        return []
