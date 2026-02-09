"""Register tools for listing and editing reference items."""

from __future__ import annotations

from typing import List, Union

from mcp.server.fastmcp import FastMCP

from .section_item_tools import ensure_non_empty_string, register_section_item_tools
from .field_adapters import ScalarFieldAdapter, WebsiteFieldAdapter
from .item_spec import FieldSpec, build_item_model, build_item_spec

REFERENCE_FIELDS = [
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
        name="position",
        field_type=str,
        adapter=ScalarFieldAdapter(
            input_key="position", server_key="position", response_key="position"
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
        name="contact",
        field_type=str,
        adapter=ScalarFieldAdapter(
            input_key="contact", server_key="phone", response_key="contact"
        ),
    ),
    FieldSpec(
        name="summary",
        field_type=str,
        adapter=ScalarFieldAdapter(
            input_key="summary", server_key="description", response_key="summary"
        ),
    ),
]

ReferenceItemInput = build_item_model(
    "ReferenceItemInput",
    REFERENCE_FIELDS,
    populate_by_name=True,
    module=__name__,
)
ReferenceItemsInput = Union[ReferenceItemInput, List[ReferenceItemInput]]
ReferenceItemIdsInput = Union[str, List[str]]

REFERENCE_SPEC = build_item_spec("references", REFERENCE_FIELDS)


def register_reference_tools(mcp: FastMCP) -> None:
    """Register tools that list or edit reference items."""
    register_section_item_tools(
        mcp,
        tool_prefix="resume.section.reference",
        section="references",
        label="References",
        noun="reference",
        spec=REFERENCE_SPEC,
        item_model=ReferenceItemInput,
        items_type=ReferenceItemsInput,
        item_ids_type=ReferenceItemIdsInput,
    )
