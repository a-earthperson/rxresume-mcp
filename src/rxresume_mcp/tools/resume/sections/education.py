"""Register tools for listing and editing education items."""

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

EDUCATION_FIELDS = [
    # JSON Resume: education[].institution / studyType / score
    FieldSpec(
        name="institution",
        field_type=str,
        adapter=ScalarFieldAdapter(
            response_key="institution",
            server_key="school",
            server_default=" ",
            input_transform=ensure_non_empty_string,
        ),
    ),
    FieldSpec(
        name="studyType",
        field_type=str,
        adapter=ScalarFieldAdapter(response_key="studyType", server_key="degree"),
    ),
    FieldSpec(
        name="area",
        field_type=str,
        adapter=ScalarFieldAdapter(response_key="area"),
    ),
    FieldSpec(
        name="score",
        field_type=str,
        adapter=ScalarFieldAdapter(
            response_key="score",
            server_key="grade",
        ),
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
