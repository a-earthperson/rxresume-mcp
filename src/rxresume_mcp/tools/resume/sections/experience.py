"""Register tools for listing and adding experience items."""

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

class ExperienceItemInput(BaseModel):
    model_config = {"extra": "forbid", "populate_by_name": True}

    id: Optional[str] = None
    name: Optional[str] = Field(default=None, alias="company")
    position: Optional[str] = None
    url: Optional[WebsiteInput] = None
    period: Optional[str] = None
    summary: Optional[str] = None
    highlights: Optional[List[str]] = None


ExperienceItemsInput = Union[ExperienceItemInput, List[ExperienceItemInput]]
ExperienceItemIdsInput = Union[str, List[str]]

def _reshape_experience_item(payload: Any) -> Any:
    if not isinstance(payload, dict):
        return payload
    summary, highlights = split_summary_highlights_description(
        payload.get("description")
    )
    normalized: Dict[str, Any] = {
        "id": payload.get("id"),
        "name": payload.get("company", "") or "",
        "position": payload.get("position", "") or "",
        "url": payload.get("website") or normalize_website_payload(None),
        "period": payload.get("period", "") or "",
        "summary": summary or "",
        "highlights": highlights or [],
    }
    return normalized


def _reshape_experience_items(payload: Any) -> Any:
    if isinstance(payload, list):
        return [_reshape_experience_item(item) for item in payload]
    return payload


def _apply_experience_defaults(payload: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(payload)
    name = normalized.pop("name", None)
    normalized["company"] = ensure_non_empty_string(name)
    normalized.setdefault("position", "")
    normalized.setdefault("period", "")
    normalized.setdefault("location", "")
    summary = normalized.pop("summary", None)
    highlights = normalized.pop("highlights", None)
    normalized["description"] = build_summary_highlights_description(
        summary, highlights
    )
    url_payload = normalized.pop("url", None)
    normalized["website"] = normalize_website_payload(url_payload)
    return normalized


def _prepare_experience_item(
    item: ExperienceItemInput, created_ids: List[str]
) -> Dict[str, Any]:
    payload = item.model_dump(exclude_none=True)
    payload = _ensure_object_payload(payload, "item")
    payload["hidden"] = False
    payload = _ensure_item_id(payload, created_ids)
    payload = _apply_experience_defaults(payload)
    payload = cast(Dict[str, Any], _normalize_url_fields(payload))
    return payload


def _build_experience_update_ops(item: ExperienceItemInput) -> List[Dict[str, Any]]:
    payload = item.model_dump(exclude_none=True)
    item_id = payload.pop("id", None)
    if not item_id or not isinstance(item_id, str):
        raise ValueError("item.id is required for update")
    ops: List[Dict[str, Any]] = []

    field_values = {
        "name": ("company", ensure_non_empty_string),
        "position": ("position", lambda value: value),
        "period": ("period", lambda value: value),
    }
    for field, (target, transform) in field_values.items():
        if field not in payload:
            continue
        ops.append(
            patch_ops.op_replace(
                patch_ops.path_section_item_field("experience", item_id, target),
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
                patch_ops.path_section_item_field("experience", item_id, "description"),
                description,
            )
        )

    if "url" in payload:
        website_payload = normalize_website_payload(payload.pop("url"))
        website_payload = cast(Dict[str, Any], _normalize_url_fields(website_payload))
        base = patch_ops.path_section_item_field("experience", item_id, "website")
        for key, value in website_payload.items():
            ops.append(patch_ops.op_replace(f"{base}/{key}", value))

    if payload:
        raise ValueError(f"Unexpected fields in experience update: {sorted(payload)}")
    if not ops:
        raise ValueError(f"No fields provided to update for item id: {item_id}")
    return ops


def register_experience_tools(mcp: FastMCP) -> None:
    """Register tools that list or add experience items."""

    @mcp.tool(
        name="resume.section.experience.list",
        description="List experience items for a resume.",
    )
    async def list_experience(
        ctx: Context,
        resume_id: str = Field(description="Resume ID"),
    ) -> Dict[str, Any]:
        async def _operation(client: RxResumeClient) -> Any:
            resume = _require_resume_object(await client.get_resume(resume_id))
            items = extract_section_items(resume, "experience", label="Experience")
            return _reshape_experience_items(items)

        return await execute_rxresume_operation(
            operation_name=f"list experience: {resume_id}",
            operation_func=_operation,
            ctx=ctx,
        )

    @mcp.tool(
        name="resume.section.experience.item.create",
        description=(
            "Add one or more experience items. "
            "All fields are optional; hidden is forced to false."
        ),
    )
    async def add_experience(
        ctx: Context,
        resume_id: str = Field(description="Resume ID"),
        items: Optional[ExperienceItemsInput] = Field(
            default=None,
            description="Experience item or list of items to add.",
        ),
    ) -> Dict[str, Any]:
        async def _operation(client: RxResumeClient) -> Any:
            if items is None:
                raise ValueError("items is required")
            created_ids: List[str] = []
            ops: List[Dict[str, Any]] = []
            for item in coerce_model_items(items, ExperienceItemInput):
                payload = _prepare_experience_item(item, created_ids)
                ops.append(
                    patch_ops.op_add(
                        patch_ops.path_section_items_append("experience"), payload
                    )
                )
            result = await apply_section_item_patch(
                client, resume_id, "experience", ops, label="Experience"
            )
            return _reshape_experience_items(result)

        return await execute_rxresume_operation(
            operation_name=f"add experience: {resume_id}",
            operation_func=_operation,
            ctx=ctx,
        )

    @mcp.tool(
        name="resume.section.experience.item.delete",
        description="Remove one or more experience items by id.",
    )
    async def remove_experience(
        ctx: Context,
        resume_id: str = Field(description="Resume ID"),
        item_ids: Optional[ExperienceItemIdsInput] = Field(
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
                        patch_ops.path_section_item("experience", item_id)
                    )
                )
            result = await apply_section_item_patch(
                client, resume_id, "experience", ops, label="Experience"
            )
            return _reshape_experience_items(result)

        return await execute_rxresume_operation(
            operation_name=f"remove experience: {resume_id}",
            operation_func=_operation,
            ctx=ctx,
        )

    @mcp.tool(
        name="resume.section.experience.item.update",
        description=(
            "Update one or more experience items by id. "
            "item.id is required; other fields are optional."
        ),
    )
    async def update_experience(
        ctx: Context,
        resume_id: str = Field(description="Resume ID"),
        items: Optional[ExperienceItemsInput] = Field(
            default=None,
            description="Experience item or list of items to update.",
        ),
    ) -> Dict[str, Any]:
        async def _operation(client: RxResumeClient) -> Any:
            if items is None:
                raise ValueError("items is required")
            ops: List[Dict[str, Any]] = []
            for item in coerce_model_items(items, ExperienceItemInput):
                ops.extend(_build_experience_update_ops(item))
            result = await apply_section_item_patch(
                client, resume_id, "experience", ops, label="Experience"
            )
            return _reshape_experience_items(result)

        return await execute_rxresume_operation(
            operation_name=f"update experience: {resume_id}",
            operation_func=_operation,
            ctx=ctx,
        )
