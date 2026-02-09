"""Register tools for editing resume basics."""

from __future__ import annotations

from typing import Any, Dict

from mcp.server.fastmcp import FastMCP

from rxresume_mcp import patch_ops

from .field_adapters import ScalarFieldAdapter, WebsiteFieldAdapter
from .item_spec import FieldSpec, MappedPatchTarget, build_object_model, build_spec
from .sections import _extract_section_data
from .section_item_tools import register_object_tools
from .tool_helpers import WebsiteInputLike


BASICS_FIELDS = [
    FieldSpec(
        name="name",
        field_type=str,
        adapter=ScalarFieldAdapter(
            input_key="name", server_key="name", response_key="name"
        ),
    ),
    FieldSpec(
        name="label",
        field_type=str,
        alias="headline",
        adapter=ScalarFieldAdapter(
            input_key="label", server_key="headline", response_key="label"
        ),
    ),
    FieldSpec(
        name="email",
        field_type=str,
        adapter=ScalarFieldAdapter(
            input_key="email", server_key="email", response_key="email"
        ),
    ),
    FieldSpec(
        name="phone",
        field_type=str,
        adapter=ScalarFieldAdapter(
            input_key="phone", server_key="phone", response_key="phone"
        ),
    ),
    FieldSpec(
        name="location",
        field_type=str,
        adapter=ScalarFieldAdapter(
            input_key="location", server_key="location", response_key="location"
        ),
    ),
    FieldSpec(
        name="url",
        field_type=WebsiteInputLike,
        alias="website",
        adapter=WebsiteFieldAdapter(
            input_key="url", server_key="website", response_key="url"
        ),
    ),
    FieldSpec(
        name="summary",
        field_type=str,
        adapter=ScalarFieldAdapter(
            input_key="summary", server_key="summary", response_key="summary"
        ),
    ),
]

BasicsInput = build_object_model(
    "BasicsInput", BASICS_FIELDS, populate_by_name=True, module=__name__
)
BASICS_SPEC = build_spec("basics", BASICS_FIELDS)
BASICS_TARGET = MappedPatchTarget(
    default_builder=patch_ops.path_basics_field,
    overrides={"summary": patch_ops.path_summary_field("content")},
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


def _build_basics_payload(resume: Dict[str, Any]) -> Any:
    basics = _extract_section_data(resume, "basics")["data"]
    if not isinstance(basics, dict):
        return basics
    payload = dict(basics)
    payload.pop("customFields", None)
    summary_data = _extract_section_data(resume, "summary")["data"]
    if isinstance(summary_data, dict):
        payload["summary"] = summary_data.get("content")
    return payload


def register_basics_tools(mcp: FastMCP) -> None:
    """Register tools that edit basics fields."""
    register_object_tools(
        mcp,
        tool_prefix="resume.basics",
        name="basics",
        spec=BASICS_SPEC,
        target=BASICS_TARGET,
        model=BasicsInput,
        payload_type=BasicsInput,
        payload_description=(
            "Basics object with any subset of fields to update. "
            "url accepts a string or {url,label} (alias: website)."
        ),
        build_payload=_build_basics_payload,
        extra_update_ops=lambda _payload: [
            patch_ops.op_replace(patch_ops.path_basics_field("customFields"), [])
        ],
        reset_payload=BASICS_RESET,
    )
