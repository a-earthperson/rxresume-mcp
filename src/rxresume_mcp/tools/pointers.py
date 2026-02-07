"""JSON pointer parsing shared by patch and schema helpers."""

from __future__ import annotations

from typing import List


def _parse_json_pointer(path: str) -> List[str]:
    """Parse RFC 6901 pointers into decoded path segments."""
    if not path.startswith("/"):
        return []
    return [
        segment.replace("~1", "/").replace("~0", "~")
        for segment in path[1:].split("/")
    ]
