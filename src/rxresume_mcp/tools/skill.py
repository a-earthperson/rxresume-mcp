"""Register tools for listing and editing skill items."""

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


class SkillItemInput(BaseModel):
    model_config = {"extra": "forbid"}

    id: Optional[str] = None
    name: Optional[str] = None
    proficiency: Optional[str] = None
    level: Optional[float] = None
    keywords: Optional[List[str]] = None


SkillItemsInput = Union[SkillItemInput, List[SkillItemInput]]
SkillItemIdsInput = Union[str, List[str]]


def _apply_skill_defaults(payload: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(payload)
    normalized["icon"] = ""
    normalized["name"] = ensure_non_empty_string(normalized.get("name"))
    normalized.setdefault("proficiency", "")
    normalized.setdefault("level", 0)
    normalized.setdefault("keywords", [])
    return normalized


def _reshape_skill_item(payload: Any) -> Any:
    if not isinstance(payload, dict):
        return payload
    normalized: Dict[str, Any] = {
        "id": payload.get("id"),
        "name": payload.get("name", "") or "",
        "proficiency": payload.get("proficiency", "") or "",
        "level": payload.get("level", 0),
        "keywords": payload.get("keywords", []) or [],
    }
    return normalized


def _reshape_skill_items(payload: Any) -> Any:
    if isinstance(payload, list):
        return [_reshape_skill_item(item) for item in payload]
    return payload


def _prepare_skill_item(
    item: SkillItemInput, created_ids: List[str]
) -> Dict[str, Any]:
    payload = item.model_dump(exclude_none=True)
    payload = _ensure_object_payload(payload, "item")
    payload["hidden"] = False
    payload = _ensure_item_id(payload, created_ids)
    payload = _apply_skill_defaults(payload)
    return payload


def _build_skill_update_ops(item: SkillItemInput) -> List[Dict[str, Any]]:
    payload = item.model_dump(exclude_none=True)
    item_id = payload.pop("id", None)
    if not item_id or not isinstance(item_id, str):
        raise ValueError("item.id is required for update")
    ops: List[Dict[str, Any]] = []

    field_values = {
        "name": ("name", ensure_non_empty_string),
        "proficiency": ("proficiency", lambda value: value),
        "level": ("level", lambda value: value),
        "keywords": ("keywords", lambda value: value),
    }
    for field, (target, transform) in field_values.items():
        if field not in payload:
            continue
        ops.append(
            patch_ops.op_replace(
                patch_ops.path_section_item_field("skills", item_id, target),
                transform(payload.pop(field)),
            )
        )

    if payload:
        raise ValueError(f"Unexpected fields in skill update: {sorted(payload)}")
    if not ops:
        raise ValueError(f"No fields provided to update for item id: {item_id}")
    return ops


def register_skill_tools(mcp: FastMCP) -> None:
    """Register tools that list or edit skill items."""

    @mcp.tool(
        name="resume.section.skill.list",
        description="List skill items for a resume.",
    )
    async def list_skill(
        ctx: Context,
        resume_id: str = Field(description="Resume ID"),
    ) -> Dict[str, Any]:
        async def _operation(client: RxResumeClient) -> Any:
            resume = _require_resume_object(await client.get_resume(resume_id))
            items = extract_section_items(resume, "skills", label="Skills")
            return _reshape_skill_items(items)

        return await execute_rxresume_operation(
            operation_name=f"list skill: {resume_id}",
            operation_func=_operation,
            ctx=ctx,
        )

    @mcp.tool(
        name="resume.section.skill.item.create",
        description=(
            "Add one or more skill items. "
            "All fields are optional; hidden is forced to false."
        ),
    )
    async def add_skill(
        ctx: Context,
        resume_id: str = Field(description="Resume ID"),
        items: Optional[SkillItemsInput] = Field(
            default=None,
            description="Skill item or list of items to add.",
        ),
    ) -> Dict[str, Any]:
        async def _operation(client: RxResumeClient) -> Any:
            if items is None:
                raise ValueError("items is required")
            created_ids: List[str] = []
            ops: List[Dict[str, Any]] = []
            for item in coerce_model_items(items, SkillItemInput):
                payload = _prepare_skill_item(item, created_ids)
                ops.append(
                    patch_ops.op_add(
                        patch_ops.path_section_items_append("skills"), payload
                    )
                )
            items_result = await apply_section_item_patch(
                client, resume_id, "skills", ops, label="Skills"
            )
            return _reshape_skill_items(items_result)

        return await execute_rxresume_operation(
            operation_name=f"add skill: {resume_id}",
            operation_func=_operation,
            ctx=ctx,
        )

    @mcp.tool(
        name="resume.section.skill.item.delete",
        description="Remove one or more skill items by id.",
    )
    async def remove_skill(
        ctx: Context,
        resume_id: str = Field(description="Resume ID"),
        item_ids: Optional[SkillItemIdsInput] = Field(
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
                        patch_ops.path_section_item("skills", item_id)
                    )
                )
            items_result = await apply_section_item_patch(
                client, resume_id, "skills", ops, label="Skills"
            )
            return _reshape_skill_items(items_result)

        return await execute_rxresume_operation(
            operation_name=f"remove skill: {resume_id}",
            operation_func=_operation,
            ctx=ctx,
        )

    @mcp.tool(
        name="resume.section.skill.item.update",
        description=(
            "Update one or more skill items by id. "
            "item.id is required; other fields are optional."
        ),
    )
    async def update_skill(
        ctx: Context,
        resume_id: str = Field(description="Resume ID"),
        items: Optional[SkillItemsInput] = Field(
            default=None,
            description="Skill item or list of items to update.",
        ),
    ) -> Dict[str, Any]:
        async def _operation(client: RxResumeClient) -> Any:
            if items is None:
                raise ValueError("items is required")
            ops: List[Dict[str, Any]] = []
            for item in coerce_model_items(items, SkillItemInput):
                ops.extend(_build_skill_update_ops(item))
            items_result = await apply_section_item_patch(
                client, resume_id, "skills", ops, label="Skills"
            )
            return _reshape_skill_items(items_result)

        return await execute_rxresume_operation(
            operation_name=f"update skill: {resume_id}",
            operation_func=_operation,
            ctx=ctx,
        )
