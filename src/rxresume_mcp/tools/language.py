"""Register tools for listing and editing language items."""

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


class LanguageItemInput(BaseModel):
    model_config = {"extra": "forbid", "populate_by_name": True}

    id: Optional[str] = None
    name: Optional[str] = Field(default=None, alias="language")
    proficiency: Optional[str] = Field(default=None, alias="fluency")
    level: Optional[float] = None


LanguageItemsInput = Union[LanguageItemInput, List[LanguageItemInput]]
LanguageItemIdsInput = Union[str, List[str]]


def _reshape_language_item(payload: Any) -> Any:
    if not isinstance(payload, dict):
        return payload
    normalized: Dict[str, Any] = {
        "id": payload.get("id"),
        "name": payload.get("language", "") or "",
        "proficiency": payload.get("fluency", "") or "",
        "level": payload.get("level", 0) or 0,
    }
    return normalized


def _reshape_language_items(payload: Any) -> Any:
    if isinstance(payload, list):
        return [_reshape_language_item(item) for item in payload]
    return payload


def _apply_language_defaults(payload: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(payload)
    name = normalized.pop("name", None)
    normalized["language"] = ensure_non_empty_string(name)
    normalized.setdefault("fluency", "")
    normalized.setdefault("level", 0)
    return normalized


def _prepare_language_item(
    item: LanguageItemInput, created_ids: List[str]
) -> Dict[str, Any]:
    payload = item.model_dump(exclude_none=True)
    payload = _ensure_object_payload(payload, "item")
    payload["hidden"] = False
    payload = _ensure_item_id(payload, created_ids)
    payload = _apply_language_defaults(payload)
    return payload


def _build_language_update_ops(item: LanguageItemInput) -> List[Dict[str, Any]]:
    payload = item.model_dump(exclude_none=True)
    item_id = payload.pop("id", None)
    if not item_id or not isinstance(item_id, str):
        raise ValueError("item.id is required for update")
    ops: List[Dict[str, Any]] = []

    field_values = {
        "name": ("language", ensure_non_empty_string),
        "proficiency": ("fluency", lambda value: value),
        "level": ("level", lambda value: value),
    }
    for field, (target, transform) in field_values.items():
        if field not in payload:
            continue
        ops.append(
            patch_ops.op_replace(
                patch_ops.path_section_item_field("languages", item_id, target),
                transform(payload.pop(field)),
            )
        )

    if payload:
        raise ValueError(f"Unexpected fields in language update: {sorted(payload)}")
    if not ops:
        raise ValueError(f"No fields provided to update for item id: {item_id}")
    return ops


def register_language_tools(mcp: FastMCP) -> None:
    """Register tools that list or edit language items."""

    @mcp.tool(
        name="resume.section.language.list",
        description="List language items for a resume.",
    )
    async def list_language(
        ctx: Context,
        resume_id: str = Field(description="Resume ID"),
    ) -> Dict[str, Any]:
        async def _operation(client: RxResumeClient) -> Any:
            resume = _require_resume_object(await client.get_resume(resume_id))
            items = extract_section_items(resume, "languages", label="Languages")
            return _reshape_language_items(items)

        return await execute_rxresume_operation(
            operation_name=f"list language: {resume_id}",
            operation_func=_operation,
            ctx=ctx,
        )

    @mcp.tool(
        name="resume.section.language.item.create",
        description=(
            "Add one or more language items. "
            "All fields are optional; hidden is forced to false."
        ),
    )
    async def add_language(
        ctx: Context,
        resume_id: str = Field(description="Resume ID"),
        items: Optional[LanguageItemsInput] = Field(
            default=None,
            description="Language item or list of items to add.",
        ),
    ) -> Dict[str, Any]:
        async def _operation(client: RxResumeClient) -> Any:
            if items is None:
                raise ValueError("items is required")
            created_ids: List[str] = []
            ops: List[Dict[str, Any]] = []
            for item in coerce_model_items(items, LanguageItemInput):
                payload = _prepare_language_item(item, created_ids)
                ops.append(
                    patch_ops.op_add(
                        patch_ops.path_section_items_append("languages"), payload
                    )
                )
            result = await apply_section_item_patch(
                client, resume_id, "languages", ops, label="Languages"
            )
            return _reshape_language_items(result)

        return await execute_rxresume_operation(
            operation_name=f"add language: {resume_id}",
            operation_func=_operation,
            ctx=ctx,
        )

    @mcp.tool(
        name="resume.section.language.item.delete",
        description="Remove one or more language items by id.",
    )
    async def remove_language(
        ctx: Context,
        resume_id: str = Field(description="Resume ID"),
        item_ids: Optional[LanguageItemIdsInput] = Field(
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
                        patch_ops.path_section_item("languages", item_id)
                    )
                )
            return await apply_section_item_patch(
                client, resume_id, "languages", ops, label="Languages"
            )

        return await execute_rxresume_operation(
            operation_name=f"remove language: {resume_id}",
            operation_func=_operation,
            ctx=ctx,
        )

    @mcp.tool(
        name="resume.section.language.item.update",
        description=(
            "Update one or more language items by id. "
            "item.id is required; other fields are optional."
        ),
    )
    async def update_language(
        ctx: Context,
        resume_id: str = Field(description="Resume ID"),
        items: Optional[LanguageItemsInput] = Field(
            default=None,
            description="Language item or list of items to update.",
        ),
    ) -> Dict[str, Any]:
        async def _operation(client: RxResumeClient) -> Any:
            if items is None:
                raise ValueError("items is required")
            ops: List[Dict[str, Any]] = []
            for item in coerce_model_items(items, LanguageItemInput):
                ops.extend(_build_language_update_ops(item))
            result = await apply_section_item_patch(
                client, resume_id, "languages", ops, label="Languages"
            )
            return _reshape_language_items(result)

        return await execute_rxresume_operation(
            operation_name=f"update language: {resume_id}",
            operation_func=_operation,
            ctx=ctx,
        )
