"""Register tools for listing and editing award items."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union, cast

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from rxresume_mcp import patch_ops
from rxresume_mcp.rxresume_client import RxResumeClient

from .core import execute_rxresume_operation
from .normalize import _normalize_url_fields
from .sections import _ensure_item_id, _ensure_object_payload, _require_resume_object
from .section_item_tools import (
    apply_section_item_patch,
    coerce_item_ids,
    coerce_model_items,
    ensure_non_empty_string,
    extract_section_items,
)
from .tool_helpers import WebsiteInput, normalize_website_payload


class AwardItemInput(BaseModel):
    model_config = {"extra": "forbid", "populate_by_name": True}

    id: Optional[str] = None
    name: Optional[str] = Field(default=None, alias="title")
    awarder: Optional[str] = None
    period: Optional[str] = Field(default=None, alias="date")
    website: Optional[WebsiteInput] = None
    summary: Optional[str] = Field(default=None, alias="description")


AwardItemsInput = Union[AwardItemInput, List[AwardItemInput]]
AwardItemIdsInput = Union[str, List[str]]


def _reshape_award_item(payload: Any) -> Any:
    if not isinstance(payload, dict):
        return payload
    normalized: Dict[str, Any] = {
        "id": payload.get("id"),
        "name": payload.get("title", "") or "",
        "awarder": payload.get("awarder", "") or "",
        "period": payload.get("date", "") or "",
        "website": payload.get("website") or normalize_website_payload(None),
        "summary": payload.get("description", "") or "",
    }
    return normalized


def _reshape_award_items(payload: Any) -> Any:
    if isinstance(payload, list):
        return [_reshape_award_item(item) for item in payload]
    return payload


def _apply_award_defaults(payload: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(payload)
    name = normalized.pop("name", None)
    normalized["title"] = ensure_non_empty_string(name)
    normalized.setdefault("awarder", "")
    normalized.setdefault("date", "")
    summary = normalized.pop("summary", None)
    normalized["description"] = summary if summary is not None else ""
    normalized["website"] = normalize_website_payload(normalized.get("website"))
    return normalized


def _prepare_award_item(item: AwardItemInput, created_ids: List[str]) -> Dict[str, Any]:
    payload = item.model_dump(exclude_none=True)
    payload = _ensure_object_payload(payload, "item")
    payload["hidden"] = False
    payload = _ensure_item_id(payload, created_ids)
    payload = _apply_award_defaults(payload)
    payload = cast(Dict[str, Any], _normalize_url_fields(payload))
    return payload


def _build_award_update_ops(item: AwardItemInput) -> List[Dict[str, Any]]:
    payload = item.model_dump(exclude_none=True)
    item_id = payload.pop("id", None)
    if not item_id or not isinstance(item_id, str):
        raise ValueError("item.id is required for update")
    ops: List[Dict[str, Any]] = []

    field_values = {
        "name": ("title", ensure_non_empty_string),
        "awarder": ("awarder", lambda value: value),
        "period": ("date", lambda value: value),
        "summary": ("description", lambda value: value),
    }
    for field, (target, transform) in field_values.items():
        if field not in payload:
            continue
        ops.append(
            patch_ops.op_replace(
                patch_ops.path_section_item_field("awards", item_id, target),
                transform(payload.pop(field)),
            )
        )

    if "website" in payload:
        website_payload = normalize_website_payload(payload.pop("website"))
        website_payload = cast(Dict[str, Any], _normalize_url_fields(website_payload))
        base = patch_ops.path_section_item_field("awards", item_id, "website")
        for key, value in website_payload.items():
            ops.append(patch_ops.op_replace(f"{base}/{key}", value))

    if payload:
        raise ValueError(f"Unexpected fields in award update: {sorted(payload)}")
    if not ops:
        raise ValueError(f"No fields provided to update for item id: {item_id}")
    return ops


def register_award_tools(mcp: FastMCP) -> None:
    """Register tools that list or edit award items."""

    @mcp.tool(
        name="resume.section.award.list",
        description="List award items for a resume.",
    )
    async def list_award(
        ctx: Context,
        resume_id: str = Field(description="Resume ID"),
    ) -> Dict[str, Any]:
        async def _operation(client: RxResumeClient) -> Any:
            resume = _require_resume_object(await client.get_resume(resume_id))
            items = extract_section_items(resume, "awards", label="Awards")
            return _reshape_award_items(items)

        return await execute_rxresume_operation(
            operation_name=f"list award: {resume_id}",
            operation_func=_operation,
            ctx=ctx,
        )

    @mcp.tool(
        name="resume.section.award.item.create",
        description=(
            "Add one or more award items. "
            "All fields are optional; hidden is forced to false."
        ),
    )
    async def add_award(
        ctx: Context,
        resume_id: str = Field(description="Resume ID"),
        items: Optional[AwardItemsInput] = Field(
            default=None,
            description="Award item or list of items to add.",
        ),
    ) -> Dict[str, Any]:
        async def _operation(client: RxResumeClient) -> Any:
            if items is None:
                raise ValueError("items is required")
            created_ids: List[str] = []
            ops: List[Dict[str, Any]] = []
            for item in coerce_model_items(items, AwardItemInput):
                payload = _prepare_award_item(item, created_ids)
                ops.append(
                    patch_ops.op_add(
                        patch_ops.path_section_items_append("awards"), payload
                    )
                )
            result = await apply_section_item_patch(
                client, resume_id, "awards", ops, label="Awards"
            )
            return _reshape_award_items(result)

        return await execute_rxresume_operation(
            operation_name=f"add award: {resume_id}",
            operation_func=_operation,
            ctx=ctx,
        )

    @mcp.tool(
        name="resume.section.award.item.delete",
        description="Remove one or more award items by id.",
    )
    async def remove_award(
        ctx: Context,
        resume_id: str = Field(description="Resume ID"),
        item_ids: Optional[AwardItemIdsInput] = Field(
            default=None, description="Item id or list of item ids to remove."
        ),
    ) -> Dict[str, Any]:
        async def _operation(client: RxResumeClient) -> Any:
            if item_ids is None:
                raise ValueError("item_ids is required")
            ops: List[Dict[str, Any]] = []
            for item_id in coerce_item_ids(item_ids):
                ops.append(
                    patch_ops.op_remove(patch_ops.path_section_item("awards", item_id))
                )
            result = await apply_section_item_patch(
                client, resume_id, "awards", ops, label="Awards"
            )
            return _reshape_award_items(result)

        return await execute_rxresume_operation(
            operation_name=f"remove award: {resume_id}",
            operation_func=_operation,
            ctx=ctx,
        )

    @mcp.tool(
        name="resume.section.award.item.update",
        description=(
            "Update one or more award items by id. "
            "item.id is required; other fields are optional."
        ),
    )
    async def update_award(
        ctx: Context,
        resume_id: str = Field(description="Resume ID"),
        items: Optional[AwardItemsInput] = Field(
            default=None,
            description="Award item or list of items to update.",
        ),
    ) -> Dict[str, Any]:
        async def _operation(client: RxResumeClient) -> Any:
            if items is None:
                raise ValueError("items is required")
            ops: List[Dict[str, Any]] = []
            for item in coerce_model_items(items, AwardItemInput):
                ops.extend(_build_award_update_ops(item))
            result = await apply_section_item_patch(
                client, resume_id, "awards", ops, label="Awards"
            )
            return _reshape_award_items(result)

        return await execute_rxresume_operation(
            operation_name=f"update award: {resume_id}",
            operation_func=_operation,
            ctx=ctx,
        )
