"""Register tools for listing and editing profile items."""

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
    coerce_item_ids,
    coerce_model_items,
    ensure_non_empty_string,
    extract_section_items,
)
from .tool_helpers import WebsiteInput, normalize_website_payload


class ProfileItemInput(BaseModel):
    model_config = {"extra": "forbid", "populate_by_name": True}

    id: Optional[str] = None
    network: Optional[str] = None
    username: Optional[str] = None
    url: Optional[WebsiteInput] = Field(default=None, alias="website")


ProfileItemsInput = Union[ProfileItemInput, List[ProfileItemInput]]
ProfileItemIdsInput = Union[str, List[str]]


def _reshape_profile_item(payload: Any) -> Any:
    if not isinstance(payload, dict):
        return payload
    normalized: Dict[str, Any] = {
        "id": payload.get("id"),
        "network": payload.get("network", "") or "",
        "username": payload.get("username", "") or "",
        "url": payload.get("website") or normalize_website_payload(None),
    }
    return normalized


def _reshape_profile_items(payload: Any) -> Any:
    if isinstance(payload, list):
        return [_reshape_profile_item(item) for item in payload]
    return payload


def _apply_profile_defaults(payload: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(payload)
    normalized.setdefault("icon", "")
    normalized["network"] = ensure_non_empty_string(normalized.get("network"))
    normalized.setdefault("username", "")
    url_payload = normalized.pop("url", None)
    normalized["website"] = normalize_website_payload(url_payload)
    return normalized


def _prepare_profile_item(
    item: ProfileItemInput, created_ids: List[str]
) -> Dict[str, Any]:
    payload = item.model_dump(exclude_none=True)
    payload = _ensure_object_payload(payload, "item")
    payload["hidden"] = False
    payload = _ensure_item_id(payload, created_ids)
    payload = _apply_profile_defaults(payload)
    payload = cast(Dict[str, Any], _normalize_url_fields(payload))
    return payload


def _build_profile_update_ops(item: ProfileItemInput) -> List[Dict[str, Any]]:
    payload = item.model_dump(exclude_none=True)
    item_id = payload.pop("id", None)
    if not item_id or not isinstance(item_id, str):
        raise ValueError("item.id is required for update")
    ops: List[Dict[str, Any]] = []

    field_values = {
        "network": ("network", ensure_non_empty_string),
        "username": ("username", lambda value: value),
    }
    for field, (target, transform) in field_values.items():
        if field not in payload:
            continue
        ops.append(
            patch_ops.op_replace(
                patch_ops.path_section_item_field("profiles", item_id, target),
                transform(payload.pop(field)),
            )
        )

    if "url" in payload:
        website_payload = normalize_website_payload(payload.pop("url"))
        website_payload = cast(Dict[str, Any], _normalize_url_fields(website_payload))
        base = patch_ops.path_section_item_field("profiles", item_id, "website")
        for key, value in website_payload.items():
            ops.append(patch_ops.op_replace(f"{base}/{key}", value))

    if payload:
        raise ValueError(f"Unexpected fields in profile update: {sorted(payload)}")
    if not ops:
        raise ValueError(f"No fields provided to update for item id: {item_id}")
    return ops


def register_profile_tools(mcp: FastMCP) -> None:
    """Register tools that list or edit profile items."""

    @mcp.tool(
        name="resume.section.profile.list",
        description="List profile items for a resume.",
    )
    async def list_profile(
        ctx: Context,
        resume_id: str = Field(description="Resume ID"),
    ) -> Dict[str, Any]:
        async def _operation(client: RxResumeClient) -> Any:
            resume = _require_resume_object(await client.get_resume(resume_id))
            items = extract_section_items(resume, "profiles", label="Profiles")
            return _reshape_profile_items(items)

        return await execute_rxresume_operation(
            operation_name=f"list profile: {resume_id}",
            operation_func=_operation,
            ctx=ctx,
        )

    @mcp.tool(
        name="resume.section.profile.item.create",
        description=(
            "Add one or more profile items. "
            "All fields are optional; hidden is forced to false."
        ),
    )
    async def add_profile(
        ctx: Context,
        resume_id: str = Field(description="Resume ID"),
        items: Optional[ProfileItemsInput] = Field(
            default=None,
            description="Profile item or list of items to add.",
        ),
    ) -> Dict[str, Any]:
        async def _operation(client: RxResumeClient) -> Any:
            if items is None:
                raise ValueError("items is required")
            created_ids: List[str] = []
            ops: List[Dict[str, Any]] = []
            for item in coerce_model_items(items, ProfileItemInput):
                payload = _prepare_profile_item(item, created_ids)
                ops.append(
                    patch_ops.op_add(
                        patch_ops.path_section_items_append("profiles"), payload
                    )
                )
            result = await apply_section_item_patch(
                client, resume_id, "profiles", ops, label="Profiles"
            )
            return _reshape_profile_items(result)

        return await execute_rxresume_operation(
            operation_name=f"add profile: {resume_id}",
            operation_func=_operation,
            ctx=ctx,
        )

    @mcp.tool(
        name="resume.section.profile.item.delete",
        description="Remove one or more profile items by id.",
    )
    async def remove_profile(
        ctx: Context,
        resume_id: str = Field(description="Resume ID"),
        item_ids: Optional[ProfileItemIdsInput] = Field(
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
                        patch_ops.path_section_item("profiles", item_id)
                    )
                )
            result = await apply_section_item_patch(
                client, resume_id, "profiles", ops, label="Profiles"
            )
            return _reshape_profile_items(result)

        return await execute_rxresume_operation(
            operation_name=f"remove profile: {resume_id}",
            operation_func=_operation,
            ctx=ctx,
        )

    @mcp.tool(
        name="resume.section.profile.item.update",
        description=(
            "Update one or more profile items by id. "
            "item.id is required; other fields are optional."
        ),
    )
    async def update_profile(
        ctx: Context,
        resume_id: str = Field(description="Resume ID"),
        items: Optional[ProfileItemsInput] = Field(
            default=None,
            description="Profile item or list of items to update.",
        ),
    ) -> Dict[str, Any]:
        async def _operation(client: RxResumeClient) -> Any:
            if items is None:
                raise ValueError("items is required")
            ops: List[Dict[str, Any]] = []
            for item in coerce_model_items(items, ProfileItemInput):
                ops.extend(_build_profile_update_ops(item))
            result = await apply_section_item_patch(
                client, resume_id, "profiles", ops, label="Profiles"
            )
            return _reshape_profile_items(result)

        return await execute_rxresume_operation(
            operation_name=f"update profile: {resume_id}",
            operation_func=_operation,
            ctx=ctx,
        )
