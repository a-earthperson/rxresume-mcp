"""Normalization helpers for user-supplied payloads."""

from __future__ import annotations

import re
from typing import Any, Dict

_URL_SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")


def _normalize_url(value: str) -> str:
    """Ensure URL values include a scheme for consistent rendering."""
    if not value:
        return value
    if _URL_SCHEME_RE.match(value):
        return value
    if value.startswith("//"):
        return f"https:{value}"
    return f"https://{value}"


def _normalize_url_fields(payload: Any) -> Any:
    """Recursively normalize url keys inside dict/list payloads."""
    if isinstance(payload, dict):
        normalized: Dict[str, Any] = {}
        for key, value in payload.items():
            if key == "url" and isinstance(value, str):
                normalized[key] = _normalize_url(value)
            else:
                normalized[key] = _normalize_url_fields(value)
        return normalized
    if isinstance(payload, list):
        return [_normalize_url_fields(item) for item in payload]
    return payload
