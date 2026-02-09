"""Register tools for listing and editing certification items."""

from __future__ import annotations

from typing import List, Union

from mcp.server.fastmcp import FastMCP

from .section_item_tools import register_section_item_tools
from .field_adapters import ScalarFieldAdapter, WebsiteFieldAdapter
from .item_spec import FieldSpec, build_item_model, build_item_spec
from .tool_helpers import WebsiteInput


CERTIFICATION_FIELDS = [
    FieldSpec(
        name="name",
        field_type=str,
        alias="title",
        adapter=ScalarFieldAdapter(
            input_key="name", server_key="title", response_key="name"
        ),
    ),
    FieldSpec(
        name="issuer",
        field_type=str,
        adapter=ScalarFieldAdapter(
            input_key="issuer", server_key="issuer", response_key="issuer"
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
        name="summary",
        field_type=str,
        alias="description",
        adapter=ScalarFieldAdapter(
            input_key="summary", server_key="description", response_key="summary"
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
]

CertificationItemInput = build_item_model(
    "CertificationItemInput",
    CERTIFICATION_FIELDS,
    populate_by_name=True,
    module=__name__,
)
CertificationItemsInput = Union[CertificationItemInput, List[CertificationItemInput]]
CertificationItemIdsInput = Union[str, List[str]]

CERTIFICATION_SPEC = build_item_spec("certifications", CERTIFICATION_FIELDS)


def register_certification_tools(mcp: FastMCP) -> None:
    """Register tools that list or edit certification items."""
    register_section_item_tools(
        mcp,
        tool_prefix="resume.section.certification",
        section="certifications",
        label="Certifications",
        noun="certification",
        spec=CERTIFICATION_SPEC,
        item_model=CertificationItemInput,
        items_type=CertificationItemsInput,
        item_ids_type=CertificationItemIdsInput,
    )
