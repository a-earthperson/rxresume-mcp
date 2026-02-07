"""Documentation registry for tool-only clients."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict

from rxresume_mcp import resources as rx_resources


def _doc_registry() -> Dict[str, Dict[str, Any]]:
    """Return the map of documentation assets exposed via tools."""
    return {
        "tool-semantics": {
            "title": "RxResume MCP Tool Semantics",
            "mime_type": "text/markdown",
            "content": rx_resources.TOOL_SEMANTICS_DOC,
        },
        "schema-summary": {
            "title": "RxResume Resume Schema Summary",
            "mime_type": "text/markdown",
            "content": rx_resources.SCHEMA_SUMMARY_DOC,
        },
        "patch-ops": {
            "title": "RxResume JSON Patch Paths",
            "mime_type": "text/markdown",
            "content": rx_resources.PATCH_OPS_DOC,
        },
        "design-notes": {
            "title": "RxResume Design Notes",
            "mime_type": "text/markdown",
            "content": rx_resources.DESIGN_NOTES_DOC,
        },
        "resume-schema": {
            "title": "RxResume Resume Schema (JSON Schema)",
            "mime_type": "application/schema+json",
            "content": rx_resources._load_resume_schema(),
        },
    }


def _hash_content(content: Any) -> tuple[str, int]:
    """Compute a stable hash/size pair for doc payloads."""
    if isinstance(content, str):
        payload = content.encode("utf-8")
        return hashlib.sha256(payload).hexdigest(), len(content)
    payload = json.dumps(content, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest(), len(payload.decode("utf-8"))
