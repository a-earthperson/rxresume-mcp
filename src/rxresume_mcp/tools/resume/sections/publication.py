"""Register tools for listing and editing publication items."""

from __future__ import annotations

from typing import List, Union

from mcp.server.fastmcp import FastMCP

from .section_item_tools import register_section_item_tools
from .field_adapters import (
    ScalarFieldAdapter,
    WebsiteFieldAdapter,
)
from .item_spec import FieldSpec, build_item_model, build_item_spec

PUBLICATION_FIELDS = [
    FieldSpec(
        name="name",
        field_type=str,
        adapter=ScalarFieldAdapter(response_key="name", server_key="title"),
    ),
    FieldSpec(
        name="publisher",
        field_type=str,
        adapter=ScalarFieldAdapter(response_key="publisher"),
    ),
    FieldSpec(
        name="releaseDate",
        field_type=str,
        adapter=ScalarFieldAdapter(response_key="releaseDate", server_key="date"),
    ),
    FieldSpec(
        name="url",
        field_type=str,
        adapter=WebsiteFieldAdapter(response_key="url", server_key="website"),
    ),
    FieldSpec(
        name="summary",
        field_type=str,
        adapter=ScalarFieldAdapter(response_key="summary", server_key="description"),
    ),
]

PublicationItemInput = build_item_model(
    "PublicationItemInput",
    PUBLICATION_FIELDS,
    populate_by_name=True,
    module=__name__,
)
PublicationItemsInput = Union[PublicationItemInput, List[PublicationItemInput]]
PublicationItemIdsInput = Union[str, List[str]]

PUBLICATION_SPEC = build_item_spec("publications", PUBLICATION_FIELDS)


def register_publication_tools(mcp: FastMCP) -> None:
    """Register tools that list or edit publication items."""
    register_section_item_tools(
        mcp,
        tool_prefix="resume.section.publication",
        section="publications",
        label="Publications",
        noun="publication",
        spec=PUBLICATION_SPEC,
        item_model=PublicationItemInput,
        items_type=PublicationItemsInput,
        item_ids_type=PublicationItemIdsInput,
    )
