"""Register tools for listing and editing education items."""

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
from .tool_helpers import WebsiteInput


SUMMARY_HIGHLIGHTS_FIELD = SummaryHighlightsFieldAdapter()

EDUCATION_FIELDS = [
    FieldSpec(
        name="school",
        field_type=str,
        adapter=ScalarFieldAdapter(
            input_key="school",
            server_key="school",
            response_key="school",
            default=" ",
            input_transform=ensure_non_empty_string,
        ),
    ),
    FieldSpec(
        name="degree",
        field_type=str,
        adapter=ScalarFieldAdapter(
            input_key="degree", server_key="degree", response_key="degree"
        ),
    ),
    FieldSpec(
        name="area",
        field_type=str,
        adapter=ScalarFieldAdapter(
            input_key="area", server_key="area", response_key="area"
        ),
    ),
    FieldSpec(
        name="grade",
        field_type=str,
        adapter=ScalarFieldAdapter(
            input_key="grade", server_key="grade", response_key="grade"
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
        field_type=WebsiteInput,
        alias="website",
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

EducationItemInput = build_item_model(
    "EducationItemInput", EDUCATION_FIELDS, populate_by_name=True, module=__name__
)
EducationItemsInput = Union[EducationItemInput, List[EducationItemInput]]
EducationItemIdsInput = Union[str, List[str]]

EDUCATION_SPEC = build_item_spec("education", EDUCATION_FIELDS)


def register_education_tools(mcp: FastMCP) -> None:
    """Register tools that list or edit education items."""
    register_section_item_tools(
        mcp,
        tool_prefix="resume.section.education",
        section="education",
        label="Education",
        noun="education",
        spec=EDUCATION_SPEC,
        item_model=EducationItemInput,
        items_type=EducationItemsInput,
        item_ids_type=EducationItemIdsInput,
    )
