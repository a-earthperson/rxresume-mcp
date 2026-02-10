"""Register tools for listing and editing skill items."""

from __future__ import annotations

from typing import List, Union

from mcp.server.fastmcp import FastMCP

from .section_item_tools import ensure_non_empty_string, register_section_item_tools
from .field_adapters import ScalarFieldAdapter, SuppressedFieldAdapter
from .item_spec import FieldSpec, build_item_model, build_item_spec

SKILL_FIELDS = [
    FieldSpec(
        name="icon",
        field_type=str,
        adapter=SuppressedFieldAdapter(server_key="icon", default=""),
    ),
    FieldSpec(
        name="name",
        field_type=str,
        adapter=ScalarFieldAdapter(
            response_key="name",
            server_default=" ",
            input_transform=ensure_non_empty_string,
        ),
    ),
    FieldSpec(
        name="proficiency",
        field_type=str,
        adapter=ScalarFieldAdapter(
            response_key="proficiency",
        ),
    ),
    FieldSpec(
        name="level",
        field_type=float,
        adapter=ScalarFieldAdapter(response_key="level", server_default=0),
    ),
    FieldSpec(
        name="keywords",
        field_type=List[str],
        adapter=ScalarFieldAdapter(
            response_key="keywords",
            server_default=[],
        ),
    ),
]

SkillItemInput = build_item_model("SkillItemInput", SKILL_FIELDS, module=__name__)
SkillItemsInput = Union[SkillItemInput, List[SkillItemInput]]
SkillItemIdsInput = Union[str, List[str]]

SKILL_SPEC = build_item_spec("skills", SKILL_FIELDS)


def register_skill_tools(mcp: FastMCP) -> None:
    """Register tools that list or edit skill items."""
    register_section_item_tools(
        mcp,
        tool_prefix="resume.section.skill",
        section="skills",
        label="Skills",
        noun="skill",
        spec=SKILL_SPEC,
        item_model=SkillItemInput,
        items_type=SkillItemsInput,
        item_ids_type=SkillItemIdsInput,
    )
