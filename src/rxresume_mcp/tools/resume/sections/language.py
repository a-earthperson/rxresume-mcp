"""Register tools for listing and editing language items."""

from __future__ import annotations

from typing import List, Union

from mcp.server.fastmcp import FastMCP

from .section_item_tools import ensure_non_empty_string, register_section_item_tools
from .field_adapters import ScalarFieldAdapter
from .item_spec import FieldSpec, build_item_model, build_item_spec

LANGUAGE_FIELDS = [
    # JSON Resume: languages[].language / fluency
    FieldSpec(
        name="language",
        field_type=str,
        adapter=ScalarFieldAdapter(
            response_key="language",
            server_key="language",
            server_default=" ",
            input_transform=ensure_non_empty_string,
        ),
    ),
    FieldSpec(
        name="fluency",
        field_type=str,
        adapter=ScalarFieldAdapter(
            response_key="fluency",
            server_key="fluency",
        ),
    ),
    FieldSpec(
        name="level",
        field_type=float,
        adapter=ScalarFieldAdapter(response_key="level", server_default=0),
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
