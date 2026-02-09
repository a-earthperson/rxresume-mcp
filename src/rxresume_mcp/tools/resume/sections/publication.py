"""Register tools for listing and editing publication items."""

from __future__ import annotations

from typing import List, Union

from mcp.server.fastmcp import FastMCP

from .section_item_tools import register_section_item_tools
from .field_adapters import (
    ScalarFieldAdapter,
    SummaryHighlightsFieldAdapter,
    WebsiteFieldAdapter,
)
from .item_spec import FieldSpec, build_item_model, build_item_spec
from .tool_helpers import WebsiteInput


SUMMARY_HIGHLIGHTS_FIELD = SummaryHighlightsFieldAdapter()

PUBLICATION_FIELDS = [
    FieldSpec(
        name="name",
        field_type=str,
        alias="title",
        adapter=ScalarFieldAdapter(
            input_key="name", server_key="title", response_key="name"
        ),
    ),
    FieldSpec(
        name="publisher",
        field_type=str,
        adapter=ScalarFieldAdapter(
            input_key="publisher", server_key="publisher", response_key="publisher"
        ),
    ),
    FieldSpec(
        name="period",
        field_type=str,
        alias="date",
        adapter=ScalarFieldAdapter(
            input_key="period", server_key="date", response_key="period"
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
