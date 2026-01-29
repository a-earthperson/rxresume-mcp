"""
Prompt templates for RxResume MCP.

These prompts are descriptive and workflow-oriented. They do not perform any
operations; they guide agents in using tools and respecting schema constraints.
"""

from __future__ import annotations

from textwrap import dedent
from typing import Literal

from mcp.server.fastmcp import FastMCP
from pydantic import Field


def _format_target(
    resume_id: str | None, username: str | None, slug: str | None
) -> str:
    if resume_id:
        return f"resume_id={resume_id}"
    if username and slug:
        return f"username={username}, slug={slug}"
    return "missing (ask user for resume_id or username/slug)"


def register_prompts(mcp: FastMCP) -> None:
    """Register RxResume prompts on the provided FastMCP instance."""

    @mcp.prompt(
        name="rxresume_edit_workflow",
        title="RxResume Edit Workflow",
        description="Schema-safe workflow for editing RxResume resume data.",
    )
    def rxresume_edit_workflow(
        edit_goal: str = Field(
            description="Requested change in plain language.",
        ),
        resume_id: str | None = Field(
            default=None,
            description="Resume ID to edit (preferred for authenticated edits).",
        ),
        username: str | None = Field(
            default=None,
            description="Username for public resume lookup.",
        ),
        slug: str | None = Field(
            default=None,
            description="Resume slug for public resume lookup.",
        ),
        risk_tolerance: Literal["conservative", "normal", "aggressive"] = Field(
            default="normal",
            description="How aggressive to be about structural edits.",
        ),
    ) -> str:
        target = _format_target(resume_id, username, slug)
        return dedent(
            f"""
            RxResume edit workflow
            Target: {target}
            Edit goal: {edit_goal}
            Risk tolerance: {risk_tolerance}

            Steps
            1) Resolve target:
               - If resume_id is available, call get_resume(resume_id).
               - Else if username+slug are available, call get_resume_by_username.
               - Else ask the user for a target identifier.
            2) Read descriptive resources before editing:
               - rxresume://schema/summary (required fields, invariants)
               - rxresume://docs/tool-semantics (tool behavior)
               - rxresume://docs/design-notes (if touching metadata/layout)
               - rxresume://schema/resume (exact field shapes if needed)
            3) Plan the smallest possible patch:
               - Update only the subtrees you must change.
               - Preserve required fields and do not add extra keys
                 (additionalProperties=false).
            4) If editing HTML fields, apply rxresume_html_content_style.
            5) Execute update_resume with a minimal data patch.
            6) Re-fetch the resume to confirm the changes applied as intended.
            """
        ).strip()

    @mcp.prompt(
        name="rxresume_patch_template",
        title="RxResume Patch Template",
        description="Minimal patch template for update_resume payloads.",
    )
    def rxresume_patch_template(
        section: Literal[
            "picture",
            "basics",
            "summary",
            "sections",
            "customSections",
            "metadata",
        ] = Field(
            description="Top-level resume section to update.",
        ),
        intent: str = Field(
            description="Brief description of the intended change.",
        ),
    ) -> str:
        return dedent(
            f"""
            Minimal patch template
            Section: {section}
            Intent: {intent}

            Use a minimal data patch. Only include fields you intend to change.
            Preserve all required fields for any object you touch.

            Example (shape only):
            {{
              "data": {{
                "{section}": {{
                  "...": "..."
                }}
              }}
            }}

            Notes
            - For sections, prefer patching a specific subsection:
              data.sections.experience, data.sections.skills, etc.
            - For customSections, keep the item schema aligned with the section type.
            - Do not introduce keys not present in the JSON schema.
            """
        ).strip()

    @mcp.prompt(
        name="rxresume_design_guardrails",
        title="RxResume Design Guardrails",
        description="Constraints for template, layout, and design edits.",
    )
    def rxresume_design_guardrails(
        change_type: Literal[
            "template", "layout", "typography", "css", "colors", "levels"
        ] = Field(
            description="Type of design change requested.",
        ),
    ) -> str:
        return dedent(
            f"""
            Design guardrails
            Change type: {change_type}

            Template
            - metadata.template must be one of:
              azurill, bronzor, chikorita, ditgar, ditto, gengar, glalie,
              kakuna, lapras, leafish, onyx, pikachu, rhyhorn.

            Layout
            - metadata.layout.pages[].main/sidebar must reference built-in section
              ids or custom section UUIDs.
            - fullWidth=true implies an empty sidebar for that page.
            - metadata.layout.sidebarWidth must be 10..50.

            Typography
            - metadata.typography.*.fontFamily must exist on Google Fonts.
            - fontWeights are strings "100".."900".
            - fontSize 6..24, lineHeight 0.5..4.

            Colors and levels
            - metadata.design.colors.* are rgba(r,g,b,a) strings.
            - metadata.design.level.type in:
              hidden, circle, square, rectangle, rectangle-full, progress-bar, icon.
            - If level.type=icon, provide metadata.design.level.icon.

            CSS
            - If metadata.css.enabled is true, metadata.css.value must be valid CSS.
            - Avoid inline styles in HTML unless CSS overrides are deliberate.
            """
        ).strip()

    @mcp.prompt(
        name="rxresume_html_content_style",
        title="RxResume HTML Content Style",
        description="Guidelines for HTML fields in resume content.",
    )
    def rxresume_html_content_style(
        field: str = Field(
            description="HTML field being edited (e.g., summary.content).",
        ),
    ) -> str:
        return dedent(
            f"""
            HTML content guidelines
            Field: {field}

            - Use minimal, semantic HTML:
              <p>, <ul>, <li>, <strong>, <em>, <a>.
            - Keep content concise to avoid layout overflow.
            - Use absolute URLs with http:// or https:// in links.
            - Avoid inline styles unless CSS overrides are explicitly enabled.
            - Prefer lists for bullet content; avoid nested lists unless required.
            """
        ).strip()

    @mcp.prompt(
        name="rxresume_custom_section_blueprint",
        title="RxResume Custom Section Blueprint",
        description="How to create or edit customSections safely.",
    )
    def rxresume_custom_section_blueprint(
        section_type: Literal[
            "profiles",
            "experience",
            "education",
            "projects",
            "skills",
            "languages",
            "interests",
            "awards",
            "certifications",
            "publications",
            "volunteer",
            "references",
        ] = Field(
            description="Custom section type (determines item schema).",
        ),
        title: str = Field(description="Section title."),
        column_count: int = Field(
            description="Number of columns to span.",
            ge=1,
            le=4,
        ),
        item_count: int = Field(
            description="Number of items to include.",
            ge=0,
        ),
    ) -> str:
        return dedent(
            f"""
            Custom section blueprint
            Type: {section_type}
            Title: {title}
            Columns: {column_count}
            Item count: {item_count}

            Requirements
            - customSections[] entry must include:
              title, columns, hidden, id, type, items.
            - id should be a UUID string.
            - type must match the item schema for {section_type}.
            - Each item requires id and hidden and the full schema for the type.
            - Do not add extra keys (additionalProperties=false).

            Example (shape only):
            {{
              "title": "{title}",
              "columns": {column_count},
              "hidden": false,
              "id": "<uuid>",
              "type": "{section_type}",
              "items": [
                {{
                  "id": "<uuid>",
                  "hidden": false
                  // add remaining required fields for the {section_type} item schema
                }}
              ]
            }}
            """
        ).strip()
