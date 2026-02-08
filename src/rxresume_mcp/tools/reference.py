"""Register tools for listing and editing reference items."""

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


class ReferenceItemInput(BaseModel):
    model_config = {"extra": "forbid", "populate_by_name": True}

    id: Optional[str] = None
    name: Optional[str] = None
    position: Optional[str] = None
    website: Optional[WebsiteInput] = None
    contact: Optional[str] = Field(default=None, alias="phone")
    summary: Optional[str] = Field(default=None, alias="description")


ReferenceItemsInput = Union[ReferenceItemInput, List[ReferenceItemInput]]
ReferenceItemIdsInput = Union[str, List[str]]


def _apply_reference_defaults(payload: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(payload)
    normalized["name"] = ensure_non_empty_string(normalized.get("name"))
    normalized.setdefault("position", "")
    normalized["phone"] = normalized.pop("contact", "")
    normalized["description"] = normalized.pop("summary", "")
    website_value = normalized.pop("website", None)
    normalized["website"] = normalize_website_payload(website_value)
    return normalized


def _reshape_reference_item(payload: Any) -> Any:
    if not isinstance(payload, dict):
        return payload
    normalized: Dict[str, Any] = {
        "id": payload.get("id"),
        "name": payload.get("name", "") or "",
        "position": payload.get("position", "") or "",
        "website": payload.get("website") or normalize_website_payload(None),
        "contact": payload.get("phone", "") or "",
        "summary": payload.get("description", "") or "",
    }
    return normalized


def _reshape_reference_items(payload: Any) -> Any:
    if isinstance(payload, list):
        return [_reshape_reference_item(item) for item in payload]
    return payload


def _prepare_reference_item(
    item: ReferenceItemInput, created_ids: List[str]
) -> Dict[str, Any]:
    payload = item.model_dump(exclude_none=True)
    payload = _ensure_object_payload(payload, "item")
    payload["hidden"] = False
    payload = _ensure_item_id(payload, created_ids)
    payload = _apply_reference_defaults(payload)
    payload = cast(Dict[str, Any], _normalize_url_fields(payload))
    return payload


def _build_reference_update_ops(item: ReferenceItemInput) -> List[Dict[str, Any]]:
    payload = item.model_dump(exclude_none=True)
    item_id = payload.pop("id", None)
    if not item_id or not isinstance(item_id, str):
        raise ValueError("item.id is required for update")
    ops: List[Dict[str, Any]] = []

    field_values = {
        "name": ("name", ensure_non_empty_string),
        "position": ("position", lambda value: value),
        "contact": ("phone", lambda value: value),
        "summary": ("description", lambda value: value),
    }
    for field, (target, transform) in field_values.items():
        if field not in payload:
            continue
        ops.append(
            patch_ops.op_replace(
                patch_ops.path_section_item_field("references", item_id, target),
                transform(payload.pop(field)),
            )
        )

    if "website" in payload:
        website_payload = normalize_website_payload(payload.pop("website"))
        website_payload = cast(Dict[str, Any], _normalize_url_fields(website_payload))
        base = patch_ops.path_section_item_field("references", item_id, "website")
        for key, value in website_payload.items():
            ops.append(patch_ops.op_replace(f"{base}/{key}", value))

    if payload:
        raise ValueError(f"Unexpected fields in reference update: {sorted(payload)}")
    if not ops:
        raise ValueError(f"No fields provided to update for item id: {item_id}")
    return ops


def register_reference_tools(mcp: FastMCP) -> None:
    """Register tools that list or edit reference items."""

    @mcp.tool(
        name="resume.section.reference.list",
        description="List reference items for a resume.",
    )
    async def list_reference(
        ctx: Context,
        resume_id: str = Field(description="Resume ID"),
    ) -> Dict[str, Any]:
        async def _operation(client: RxResumeClient) -> Any:
            resume = _require_resume_object(await client.get_resume(resume_id))
            items = extract_section_items(resume, "references", label="References")
            return _reshape_reference_items(items)

        return await execute_rxresume_operation(
            operation_name=f"list reference: {resume_id}",
            operation_func=_operation,
            ctx=ctx,
        )

    @mcp.tool(
        name="resume.section.project.item.create",
        description=(
            "Add one or more reference items. "
            "All fields are optional; hidden is forced to false."
        ),
    )
    async def add_reference(
        ctx: Context,
        resume_id: str = Field(description="Resume ID"),
        items: Optional[ReferenceItemsInput] = Field(
            default=None,
            description="Reference item or list of items to add.",
        ),
    ) -> Dict[str, Any]:
        async def _operation(client: RxResumeClient) -> Any:
            if items is None:
                raise ValueError("items is required")
            created_ids: List[str] = []
            ops: List[Dict[str, Any]] = []
            for item in coerce_model_items(items, ReferenceItemInput):
                payload = _prepare_reference_item(item, created_ids)
                ops.append(
                    patch_ops.op_add(
                        patch_ops.path_section_items_append("references"), payload
                    )
                )
            result = await apply_section_item_patch(
                client, resume_id, "references", ops, label="References"
            )
            return _reshape_reference_items(result)

        return await execute_rxresume_operation(
            operation_name=f"add reference: {resume_id}",
            operation_func=_operation,
            ctx=ctx,
        )

    @mcp.tool(
        name="resume.section.project.item.delete",
        description="Remove one or more reference items by id.",
    )
    async def remove_reference(
        ctx: Context,
        resume_id: str = Field(description="Resume ID"),
        item_ids: Optional[ReferenceItemIdsInput] = Field(
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
                        patch_ops.path_section_item("references", item_id)
                    )
                )
            result = await apply_section_item_patch(
                client, resume_id, "references", ops, label="References"
            )
            return _reshape_reference_items(result)

        return await execute_rxresume_operation(
            operation_name=f"remove reference: {resume_id}",
            operation_func=_operation,
            ctx=ctx,
        )

    @mcp.tool(
        name="resume.section.project.item.update",
        description=(
            "Update one or more reference items by id. "
            "item.id is required; other fields are optional."
        ),
    )
    async def update_reference(
        ctx: Context,
        resume_id: str = Field(description="Resume ID"),
        items: Optional[ReferenceItemsInput] = Field(
            default=None,
            description="Reference item or list of items to update.",
        ),
    ) -> Dict[str, Any]:
        async def _operation(client: RxResumeClient) -> Any:
            if items is None:
                raise ValueError("items is required")
            ops: List[Dict[str, Any]] = []
            for item in coerce_model_items(items, ReferenceItemInput):
                ops.extend(_build_reference_update_ops(item))
            result = await apply_section_item_patch(
                client, resume_id, "references", ops, label="References"
            )
            return _reshape_reference_items(result)

        return await execute_rxresume_operation(
            operation_name=f"update reference: {resume_id}",
            operation_func=_operation,
            ctx=ctx,
        )
