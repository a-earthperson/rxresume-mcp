"""Register tools for listing and editing award items."""

from __future__ import annotations

from typing import List, Union

from mcp.server.fastmcp import FastMCP

from .section_item_tools import (
    register_section_item_tools,
)
from .field_adapters import (
    ScalarFieldAdapter,
    WebsiteFieldAdapter,
)
from .item_spec import FieldSpec, build_item_model, build_item_spec

AWARD_FIELDS = [
    FieldSpec(
        name="name",
        field_type=str,
        adapter=ScalarFieldAdapter(response_key="name", server_key="title"),
    ),
    FieldSpec(
        name="awarder",
        field_type=str,
        adapter=ScalarFieldAdapter(response_key="awarder"),
    ),
    FieldSpec(
        name="period",
        field_type=str,
        adapter=ScalarFieldAdapter(response_key="period", server_key="date"),
    ),
    FieldSpec(
        name="description",
        field_type=str,
        adapter=ScalarFieldAdapter(response_key="description"),
    ),
    FieldSpec(
        name="url",
        field_type=str,
        adapter=WebsiteFieldAdapter(response_key="url", server_key="website"),
    ),
]

AwardItemInput = build_item_model(
    "AwardItemInput", AWARD_FIELDS, populate_by_name=True, module=__name__
)
AwardItemsInput = Union[AwardItemInput, List[AwardItemInput]]
AwardItemIdsInput = Union[str, List[str]]

AWARD_SPEC = build_item_spec("awards", AWARD_FIELDS)


def register_award_tools(mcp: FastMCP) -> None:
    """Register tools that list or edit award items."""
    register_section_item_tools(
        mcp,
        tool_prefix="resume.section.award",
        section="awards",
        label="Awards",
        noun="award",
        spec=AWARD_SPEC,
        item_model=AwardItemInput,
        items_type=AwardItemsInput,
        item_ids_type=AwardItemIdsInput,
    )
