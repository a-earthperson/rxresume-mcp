"""Register tools for listing and editing experience items."""

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

EXPERIENCE_FIELDS = [
    FieldSpec(
        name="name",
        field_type=str,
        adapter=ScalarFieldAdapter(
            input_key="name",
            server_key="company",
            response_key="name",
            default=" ",
            input_transform=ensure_non_empty_string,
        ),
    ),
    FieldSpec(
        name="position",
        field_type=str,
        adapter=ScalarFieldAdapter(
            input_key="position", server_key="position", response_key="position"
        ),
    ),
    FieldSpec(
        name="location",
        field_type=str,
        adapter=ScalarFieldAdapter(
            input_key="location", server_key="location", response_key="location"
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
        tool_prefix="resume.section.experience",
        section="experience",
        label="Experience",
        noun="experience",
        spec=EXPERIENCE_SPEC,
        item_model=ExperienceItemInput,
        items_type=ExperienceItemsInput,
        item_ids_type=ExperienceItemIdsInput,
    )
