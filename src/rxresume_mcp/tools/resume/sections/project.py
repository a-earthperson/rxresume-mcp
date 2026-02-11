"""Register tools for listing and editing project items."""

from __future__ import annotations

from typing import List, Union

from mcp.server.fastmcp import FastMCP

from .section_item_tools import ensure_non_empty_string, register_section_item_tools
from .field_adapters import (
    NoopFieldAdapter,
    PeriodRangeAdapter,
    ScalarFieldAdapter,
    WebsiteFieldAdapter,
)
from .item_spec import FieldSpec, build_item_model, build_item_spec

PROJECT_FIELDS = [
    FieldSpec(
        name="name",
        field_type=str,
        adapter=ScalarFieldAdapter(
            response_key="name",
            server_default=" ",
            input_transform=ensure_non_empty_string,
        ),
    ),
    FieldSpec(
        name="startDate",
        field_type=str,
        adapter=NoopFieldAdapter(),
    ),
    FieldSpec(
        name="endDate",
        field_type=str,
        adapter=NoopFieldAdapter(),
    ),
    # Stored upstream as `period`, exposed as startDate/endDate.
    FieldSpec(
        name="__period",
        field_type=str,
        adapter=PeriodRangeAdapter(server_key="period"),
    ),
    FieldSpec(
        name="url",
        field_type=str,
        adapter=WebsiteFieldAdapter(response_key="url", server_key="website"),
    ),
    FieldSpec(
        name="description",
        field_type=str,
        adapter=ScalarFieldAdapter(response_key="description"),
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
