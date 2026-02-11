"""Register tools for listing and editing experience items."""

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

EXPERIENCE_FIELDS = [
    FieldSpec(
        name="name",
        field_type=str,
        adapter=ScalarFieldAdapter(
            response_key="name",
            server_key="company",
            server_default=" ",
            input_transform=ensure_non_empty_string,
        ),
    ),
    FieldSpec(
        name="position",
        field_type=str,
        adapter=ScalarFieldAdapter(response_key="position"),
    ),
    FieldSpec(
        name="location",
        field_type=str,
        adapter=ScalarFieldAdapter(response_key="location"),
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

ExperienceItemInput = build_item_model(
    "ExperienceItemInput", EXPERIENCE_FIELDS, populate_by_name=True, module=__name__
)
ExperienceItemsInput = Union[ExperienceItemInput, List[ExperienceItemInput]]
ExperienceItemIdsInput = Union[str, List[str]]

EXPERIENCE_SPEC = build_item_spec("experience", EXPERIENCE_FIELDS)


def register_experience_tools(mcp: FastMCP) -> None:
    """Register tools that list or edit experience items."""
    register_section_item_tools(
        mcp,
        # JSON Resume uses `work` for this section.
        tool_prefix="resume.section.work",
        section="experience",
        label="Work",
        noun="work",
        spec=EXPERIENCE_SPEC,
        item_model=ExperienceItemInput,
        items_type=ExperienceItemsInput,
        item_ids_type=ExperienceItemIdsInput,
    )
