"""Small shared helpers for MCP tools."""

from __future__ import annotations

from typing import Dict, Optional, Union, cast

from pydantic import BaseModel

from .normalize import _normalize_url_fields


class WebsiteInput(BaseModel):
    model_config = {"extra": "forbid"}

    url: Optional[str] = None
    label: Optional[str] = None


WebsiteInputLike = Union[str, Dict[str, str], WebsiteInput]


def coerce_website_input(
    value: WebsiteInputLike, *, require_url: bool = False
) -> Dict[str, str]:
    """Normalize website input into the schema-required shape."""
    if isinstance(value, WebsiteInput):
        payload = value.model_dump(exclude_none=True)
    elif isinstance(value, str):
        payload = {"url": value}
    elif isinstance(value, dict):
        payload = WebsiteInput.model_validate(value).model_dump(exclude_none=True)
    else:
        raise ValueError("website must be a string or an object with url/label")

    url = payload.get("url")
    label = payload.get("label", "")
    if label is None:
        label = ""
    if not isinstance(label, str):
        raise ValueError("website.label must be a string")
    if url is None:
        url = ""
    if not isinstance(url, str):
        raise ValueError("website.url must be a string")
    if require_url and not url:
        raise ValueError("website.url must be a non-empty string")
    return {"url": url, "label": label}


def normalize_website_payload(
    value: Optional[WebsiteInputLike],
    *,
    default_url: str = "",
    default_label: str = "",
) -> Dict[str, str]:
    """Merge website input with defaults and return a normalized dict."""
    normalized = {"url": default_url, "label": default_label}
    if value is None:
        return normalized
    normalized.update(coerce_website_input(value, require_url=False))
    return normalized


def normalize_website_for_patch(value: Optional[WebsiteInputLike]) -> Dict[str, str]:
    """Normalize website input and ensure URL schemes are present."""
    payload = normalize_website_payload(value)
    return cast(Dict[str, str], _normalize_url_fields(payload))
