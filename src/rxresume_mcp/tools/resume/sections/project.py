"""Register tools for listing and editing project items."""

from __future__ import annotations

from typing import List, Union

from mcp.server.fastmcp import FastMCP

from .section_item_tools import ensure_non_empty_string, register_section_item_tools
from .field_adapters import (
    ScalarFieldAdapter,
    SummaryHighlightsFieldAdapter,
    WebsiteFieldAdapter,
)
from .item_spec import FieldSpec, build_item_model, build_item_spec

SUMMARY_HIGHLIGHTS_FIELD = SummaryHighlightsFieldAdapter()

PROJECT_FIELDS = [
    FieldSpec(
        name="name",
        field_type=str,
        adapter=ScalarFieldAdapter(
            input_key="name",
            server_key="name",
            response_key="name",
            default=" ",
            input_transform=ensure_non_empty_string,
        ),
    ),
    FieldSpec(
        name="period",
        field_type=str,
        adapter=ScalarFieldAdapter(
            input_key="period", server_key="period", response_key="period"
        ),
    ),
    FieldSpec(
        name="url",
        field_type=str,
        adapter=WebsiteFieldAdapter(
            input_key="url", server_key="website", response_key="url"
        ),
    ),
    FieldSpec(
        name="summary",
        field_type=str,
        adapter=SUMMARY_HIGHLIGHTS_FIELD,
    ),
    FieldSpec(
        name="highlights",
        field_type=List[str],
        adapter=SUMMARY_HIGHLIGHTS_FIELD,
    ),
]

ProjectItemInput = build_item_model(
    "ProjectItemInput", PROJECT_FIELDS, populate_by_name=True, module=__name__
)
ProjectItemsInput = Union[ProjectItemInput, List[ProjectItemInput]]
ProjectItemIdsInput = Union[str, List[str]]

PROJECT_SPEC = build_item_spec("projects", PROJECT_FIELDS)


def register_project_tools(mcp: FastMCP) -> None:
    """Register tools that list or edit project items."""
    register_section_item_tools(
        mcp,
        tool_prefix="resume.section.project",
        section="projects",
        label="Projects",
        noun="project",
        spec=PROJECT_SPEC,
        item_model=ProjectItemInput,
        items_type=ProjectItemsInput,
        item_ids_type=ProjectItemIdsInput,
    )
