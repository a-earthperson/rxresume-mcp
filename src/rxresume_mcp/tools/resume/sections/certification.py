"""Register tools for listing and editing certification items."""

from __future__ import annotations

from typing import List, Union

from mcp.server.fastmcp import FastMCP

from .section_item_tools import register_section_item_tools
from .field_adapters import (
    ScalarFieldAdapter,
    WebsiteFieldAdapter,
    normalize_date_input,
)
from .item_spec import FieldSpec, build_item_model, build_item_spec

CERTIFICATION_FIELDS = [
    FieldSpec(
        name="name",
        field_type=str,
        adapter=ScalarFieldAdapter(response_key="name", server_key="title"),
    ),
    FieldSpec(
        name="issuer",
        field_type=str,
        adapter=ScalarFieldAdapter(response_key="issuer"),
    ),
    FieldSpec(
        name="date",
        field_type=str,
        adapter=ScalarFieldAdapter(
            response_key="date", input_transform=normalize_date_input
        ),
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
        # JSON Resume uses `certificates` for this section.
        tool_prefix="resume.section.certificate",
        section="certifications",
        label="Certificates",
        noun="certificate",
        spec=CERTIFICATION_SPEC,
        item_model=CertificationItemInput,
        items_type=CertificationItemsInput,
        item_ids_type=CertificationItemIdsInput,
    )
