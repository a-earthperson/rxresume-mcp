"""Shared helpers for section item tools."""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional, Set, Type, TypeVar

from pydantic import BaseModel

from rxresume_mcp import patch_ops
from rxresume_mcp.client import RxResumeClient

from .normalize import _normalize_url_fields
from .sections import _extract_section_data, _require_resume_object

ModelT = TypeVar("ModelT", bound=BaseModel)

_DESCRIPTION_UL_RE = re.compile(r"<ul[^>]*>.*?</ul>", re.IGNORECASE | re.DOTALL)
_DESCRIPTION_LI_RE = re.compile(r"<li[^>]*>(.*?)</li>", re.IGNORECASE | re.DOTALL)
_DESCRIPTION_TAG_RE = re.compile(r"<[^>]+>")


def ensure_non_empty_string(value: Any, fallback: str = " ") -> str:
    """Return value if it is a non-empty string; otherwise fallback."""
    if isinstance(value, str) and value.strip() != "":
        return value
    return fallback


def _strip_html_tags(value: str) -> str:
    """Remove HTML tags from a string."""
    return _DESCRIPTION_TAG_RE.sub("", value).strip()


def build_summary_highlights_description(
    summary: Optional[str], highlights: Optional[List[str]]
) -> str:
    """Build a description HTML string from summary and highlights."""
    summary_value = summary.strip() if isinstance(summary, str) else ""
    highlight_items = [
        item.strip()
        for item in (highlights or [])
        if isinstance(item, str) and item.strip()
    ]
    if not summary_value and not highlight_items:
        return ""
    parts: List[str] = []
    if summary_value:
        if "<" in summary_value and ">" in summary_value:
            parts.append(summary_value)
        else:
            parts.append(f"<p>{summary_value}</p>")
    if highlight_items:
        list_items = "".join(f"<li><p>{item}</p></li>" for item in highlight_items)
        parts.append(f"<ul>{list_items}</ul>")
    return "".join(parts)


def split_summary_highlights_description(
    description: Any,
) -> tuple[Optional[str], Optional[List[str]]]:
    """Split a description HTML string into summary and highlights."""
    if not isinstance(description, str) or not description:
        return None, None
    highlights = [
        _strip_html_tags(item) for item in _DESCRIPTION_LI_RE.findall(description)
    ]
    highlights = [item for item in highlights if item]
    summary = _DESCRIPTION_UL_RE.sub("", description).strip()
    if not _strip_html_tags(summary):
        summary = ""
    summary_value = summary or None
    highlights_value = highlights or None
    return summary_value, highlights_value


def coerce_item_ids(item_ids: Any, label: str = "item_ids") -> List[str]:
    """Normalize an id or list of ids into a list of non-empty strings."""
    if isinstance(item_ids, str):
        if not item_ids:
            raise ValueError(f"{label} must not be empty")
        return [item_ids]
    if isinstance(item_ids, list):
        if not item_ids:
            raise ValueError(f"{label} list must not be empty")
        ids: List[str] = []
        for item_id in item_ids:
            if not isinstance(item_id, str) or not item_id:
                raise ValueError(f"{label} must be non-empty strings")
            ids.append(item_id)
        return ids
    raise ValueError(f"{label} must be a string or a list of strings")


def coerce_model_items(
    items: Any, model_cls: Type[ModelT], label: str = "items"
) -> List[ModelT]:
    """Normalize an item or list of items into a list of model instances."""
    if isinstance(items, model_cls):
        return [items]
    if isinstance(items, list):
        if not items:
            raise ValueError(f"{label} list must not be empty")
        normalized: List[ModelT] = []
        for item in items:
            if isinstance(item, model_cls):
                normalized.append(item)
            elif isinstance(item, dict):
                normalized.append(model_cls.model_validate(item))
            else:
                raise ValueError(f"{label} must contain objects only")
        return normalized
    if isinstance(items, dict):
        return [model_cls.model_validate(items)]
    raise ValueError(f"{label} must be an object or a list of objects")


def extract_section_items(
    resume: Dict[str, Any], section: str, *, label: str | None = None
) -> List[Any]:
    """Return the items array for a section or raise if malformed."""
    label_value = label or section.capitalize()
    section_data = _extract_section_data(resume, f"sections.{section}")["data"]
    if not isinstance(section_data, dict):
        raise ValueError(f"{label_value} section is not a JSON object")
    items = section_data.get("items")
    if not isinstance(items, list):
        raise ValueError(f"{label_value} items is not an array")
    return items


def build_section_item_update_ops(
    section: str,
    item: BaseModel,
    *,
    nested_object_fields: Iterable[str] | None = None,
    normalize_urls: bool = True,
) -> List[Dict[str, Any]]:
    """Build patch operations for a section item update."""
    payload = item.model_dump(exclude_none=True)
    item_id = payload.pop("id", None)
    if not item_id or not isinstance(item_id, str):
        raise ValueError("item.id is required for update")

    ops: List[Dict[str, Any]] = []
    nested_fields: Set[str] = set(nested_object_fields or ())
    for field in list(payload.keys()):
        if field not in nested_fields:
            continue
        nested_payload = payload.pop(field)
        if not isinstance(nested_payload, dict):
            raise ValueError(f"{field} must be an object")
        if normalize_urls:
            nested_payload = _normalize_url_fields(nested_payload)
        base = patch_ops.path_section_item_field(section, item_id, field)
        for key, value in nested_payload.items():
            ops.append(patch_ops.op_replace(f"{base}/{key}", value))

    for key, value in payload.items():
        ops.append(
            patch_ops.op_replace(
                patch_ops.path_section_item_field(section, item_id, key), value
            )
        )

    if not ops:
        raise ValueError(f"No fields provided to update for item id: {item_id}")
    return ops


async def apply_section_item_patch(
    client: RxResumeClient,
    resume_id: str,
    section: str,
    ops: List[Dict[str, Any]],
    *,
    label: str | None = None,
) -> List[Any]:
    """Patch a resume and return the updated section items."""
    validated_ops = patch_ops.validate_patch_ops(ops)
    result = await client.patch_resume(resume_id, patch_ops=validated_ops)
    resume = _require_resume_object(result)
    return extract_section_items(resume, section, label=label)
