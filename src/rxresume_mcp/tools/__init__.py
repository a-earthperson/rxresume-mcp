"""Tooling helpers and MCP tool registrations."""

from __future__ import annotations

import uuid as uuid

from .core import AppContext, app_lifespan, execute_rxresume_operation, format_response, _encode_binary
from .resume.sections.normalize import (
    _URL_SCHEME_RE,
    _normalize_url,
    _normalize_url_fields,
)
from .patching import _auto_id_patch_ops, _build_summary
from .pointers import _parse_json_pointer
from .registry import register_tools
from .schema import (
    _parse_schema_pointer,
    _resolve_schema_dot_path,
    _resolve_schema_dot_segment,
    _resolve_schema_path,
    _resolve_schema_ref,
    _summarize_schema_node,
)
from .resume.sections.sections import (
    _custom_section_exists,
    _ensure_custom_section_type,
    _ensure_item_id,
    _ensure_item_ids,
    _ensure_object_payload,
    _ensure_section_type,
    _extract_section_data,
    _find_custom_section,
    _find_item,
    _require_resume_data,
    _require_resume_object,
    _summarize_custom_sections,
)

__all__ = [
    "AppContext",
    "app_lifespan",
    "execute_rxresume_operation",
    "register_tools",
    "format_response",
    "_encode_binary",
    "_URL_SCHEME_RE",
    "_require_resume_object",
    "_require_resume_data",
    "_ensure_section_type",
    "_ensure_custom_section_type",
    "_ensure_object_payload",
    "_find_custom_section",
    "_custom_section_exists",
    "_summarize_custom_sections",
    "_find_item",
    "_ensure_item_id",
    "_ensure_item_ids",
    "_normalize_url",
    "_normalize_url_fields",
    "_parse_json_pointer",
    "_auto_id_patch_ops",
    "_build_summary",
    "_extract_section_data",
    "_parse_schema_pointer",
    "_resolve_schema_path",
    "_resolve_schema_dot_path",
    "_resolve_schema_dot_segment",
    "_resolve_schema_ref",
    "_summarize_schema_node",
    "uuid",
]
