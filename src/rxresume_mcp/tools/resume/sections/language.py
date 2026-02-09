"""Register tools for listing and editing language items."""

from __future__ import annotations

from typing import List, Union

from mcp.server.fastmcp import FastMCP

from .section_item_tools import ensure_non_empty_string, register_section_item_tools
from .field_adapters import ScalarFieldAdapter
from .item_spec import FieldSpec, build_item_model, build_item_spec


LANGUAGE_FIELDS = [
    FieldSpec(
        name="name",
        field_type=str,
        alias="language",
        adapter=ScalarFieldAdapter(
            input_key="name",
            server_key="language",
            response_key="name",
            default=" ",
            input_transform=ensure_non_empty_string,
        ),
    ),
    FieldSpec(
        name="proficiency",
        field_type=str,
        alias="fluency",
        adapter=ScalarFieldAdapter(
            input_key="proficiency",
            server_key="fluency",
            response_key="proficiency",
            default="",
        ),
    ),
    FieldSpec(
        name="level",
        field_type=float,
        adapter=ScalarFieldAdapter(
            input_key="level", server_key="level", response_key="level", default=0
        ),
    ),
]

LanguageItemInput = build_item_model(
    "LanguageItemInput", LANGUAGE_FIELDS, populate_by_name=True, module=__name__
)
LanguageItemsInput = Union[LanguageItemInput, List[LanguageItemInput]]
LanguageItemIdsInput = Union[str, List[str]]

LANGUAGE_SPEC = build_item_spec("languages", LANGUAGE_FIELDS)


def register_language_tools(mcp: FastMCP) -> None:
    """Register tools that list or edit language items."""
    register_section_item_tools(
        mcp,
        tool_prefix="resume.section.language",
        section="languages",
        label="Languages",
        noun="language",
        spec=LANGUAGE_SPEC,
        item_model=LanguageItemInput,
        items_type=LanguageItemsInput,
        item_ids_type=LanguageItemIdsInput,
    )
