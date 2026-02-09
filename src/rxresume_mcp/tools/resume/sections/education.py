"""Register tools for listing and editing education items."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union, cast

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from rxresume_mcp import patch_ops
from rxresume_mcp.client import RxResumeClient

from ...core import execute_rxresume_operation
from .normalize import _normalize_url_fields
from .sections import _ensure_item_id, _ensure_object_payload, _require_resume_object
from .section_item_tools import (
    apply_section_item_patch,
    build_summary_highlights_description,
    coerce_item_ids,
    coerce_model_items,
    ensure_non_empty_string,
    extract_section_items,
    split_summary_highlights_description,
)
from .tool_helpers import WebsiteInput, normalize_website_payload


class EducationItemInput(BaseModel):
    model_config = {"extra": "forbid"}

    id: Optional[str] = None
    school: Optional[str] = None
    degree: Optional[str] = None
    area: Optional[str] = None
    grade: Optional[str] = None
    location: Optional[str] = None
    period: Optional[str] = None
    website: Optional[WebsiteInput] = None
    summary: Optional[str] = None
    highlights: Optional[List[str]] = None


EducationItemsInput = Union[EducationItemInput, List[EducationItemInput]]
EducationItemIdsInput = Union[str, List[str]]


def _apply_education_defaults(payload: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(payload)
    normalized["school"] = ensure_non_empty_string(normalized.get("school"))
    normalized.setdefault("degree", "")
    normalized.setdefault("area", "")
    normalized.setdefault("grade", "")
    normalized.setdefault("location", "")
    normalized.setdefault("period", "")
    summary = normalized.pop("summary", None)
    highlights = normalized.pop("highlights", None)
    normalized["description"] = build_summary_highlights_description(
        summary, highlights
    )
    normalized["website"] = normalize_website_payload(normalized.get("website"))
    return normalized


def _reshape_education_item(payload: Any) -> Any:
    if not isinstance(payload, dict):
        return payload
    summary, highlights = split_summary_highlights_description(
        payload.get("description")
    )
    normalized: Dict[str, Any] = {
        "id": payload.get("id"),
        "school": payload.get("school", "") or "",
        "degree": payload.get("degree", "") or "",
        "area": payload.get("area", "") or "",
        "grade": payload.get("grade", "") or "",
        "location": payload.get("location", "") or "",
        "period": payload.get("period", "") or "",
        "website": payload.get("website") or normalize_website_payload(None),
        "summary": summary or "",
        "highlights": highlights or [],
    }
    return normalized


def _reshape_education_items(payload: Any) -> Any:
    if isinstance(payload, list):
        return [_reshape_education_item(item) for item in payload]
    return payload


def _prepare_education_item(
    item: EducationItemInput, created_ids: List[str]
) -> Dict[str, Any]:
    payload = item.model_dump(exclude_none=True)
    payload = _ensure_object_payload(payload, "item")
    payload["hidden"] = False
    payload = _ensure_item_id(payload, created_ids)
    payload = _apply_education_defaults(payload)
    payload = cast(Dict[str, Any], _normalize_url_fields(payload))
    return payload


def _build_education_update_ops(item: EducationItemInput) -> List[Dict[str, Any]]:
    payload = item.model_dump(exclude_none=True)
    item_id = payload.pop("id", None)
    if not item_id or not isinstance(item_id, str):
        raise ValueError("item.id is required for update")
    ops: List[Dict[str, Any]] = []

    field_values = {
        "school": ("school", ensure_non_empty_string),
        "degree": ("degree", lambda value: value),
        "area": ("area", lambda value: value),
        "grade": ("grade", lambda value: value),
        "location": ("location", lambda value: value),
        "period": ("period", lambda value: value),
    }
    for field, (target, transform) in field_values.items():
        if field not in payload:
            continue
        ops.append(
            patch_ops.op_replace(
                patch_ops.path_section_item_field("education", item_id, target),
                transform(payload.pop(field)),
            )
        )

    summary_provided = "summary" in payload
    highlights_provided = "highlights" in payload
    if summary_provided or highlights_provided:
        description = build_summary_highlights_description(
            payload.pop("summary", None) if summary_provided else None,
            payload.pop("highlights", None) if highlights_provided else None,
        )
        ops.append(
            patch_ops.op_replace(
                patch_ops.path_section_item_field("education", item_id, "description"),
                description,
            )
        )

    if "website" in payload:
        website_payload = normalize_website_payload(payload.pop("website"))
        website_payload = cast(Dict[str, Any], _normalize_url_fields(website_payload))
        base = patch_ops.path_section_item_field("education", item_id, "website")
        for key, value in website_payload.items():
            ops.append(patch_ops.op_replace(f"{base}/{key}", value))

    if payload:
        raise ValueError(f"Unexpected fields in education update: {sorted(payload)}")
    if not ops:
        raise ValueError(f"No fields provided to update for item id: {item_id}")
    return ops


def register_education_tools(mcp: FastMCP) -> None:
    """Register tools that list or edit education items."""

    @mcp.tool(
        name="resume.section.education.list",
        description="List education items for a resume.",
    )
    async def list_education(
        ctx: Context,
        resume_id: str = Field(description="Resume ID"),
    ) -> Dict[str, Any]:
        async def _operation(client: RxResumeClient) -> Any:
            resume = _require_resume_object(await client.get_resume(resume_id))
            items = extract_section_items(resume, "education", label="Education")
            return _reshape_education_items(items)

        return await execute_rxresume_operation(
            operation_name=f"list education: {resume_id}",
            operation_func=_operation,
            ctx=ctx,
        )

    @mcp.tool(
        name="resume.section.education.item.create",
        description=(
            "Add one or more education items. "
            "All fields are optional; hidden is forced to false."
        ),
    )
    async def add_education(
        ctx: Context,
        resume_id: str = Field(description="Resume ID"),
        items: Optional[EducationItemsInput] = Field(
            default=None,
            description="Education item or list of items to add.",
        ),
    ) -> Dict[str, Any]:
        async def _operation(client: RxResumeClient) -> Any:
            if items is None:
                raise ValueError("items is required")
            created_ids: List[str] = []
            ops: List[Dict[str, Any]] = []
            for item in coerce_model_items(items, EducationItemInput):
                payload = _prepare_education_item(item, created_ids)
                ops.append(
                    patch_ops.op_add(
                        patch_ops.path_section_items_append("education"), payload
                    )
                )
            result = await apply_section_item_patch(
                client, resume_id, "education", ops, label="Education"
            )
            return _reshape_education_items(result)

        return await execute_rxresume_operation(
            operation_name=f"add education: {resume_id}",
            operation_func=_operation,
            ctx=ctx,
        )

    @mcp.tool(
        name="resume.section.education.item.delete",
        description="Remove one or more education items by id.",
    )
    async def remove_education(
        ctx: Context,
        resume_id: str = Field(description="Resume ID"),
        item_ids: Optional[EducationItemIdsInput] = Field(
            default=None, description="Item id or list of item ids to remove."
        ),
    ) -> Dict[str, Any]:
        async def _operation(client: RxResumeClient) -> Any:
            if item_ids is None:
                raise ValueError("item_ids is required")
            ops: List[Dict[str, Any]] = []
            for item_id in coerce_item_ids(item_ids):
                ops.append(
                    patch_ops.op_remove(
                        patch_ops.path_section_item("education", item_id)
                    )
                )
            result = await apply_section_item_patch(
                client, resume_id, "education", ops, label="Education"
            )
            return _reshape_education_items(result)

        return await execute_rxresume_operation(
            operation_name=f"remove education: {resume_id}",
            operation_func=_operation,
            ctx=ctx,
        )

    @mcp.tool(
        name="resume.section.education.item.update",
        description=(
            "Update one or more education items by id. "
            "item.id is required; other fields are optional."
        ),
    )
    async def update_education(
        ctx: Context,
        resume_id: str = Field(description="Resume ID"),
        items: Optional[EducationItemsInput] = Field(
            default=None,
            description="Education item or list of items to update.",
        ),
    ) -> Dict[str, Any]:
        async def _operation(client: RxResumeClient) -> Any:
            if items is None:
                raise ValueError("items is required")
            ops: List[Dict[str, Any]] = []
            for item in coerce_model_items(items, EducationItemInput):
                ops.extend(_build_education_update_ops(item))
            result = await apply_section_item_patch(
                client, resume_id, "education", ops, label="Education"
            )
            return _reshape_education_items(result)

        return await execute_rxresume_operation(
            operation_name=f"update education: {resume_id}",
            operation_func=_operation,
            ctx=ctx,
        )
