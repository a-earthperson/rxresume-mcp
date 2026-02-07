"""JSON Patch helpers and patch summary shaping."""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from .pointers import _parse_json_pointer


def _auto_id_patch_ops(
    ops: List[Dict[str, Any]],
) -> tuple[List[Dict[str, Any]], List[str]]:
    """Inject ids for known append paths so callers can reference new items."""
    created_ids: List[str] = []
    normalized_ops: List[Dict[str, Any]] = []

    for op in ops:
        if op.get("op") == "add":
            path = op.get("path")
            value = op.get("value")
            if isinstance(path, str) and isinstance(value, dict):
                segments = _parse_json_pointer(path)
                is_section_item_append = (
                    len(segments) == 5
                    and segments[0] == "data"
                    and segments[1] == "sections"
                    and segments[3] == "items"
                    and segments[4] == "-"
                )
                is_custom_section_append = (
                    len(segments) == 3
                    and segments[0] == "data"
                    and segments[1] == "customSections"
                    and segments[2] == "-"
                )
                is_custom_section_item_append = (
                    len(segments) == 6
                    and segments[0] == "data"
                    and segments[1] == "customSections"
                    and segments[2] == "id"
                    and segments[4] == "items"
                    and segments[5] == "-"
                )
                is_custom_field_append = (
                    len(segments) == 4
                    and segments[0] == "data"
                    and segments[1] == "basics"
                    and segments[2] == "customFields"
                    and segments[3] == "-"
                )

                if (
                    is_section_item_append
                    or is_custom_section_append
                    or is_custom_section_item_append
                    or is_custom_field_append
                ):
                    if not value.get("id"):
                        new_id = str(uuid.uuid4())
                        value = dict(value)
                        value["id"] = new_id
                        created_ids.append(new_id)
                        op = dict(op)
                        op["value"] = value
        normalized_ops.append(op)

    return normalized_ops, created_ids


def _build_summary(
    resume_id: str,
    ops: List[Dict[str, Any]],
    created_ids: List[str],
    *,
    include_result: bool,
    result: Any,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Shape a consistent patch summary for tool responses."""
    summary = {
        "resume_id": resume_id,
        "applied_ops": ops,
        "changed_paths": [op.get("path") for op in ops if "path" in op],
        "created_ids": created_ids,
    }
    if include_result:
        summary["resume"] = result
    if extra:
        summary.update(extra)
    return summary
