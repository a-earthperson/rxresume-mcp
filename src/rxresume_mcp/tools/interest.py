"""Register tools for listing and editing interest items."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from rxresume_mcp import patch_ops
from rxresume_mcp.rxresume_client import RxResumeClient

from .core import execute_rxresume_operation
from .sections import _ensure_item_id, _ensure_object_payload, _require_resume_object
from .section_item_tools import (
    apply_section_item_patch,
    coerce_item_ids,
    coerce_model_items,
    ensure_non_empty_string,
    extract_section_items,
)


class InterestItemInput(BaseModel):
    model_config = {"extra": "forbid"}

    id: Optional[str] = None
    name: Optional[str] = None
    keywords: Optional[List[str]] = None


InterestItemsInput = Union[InterestItemInput, List[InterestItemInput]]
InterestItemIdsInput = Union[str, List[str]]


def _apply_interest_defaults(payload: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(payload)
    normalized["icon"] = ""
    normalized["name"] = ensure_non_empty_string(normalized.get("name"))
    normalized.setdefault("keywords", [])
    return normalized


def _reshape_interest_item(payload: Any) -> Any:
    if not isinstance(payload, dict):
        return payload
    normalized: Dict[str, Any] = {
        "id": payload.get("id"),
        "name": payload.get("name", "") or "",
        "keywords": payload.get("keywords", []) or [],
    }
    return normalized


def _reshape_interest_items(payload: Any) -> Any:
    if isinstance(payload, list):
        return [_reshape_interest_item(item) for item in payload]
    return payload


def _prepare_interest_item(
    item: InterestItemInput, created_ids: List[str]
) -> Dict[str, Any]:
    payload = item.model_dump(exclude_none=True)
    payload = _ensure_object_payload(payload, "item")
    payload["hidden"] = False
    payload = _ensure_item_id(payload, created_ids)
    payload = _apply_interest_defaults(payload)
    return payload


def _build_interest_update_ops(item: InterestItemInput) -> List[Dict[str, Any]]:
    payload = item.model_dump(exclude_none=True)
    item_id = payload.pop("id", None)
    if not item_id or not isinstance(item_id, str):
        raise ValueError("item.id is required for update")
    ops: List[Dict[str, Any]] = []

    field_values = {
        "name": ("name", ensure_non_empty_string),
        "keywords": ("keywords", lambda value: value),
    }
    for field, (target, transform) in field_values.items():
        if field not in payload:
            continue
        ops.append(
            patch_ops.op_replace(
                patch_ops.path_section_item_field("interests", item_id, target),
                transform(payload.pop(field)),
            )
        )

    if payload:
        raise ValueError(f"Unexpected fields in interest update: {sorted(payload)}")
    if not ops:
        raise ValueError(f"No fields provided to update for item id: {item_id}")
    return ops


def register_interest_tools(mcp: FastMCP) -> None:
    """Register tools that list or edit interest items."""

    @mcp.tool(
        name="resume.section.interest.list",
        description="List interest items for a resume.",
    )
    async def list_interest(
        ctx: Context,
        resume_id: str = Field(description="Resume ID"),
    ) -> Dict[str, Any]:
        async def _operation(client: RxResumeClient) -> Any:
            resume = _require_resume_object(await client.get_resume(resume_id))
            items = extract_section_items(resume, "interests", label="Interests")
            return _reshape_interest_items(items)

        return await execute_rxresume_operation(
            operation_name=f"list interest: {resume_id}",
            operation_func=_operation,
            ctx=ctx,
        )

    @mcp.tool(
        name="resume.section.interest.item.create",
        description=(
            "Add one or more interest items. "
            "All fields are optional; hidden is forced to false."
        ),
    )
    async def add_interest(
        ctx: Context,
        resume_id: str = Field(description="Resume ID"),
        items: Optional[InterestItemsInput] = Field(
            default=None,
            description="Interest item or list of items to add.",
        ),
    ) -> Dict[str, Any]:
        async def _operation(client: RxResumeClient) -> Any:
            if items is None:
                raise ValueError("items is required")
            created_ids: List[str] = []
            ops: List[Dict[str, Any]] = []
            for item in coerce_model_items(items, InterestItemInput):
                payload = _prepare_interest_item(item, created_ids)
                ops.append(
                    patch_ops.op_add(
                        patch_ops.path_section_items_append("interests"), payload
                    )
                )
            items_result = await apply_section_item_patch(
                client, resume_id, "interests", ops, label="Interests"
            )
            return _reshape_interest_items(items_result)

        return await execute_rxresume_operation(
            operation_name=f"add interest: {resume_id}",
            operation_func=_operation,
            ctx=ctx,
        )

    @mcp.tool(
        name="resume.section.interest.item.delete",
        description="Remove one or more interest items by id.",
    )
    async def remove_interest(
        ctx: Context,
        resume_id: str = Field(description="Resume ID"),
        item_ids: Optional[InterestItemIdsInput] = Field(
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
                        patch_ops.path_section_item("interests", item_id)
                    )
                )
            items_result = await apply_section_item_patch(
                client, resume_id, "interests", ops, label="Interests"
            )
            return _reshape_interest_items(items_result)

        return await execute_rxresume_operation(
            operation_name=f"remove interest: {resume_id}",
            operation_func=_operation,
            ctx=ctx,
        )

    @mcp.tool(
        name="resume.section.interest.item.update",
        description=(
            "Update one or more interest items by id. "
            "item.id is required; other fields are optional."
        ),
    )
    async def update_interest(
        ctx: Context,
        resume_id: str = Field(description="Resume ID"),
        items: Optional[InterestItemsInput] = Field(
            default=None,
            description="Interest item or list of items to update.",
        ),
    ) -> Dict[str, Any]:
        async def _operation(client: RxResumeClient) -> Any:
            if items is None:
                raise ValueError("items is required")
            ops: List[Dict[str, Any]] = []
            for item in coerce_model_items(items, InterestItemInput):
                ops.extend(_build_interest_update_ops(item))
            items_result = await apply_section_item_patch(
                client, resume_id, "interests", ops, label="Interests"
            )
            return _reshape_interest_items(items_result)

        return await execute_rxresume_operation(
            operation_name=f"update interest: {resume_id}",
            operation_func=_operation,
            ctx=ctx,
        )
