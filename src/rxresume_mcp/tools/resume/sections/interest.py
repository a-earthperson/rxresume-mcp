"""Register tools for listing and editing interest items."""

from __future__ import annotations

from typing import List, Union

from mcp.server.fastmcp import FastMCP

from .section_item_tools import ensure_non_empty_string, register_section_item_tools
from .field_adapters import ScalarFieldAdapter, SuppressedFieldAdapter
from .item_spec import FieldSpec, build_item_model, build_item_spec

INTEREST_FIELDS = [
    FieldSpec(
        name="icon",
        field_type=str,
        adapter=SuppressedFieldAdapter(server_key="icon", default=""),
    ),
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
        name="keywords",
        field_type=List[str],
        adapter=ScalarFieldAdapter(
            input_key="keywords",
            server_key="keywords",
            response_key="keywords",
            default=[],
        ),
    ),
]

InterestItemInput = build_item_model(
    "InterestItemInput", INTEREST_FIELDS, module=__name__
)
InterestItemsInput = Union[InterestItemInput, List[InterestItemInput]]
InterestItemIdsInput = Union[str, List[str]]

INTEREST_SPEC = build_item_spec("interests", INTEREST_FIELDS)


def register_interest_tools(mcp: FastMCP) -> None:
    """Register tools that list or edit interest items."""
    register_section_item_tools(
        mcp,
        tool_prefix="resume.section.interest",
        section="interests",
        label="Interests",
        noun="interest",
        spec=INTEREST_SPEC,
        item_model=InterestItemInput,
        items_type=InterestItemsInput,
        item_ids_type=InterestItemIdsInput,
    )
