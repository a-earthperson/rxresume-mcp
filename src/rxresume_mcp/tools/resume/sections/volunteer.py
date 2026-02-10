"""Register tools for listing and editing volunteer items."""

from __future__ import annotations

from typing import List, Union

from mcp.server.fastmcp import FastMCP

from .section_item_tools import ensure_non_empty_string, register_section_item_tools
from .field_adapters import (
    ScalarFieldAdapter,
    WebsiteFieldAdapter,
)
from .item_spec import FieldSpec, build_item_model, build_item_spec

VOLUNTEER_FIELDS = [
    FieldSpec(
        name="name",
        field_type=str,
        adapter=ScalarFieldAdapter(
            response_key="name",
            server_key="organization",
            server_default=" ",
            input_transform=ensure_non_empty_string,
        ),
    ),
    FieldSpec(
        name="location",
        field_type=str,
        adapter=ScalarFieldAdapter(response_key="location"),
    ),
    FieldSpec(
        name="period",
        field_type=str,
        adapter=ScalarFieldAdapter(response_key="period"),
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

VolunteerItemInput = build_item_model(
    "VolunteerItemInput", VOLUNTEER_FIELDS, populate_by_name=True, module=__name__
)
VolunteerItemsInput = Union[VolunteerItemInput, List[VolunteerItemInput]]
VolunteerItemIdsInput = Union[str, List[str]]

VOLUNTEER_SPEC = build_item_spec("volunteer", VOLUNTEER_FIELDS)


def register_volunteer_tools(mcp: FastMCP) -> None:
    """Register tools that list or edit volunteer items."""
    register_section_item_tools(
        mcp,
        tool_prefix="resume.section.volunteer",
        section="volunteer",
        label="Volunteer",
        noun="volunteer",
        spec=VOLUNTEER_SPEC,
        item_model=VolunteerItemInput,
        items_type=VolunteerItemsInput,
        item_ids_type=VolunteerItemIdsInput,
    )
