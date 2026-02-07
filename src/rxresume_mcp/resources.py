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
    - list_resumes: sort is passed through verbatim (API-defined values:
      "lastUpdatedAt", "createdAt", "name"). "lastUpdatedAt" sorts descending.
    - get_resume / get_resume_by_username: return full resume objects including
      "data".
    - get_resume_section: returns a focused subtree by section path
      (basics | summary | picture | metadata | sections.<type> |
      customSections | customSections.<id>). customSections returns a summary
      list (id/title/type/hidden/columns/item_count).
    - create_resume: always sends tags array (empty allowed); with_sample_data
      maps to "withSampleData".
    - create_resume: returns the created resume id (string).
    - create_resume: include_resume=true fetches and returns the full resume.
    - update_resume: requires at least one of name/slug/tags/data; only provided
      name/slug/tags are sent.
    - update_resume: data is validated against the local JSON schema before PUT;
      schema errors are returned to MCP.
    - update_resume: tags=None leaves tags unchanged; tags=[] clears all tags.
    - update_resume: name is the resume title; use data.basics.name for the
      person's name.
    - update_resume: do not send JSON Resume-style keys at the top level
      (education, employment, job_title, etc). Use data.basics and data.sections.
    - update_resume: when adding or replacing list entries (items/customSections),
      you must include required fields like id/hidden and all section-required
      fields. update_resume does not auto-generate ids.
    - HTML fields (summary.content, item descriptions, metadata.notes) must be
      HTML strings; use rxresume_html_content_style for guidance.
    - edit_section_items: builds JSON Patch ops to add/update/remove section
      items by id (built-in sections or a specific custom section). Required
      fields vary by section; consult rxresume://schema/summary.
    - edit_section_items: prepends https:// on url fields missing a scheme.
      created_item_ids is returned on add.
    - edit_custom_sections: builds JSON Patch ops to add/update/remove custom
      sections by id. custom section type must be one of the built-in section types.
    - edit_custom_sections: include items in the section payload to create in
      one call; ids are auto-generated when missing.
    - edit_custom_sections: prepends https:// on url fields missing a scheme.
      created_custom_section_id/created_item_ids are returned on add.
    - patch_resume: JSON Patch escape hatch with RxResume extensions (id-based
      paths and layout normalization). Validates RFC 6902 shape and auto-injects
      ids for add ops on items/customSections/customFields when missing.
    - edit_section_items / edit_custom_sections / patch_resume: default response
      is a minimal summary; include_result=true returns the full resume.
      result_section_path returns just a subtree from the patch result.
    - get_rxresume_docs: returns documentation snippets for tool-only clients;
      use include_content/include_schema to expand payloads.
    - get_resume_schema_fragment: returns a summarized schema fragment at a
      JSON pointer or dot path (depth-controlled). Dot paths traverse properties
      and array items (e.g., sections.experience, customSections.items).
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

    Common field mappings
    - Person name -> basics.name
    - Headline/job title -> basics.headline
    - Email/phone/location -> basics.email/phone/location
    - Website -> basics.website.url + basics.website.label
    - Social links -> sections.profiles.items (or basics.customFields)
    - Education entries -> sections.education.items
    - Employment entries -> sections.experience.items
    - Projects -> sections.projects.items
    - Skills -> sections.skills.items
    - Notes (private) -> metadata.notes (HTML string)

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


PATCH_OPS_DOC = dedent(
    """
    # RxResume JSON Patch paths (PATCH /resume/{id})

    Content type
    - application/json-patch+json (preferred) or application/json

    Allowed top-level paths
    - /name, /slug, /tags, /isPublic
    - /tags is an array; add with /tags/- and remove by index (e.g., /tags/0)
    - top-level fields cannot be removed

    Data paths
    - /data/... (resume data subtree, schema-validated)
    - Built-in sections:
      /data/sections/<section>/items/...
    - Custom sections:
      /data/customSections/...

    By-id resolution
    - Section items:
      /data/sections/<section>/items/id/<item_id>/...
    - Custom sections:
      /data/customSections/id/<custom_section_id>/...
    - Custom section items:
      /data/customSections/id/<custom_section_id>/items/id/<item_id>/...

    Auto-id injection (MCP wrapper + server normalization)
    - For add ops on items/customSections/customFields with missing ids, the
      MCP tool injects a UUID before PATCH.
    - Paths commonly used for auto-id:
      /data/sections/<section>/items/-
      /data/customSections/-
      /data/customSections/id/<custom_section_id>/items/-
      /data/basics/customFields/-

    Layout normalization (server-side)
    - When customSections are added/removed and layout is not explicitly patched,
      metadata.layout.pages[*].main/sidebar are normalized to include/remove the
      custom section ids.

    Important edge cases
    - Numeric ids are treated as array indexes unless you use the explicit
      /id/<id> form.
    - Append to arrays using "-" (e.g., /data/sections/experience/items/-).
    - "move" and "copy" cannot use a "-" path for the "from" location.
    - Forbidden path segments: __proto__, prototype, constructor.

    Section types (built-in)
    - profiles, experience, education, projects, skills, languages, interests,
      awards, certifications, publications, volunteer, references
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

    @mcp.resource(
        "rxresume://docs/patch-ops",
        name="rxresume_patch_ops",
        title="RxResume JSON Patch Paths",
        description="Allowed JSON Patch paths and by-id rules for PATCH /resume/{id}.",
        mime_type="text/markdown",
    )
    def get_patch_ops() -> str:
        return PATCH_OPS_DOC
