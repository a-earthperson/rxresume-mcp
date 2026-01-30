"""
MCP resource definitions for RxResume.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from textwrap import dedent
from typing import Any, Dict

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)


TOOL_SEMANTICS_DOC = dedent(
    """
    # RxResume MCP tool semantics

    General behavior
    - All tools return {"status": "success", "response": ...} or
      {"status": "error", "error": "..."}.
    - Errors are propagated from the RxResume REST API (HTTP status and
      payload are stringified).
    - Export tools return base64 payloads: {"content_type", "content_base64",
      "size_bytes"} when the API returns bytes.
    - No caching, retries, or mutation beyond the requested endpoint.

    Tool-specific notes
    - list_resumes: tags are sent as repeated "tags[]" query params; empty list
      => no tag filter.
    - list_resumes: sort is passed through verbatim (API-defined values,
      e.g. "updatedAt", "-updatedAt").
    - get_resume / get_resume_by_username: return full resume objects including
      "data".
    - create_resume: always sends tags array (empty allowed); with_sample_data
      maps to "withSampleData".
    - create_resume: returns the created resume id (string).
    - update_resume: requires at least one of name/slug/tags/data; only provided
      name/slug/tags are sent.
    - update_resume: data is validated against the local JSON schema before PUT;
      schema errors are returned to MCP.
    - update_resume: tags=None leaves tags unchanged; tags=[] clears all tags.
    - delete_resume: sends DELETE with an empty JSON body; response may be empty.
    - export_resume_pdf / export_resume_screenshot: Accept header set to
      PDF/PNG.
    - export_resume_pdf / export_resume_screenshot: if API returns JSON, it is
      forwarded as JSON.
    """
).strip()


SCHEMA_SUMMARY_DOC = dedent(
    """
    # RxResume resume schema (structure + invariants)

    Top-level
    - Required keys: picture, basics, summary, sections, customSections, metadata.
    - additionalProperties is false at the top-level and most nested objects: do
      not add extra keys.

    Cross-cutting invariants
    - Required fields must be present even if blank (e.g., website.url,
      website.label, icon fields).
    - Many rich text fields are HTML strings (summary.content, section item
      descriptions, metadata.notes).
    - URL fields require a scheme (http:// or https://).
    - All section items and custom sections require "id" (typically UUID
      strings) and "hidden" booleans.

    Sections
    - Fixed sections: profiles, experience, education, projects, skills,
      languages, interests, awards, certifications, publications, volunteer,
      references.
    - Each section object requires title, columns, hidden, and items[].
    - Item schemas are strict (no extra keys) and vary by section; see JSON
      schema for exact fields.

    Custom sections
    - customSections[] requires title, columns, hidden, id, type, items.
    - type must be one of the fixed section types; items must conform to that
      type's item schema.

    Key numeric/enum constraints
    - picture.size: 32..512; picture.rotation: 0..360; picture.aspectRatio:
      0.5..2.5.
    - picture.borderRadius: 0..100; borderWidth/shadowWidth: >= 0.
    - skills.level and languages.level: 0..5 (0 hides level indicator).
    - metadata.layout.sidebarWidth: 10..50.
    - metadata.page.format: a4 | letter | free-form.
    - metadata.typography.fontSize: 6..24; lineHeight: 0.5..4.
    """
).strip()


DESIGN_NOTES_DOC = dedent(
    """
    # RxResume design notes (templating + styling)

    - metadata.template selects a fixed template (enum: azurill, bronzor,
      chikorita, ditgar, ditto, gengar, glalie, kakuna, lapras, leafish, onyx,
      pikachu, rhyhorn).
    - metadata.layout.pages controls section placement; section ids must be
      known built-ins or custom section UUIDs; ordering determines render order.
    - metadata.layout.pages[].fullWidth=true means use only the main column;
      sidebar should be empty.
    - metadata.page.format: a4, letter, or free-form; margin/gap values are in
      points (pt) and must be >= 0.
    - metadata.typography.body/heading fonts must exist on Google Fonts;
      fontWeights are "100".."900".
    - metadata.design.colors.* are rgba(...) strings; metadata.design.level.type
      controls level rendering.
    - If metadata.design.level.type = "icon", provide metadata.design.level.icon.
    - metadata.css.enabled toggles custom CSS; when enabled, metadata.css.value
      must be valid CSS.
    - icon fields use @phosphor-icons/web; use "" to hide an icon when unsure.
    """
).strip()


def _find_resume_schema_path() -> Path | None:
    package_candidate = (
        Path(__file__).resolve().parent / "resources" / "resume-schema.json"
    )
    if package_candidate.is_file():
        return package_candidate

    return None


def _load_resume_schema() -> Dict[str, Any]:
    schema_path = _find_resume_schema_path()
    if not schema_path:
        logger.warning("Resume schema file not found for MCP resources.")
        return {
            "error": "Resume schema file not found.",
            "hint": "See rxresume://schema/summary for structure and invariants.",
        }

    try:
        return json.loads(schema_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Failed to read resume schema: %s", exc)
        return {
            "error": "Resume schema could not be loaded.",
            "hint": "See rxresume://schema/summary for structure and invariants.",
        }


def register_resources(mcp: FastMCP) -> None:
    """Register RxResume MCP resource endpoints."""

    @mcp.resource(
        "rxresume://docs/tool-semantics",
        name="rxresume_tool_semantics",
        title="RxResume MCP Tool Semantics",
        description="Behavioral constraints and response envelopes for RxResume MCP tools.",
        mime_type="text/markdown",
    )
    def get_tool_semantics() -> str:
        return TOOL_SEMANTICS_DOC

    @mcp.resource(
        "rxresume://schema/summary",
        name="rxresume_schema_summary",
        title="RxResume Resume Schema Summary",
        description="Structure and invariants for resume data objects.",
        mime_type="text/markdown",
    )
    def get_schema_summary() -> str:
        return SCHEMA_SUMMARY_DOC

    @mcp.resource(
        "rxresume://schema/resume",
        name="rxresume_resume_schema",
        title="RxResume Resume Schema (JSON Schema)",
        description="Full JSON schema for resume data objects.",
        mime_type="application/schema+json",
    )
    def get_resume_schema() -> Dict[str, Any]:
        return _load_resume_schema()

    @mcp.resource(
        "rxresume://docs/design-notes",
        name="rxresume_design_notes",
        title="RxResume Design Notes",
        description="Templating and styling constraints for schema-valid edits.",
        mime_type="text/markdown",
    )
    def get_design_notes() -> str:
        return DESIGN_NOTES_DOC
