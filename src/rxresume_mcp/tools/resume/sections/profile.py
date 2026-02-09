"""Register tools for listing and editing profile items."""

from __future__ import annotations

from typing import List, Union

from mcp.server.fastmcp import FastMCP

from .section_item_tools import ensure_non_empty_string, register_section_item_tools
from .field_adapters import ScalarFieldAdapter, SuppressedFieldAdapter, WebsiteFieldAdapter
from .item_spec import FieldSpec, build_item_model, build_item_spec
from .tool_helpers import WebsiteInput


PROFILE_FIELDS = [
    FieldSpec(
        name="icon",
        field_type=str,
        adapter=SuppressedFieldAdapter(server_key="icon", default=""),
    ),
    FieldSpec(
        name="network",
        field_type=str,
        adapter=ScalarFieldAdapter(
            input_key="network",
            server_key="network",
            response_key="network",
            default=" ",
            input_transform=ensure_non_empty_string,
        ),
    ),
    FieldSpec(
        name="username",
        field_type=str,
        adapter=ScalarFieldAdapter(
            input_key="username", server_key="username", response_key="username"
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

ProfileItemInput = build_item_model(
    "ProfileItemInput", PROFILE_FIELDS, populate_by_name=True, module=__name__
)
ProfileItemsInput = Union[ProfileItemInput, List[ProfileItemInput]]
ProfileItemIdsInput = Union[str, List[str]]

PROFILE_SPEC = build_item_spec("profiles", PROFILE_FIELDS)


def register_profile_tools(mcp: FastMCP) -> None:
    """Register tools that list or edit profile items."""
    register_section_item_tools(
        mcp,
        tool_prefix="resume.section.profile",
        section="profiles",
        label="Profiles",
        noun="profile",
        spec=PROFILE_SPEC,
        item_model=ProfileItemInput,
        items_type=ProfileItemsInput,
        item_ids_type=ProfileItemIdsInput,
    )
