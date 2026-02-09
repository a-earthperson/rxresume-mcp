"""Register tools for editing resume basics."""

from __future__ import annotations

from typing import Optional

from mcp.server.fastmcp import FastMCP

from rxresume_mcp import patch_ops

from .field_adapters import ScalarFieldAdapter, WebsiteFieldAdapter
from .item_spec import (
    FieldSpec,
    build_object_model,
    build_object_spec,
    resume_data_path,
)
from .section_item_tools import register_object_tools
from .tool_helpers import WebsiteInputLike


def _basics_path(_section: str, _item_id: str, field: str) -> str:
    return patch_ops.path_basics_field(field)


def _summary_path(_section: str, _item_id: str, _field: str) -> str:
    return patch_ops.path_summary_field("content")


def _basics_scalar(
    name: str,
    *,
    alias: Optional[str] = None,
    response_key: Optional[str] = None,
) -> FieldSpec:
    return FieldSpec(
        name=name,
        field_type=str,
        alias=alias,
        adapter=ScalarFieldAdapter(
            input_key=name,
            server_key=alias or name,
            response_key=response_key or name,
            path_builder=_basics_path,
        ),
    )


def _summary_scalar() -> FieldSpec:
    return FieldSpec(
        name="summary",
        field_type=str,
        source_getter=resume_data_path("summary", "content"),
        adapter=ScalarFieldAdapter(
            input_key="summary",
            server_key="summary",
            response_key="summary",
            path_builder=_summary_path,
        ),
    )


def _basics_website() -> FieldSpec:
    return FieldSpec(
        name="url",
        field_type=WebsiteInputLike,
        alias="website",
        adapter=WebsiteFieldAdapter(
            input_key="url",
            server_key="website",
            response_key="url",
            path_builder=_basics_path,
        ),
    )


BASICS_FIELDS = [
    _basics_scalar("name"),
    _basics_scalar("label", alias="headline"),
    _basics_scalar("email"),
    _basics_scalar("phone"),
    _basics_scalar("location"),
    _basics_website(),
    _summary_scalar(),
]

BasicsInput = build_object_model(
    "BasicsInput", BASICS_FIELDS, populate_by_name=True, module=__name__
)
BASICS_SPEC = build_object_spec(
    "basics",
    BASICS_FIELDS,
    source_root=("data", "basics"),
)

BASICS_RESET = BasicsInput(
    name="",
    label="",
    email="",
    phone="",
    location="",
    url={"url": "", "label": ""},
    summary="",
)


def register_basics_tools(mcp: FastMCP) -> None:
    """Register tools that edit basics fields."""
    register_object_tools(
        mcp,
        tool_prefix="resume.basics",
        name="basics",
        spec=BASICS_SPEC,
        model=BasicsInput,
        payload_type=BasicsInput,
        payload_description=(
            "Basics object with any subset of fields to update. "
            "url accepts a string or {url,label} (alias: website)."
        ),
        extra_update_ops=lambda _payload: [
            patch_ops.op_replace(patch_ops.path_basics_field("customFields"), [])
        ],
        reset_payload=BASICS_RESET,
    )
