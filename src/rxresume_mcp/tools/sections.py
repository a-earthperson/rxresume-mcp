"""Helpers for validating and locating resume sections and items."""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from rxresume_mcp import patch_ops


def _require_resume_object(payload: Any) -> Dict[str, Any]:
    """Assert that a resume payload is a JSON object."""
    if not isinstance(payload, dict):
        raise ValueError("Resume payload is not a JSON object")
    return payload


def _require_resume_data(resume: Dict[str, Any]) -> Dict[str, Any]:
    """Assert that resume data is present as a JSON object."""
    data = resume.get("data")
    if not isinstance(data, dict):
        raise ValueError("Resume data is not a JSON object")
    return data


def _ensure_section_type(section: str) -> None:
    """Guard section names against the schema-backed section types."""
    if section not in patch_ops.SECTION_TYPES:
        allowed = ", ".join(patch_ops.SECTION_TYPES)
        raise ValueError(f"Unknown section type: {section}. Expected one of: {allowed}")


def _ensure_custom_section_type(section_type: Any) -> str:
    """Validate and return a custom section type value."""
    if not isinstance(section_type, str) or not section_type:
        raise ValueError("section.type must be a non-empty string")
    if section_type not in patch_ops.SECTION_TYPES:
        allowed = ", ".join(patch_ops.SECTION_TYPES)
        raise ValueError(f"section.type must be one of: {allowed}")
    return section_type


def _find_custom_section(data: Dict[str, Any], custom_section_id: str) -> Dict[str, Any]:
    """Find a custom section by id or raise if missing."""
    custom_sections = data.get("customSections")
    if not isinstance(custom_sections, list):
        raise ValueError("Resume customSections is not an array")
    for section in custom_sections:
        if isinstance(section, dict) and section.get("id") == custom_section_id:
            return section
    raise ValueError(f"Custom section not found: {custom_section_id}")


def _custom_section_exists(data: Dict[str, Any], custom_section_id: str) -> bool:
    """Check for a custom section id without throwing."""
    custom_sections = data.get("customSections")
    if not isinstance(custom_sections, list):
        return False
    for section in custom_sections:
        if isinstance(section, dict) and section.get("id") == custom_section_id:
            return True
    return False


def _summarize_custom_sections(custom_sections: List[Any]) -> List[Dict[str, Any]]:
    """Return lightweight metadata so list responses stay compact."""
    summaries: List[Dict[str, Any]] = []
    for section in custom_sections:
        if not isinstance(section, dict):
            continue
        items = section.get("items")
        summaries.append(
            {
                "id": section.get("id"),
                "title": section.get("title"),
                "type": section.get("type"),
                "hidden": section.get("hidden"),
                "columns": section.get("columns"),
                "item_count": len(items) if isinstance(items, list) else 0,
            }
        )
    return summaries


def _find_item(items: Any, item_id: str) -> Optional[Dict[str, Any]]:
    """Locate a section item by id, returning None if not found."""
    if not isinstance(items, list):
        return None
    for item in items:
        if isinstance(item, dict) and item.get("id") == item_id:
            return item
    return None


def _ensure_object_payload(value: Any, label: str) -> Dict[str, Any]:
    """Validate object-shaped payloads and return a shallow copy."""
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return dict(value)


def _ensure_item_id(item: Dict[str, Any], created_ids: List[str]) -> Dict[str, Any]:
    """Add an id to item payloads so patch operations can target them."""
    if "id" not in item or not item.get("id"):
        new_id = str(uuid.uuid4())
        item = dict(item)
        item["id"] = new_id
        created_ids.append(new_id)
    return item


def _ensure_item_ids(items: Any, created_ids: List[str]) -> Any:
    """Normalize a list of items so each dict has an id."""
    if not isinstance(items, list):
        return items
    normalized: List[Any] = []
    for item in items:
        if isinstance(item, dict):
            normalized.append(_ensure_item_id(item, created_ids))
        else:
            normalized.append(item)
    return normalized


def _extract_section_data(resume: Dict[str, Any], section_path: str) -> Dict[str, Any]:
    """Return a focused subtree of resume data based on a section path."""
    data = _require_resume_data(resume)
    parts = section_path.split(".")
    if parts == ["basics"]:
        section_data = data.get("basics")
    elif parts == ["summary"]:
        section_data = data.get("summary")
    elif parts == ["picture"]:
        section_data = data.get("picture")
    elif parts == ["metadata"]:
        section_data = data.get("metadata")
    elif len(parts) == 2 and parts[0] == "sections":
        section_type = parts[1]
        _ensure_section_type(section_type)
        section_data = data.get("sections", {}).get(section_type)
    elif parts == ["customSections"]:
        custom_sections = data.get("customSections")
        if not isinstance(custom_sections, list):
            raise ValueError("Resume customSections is not an array")
        section_data = _summarize_custom_sections(custom_sections)
    elif len(parts) == 2 and parts[0] == "customSections":
        section_data = _find_custom_section(data, parts[1])
    else:
        raise ValueError(
            "Invalid section_path. Use basics, summary, picture, metadata, "
            "sections.<type>, customSections, or customSections.<id>."
        )

    if section_data is None:
        raise ValueError(f"Section not found for path: {section_path}")

    return {
        "section_path": section_path,
        "data": section_data,
    }
