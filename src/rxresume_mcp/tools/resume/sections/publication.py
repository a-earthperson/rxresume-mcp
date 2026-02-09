"""Register tools for listing and editing publication items."""

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


class PublicationItemInput(BaseModel):
    model_config = {"extra": "forbid", "populate_by_name": True}

    id: Optional[str] = None
    name: Optional[str] = Field(default=None, alias="title")
    publisher: Optional[str] = None
    period: Optional[str] = Field(default=None, alias="date")
    website: Optional[WebsiteInput] = None
    summary: Optional[str] = None
    highlights: Optional[List[str]] = None


PublicationItemsInput = Union[PublicationItemInput, List[PublicationItemInput]]
PublicationItemIdsInput = Union[str, List[str]]


def _apply_publication_defaults(payload: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(payload)
    name = normalized.pop("name", None)
    normalized["title"] = ensure_non_empty_string(name)
    normalized.setdefault("publisher", "")
    normalized.setdefault("date", "")
    summary = normalized.pop("summary", None)
    highlights = normalized.pop("highlights", None)
    normalized["description"] = build_summary_highlights_description(
        summary, highlights
    )
    normalized["website"] = normalize_website_payload(normalized.get("website"))
    return normalized


def _reshape_publication_item(payload: Any) -> Any:
    if not isinstance(payload, dict):
        return payload
    summary, highlights = split_summary_highlights_description(
        payload.get("description")
    )
    normalized: Dict[str, Any] = {
        "id": payload.get("id"),
        "name": payload.get("title", "") or "",
        "publisher": payload.get("publisher", "") or "",
        "period": payload.get("date", "") or "",
        "website": payload.get("website") or normalize_website_payload(None),
        "summary": summary or "",
        "highlights": highlights or [],
    }
    return normalized


def _reshape_publication_items(payload: Any) -> Any:
    if isinstance(payload, list):
        return [_reshape_publication_item(item) for item in payload]
    return payload


def _prepare_publication_item(
    item: PublicationItemInput, created_ids: List[str]
) -> Dict[str, Any]:
    payload = item.model_dump(exclude_none=True)
    payload = _ensure_object_payload(payload, "item")
    payload["hidden"] = False
    payload = _ensure_item_id(payload, created_ids)
    payload = _apply_publication_defaults(payload)
    payload = cast(Dict[str, Any], _normalize_url_fields(payload))
    return payload


def _build_publication_update_ops(item: PublicationItemInput) -> List[Dict[str, Any]]:
    payload = item.model_dump(exclude_none=True)
    item_id = payload.pop("id", None)
    if not item_id or not isinstance(item_id, str):
        raise ValueError("item.id is required for update")
    ops: List[Dict[str, Any]] = []

    field_values = {
        "name": ("title", ensure_non_empty_string),
        "publisher": ("publisher", lambda value: value),
        "period": ("date", lambda value: value),
    }
    for field, (target, transform) in field_values.items():
        if field not in payload:
            continue
        ops.append(
            patch_ops.op_replace(
                patch_ops.path_section_item_field("publications", item_id, target),
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
                patch_ops.path_section_item_field(
                    "publications", item_id, "description"
                ),
                description,
            )
        )

    if "website" in payload:
        website_payload = normalize_website_payload(payload.pop("website"))
        website_payload = cast(Dict[str, Any], _normalize_url_fields(website_payload))
        base = patch_ops.path_section_item_field("publications", item_id, "website")
        for key, value in website_payload.items():
            ops.append(patch_ops.op_replace(f"{base}/{key}", value))

    if payload:
        raise ValueError(f"Unexpected fields in publication update: {sorted(payload)}")
    if not ops:
        raise ValueError(f"No fields provided to update for item id: {item_id}")
    return ops


def register_publication_tools(mcp: FastMCP) -> None:
    """Register tools that list or edit publication items."""

    @mcp.tool(
        name="resume.section.publication.list",
        description="List publication items for a resume.",
    )
    async def list_publication(
        ctx: Context,
        resume_id: str = Field(description="Resume ID"),
    ) -> Dict[str, Any]:
        async def _operation(client: RxResumeClient) -> Any:
            resume = _require_resume_object(await client.get_resume(resume_id))
            items = extract_section_items(resume, "publications", label="Publications")
            return _reshape_publication_items(items)

        return await execute_rxresume_operation(
            operation_name=f"list publication: {resume_id}",
            operation_func=_operation,
            ctx=ctx,
        )

    @mcp.tool(
        name="resume.section.publication.item.create",
        description=(
            "Add one or more publication items. "
            "All fields are optional; hidden is forced to false."
        ),
    )
    async def add_publication(
        ctx: Context,
        resume_id: str = Field(description="Resume ID"),
        items: Optional[PublicationItemsInput] = Field(
            default=None,
            description="Publication item or list of items to add.",
        ),
    ) -> Dict[str, Any]:
        async def _operation(client: RxResumeClient) -> Any:
            if items is None:
                raise ValueError("items is required")
            created_ids: List[str] = []
            ops: List[Dict[str, Any]] = []
            for item in coerce_model_items(items, PublicationItemInput):
                payload = _prepare_publication_item(item, created_ids)
                ops.append(
                    patch_ops.op_add(
                        patch_ops.path_section_items_append("publications"), payload
                    )
                )
            result = await apply_section_item_patch(
                client, resume_id, "publications", ops, label="Publications"
            )
            return _reshape_publication_items(result)

        return await execute_rxresume_operation(
            operation_name=f"add publication: {resume_id}",
            operation_func=_operation,
            ctx=ctx,
        )

    @mcp.tool(
        name="resume.section.publication.item.delete",
        description="Remove one or more publication items by id.",
    )
    async def remove_publication(
        ctx: Context,
        resume_id: str = Field(description="Resume ID"),
        item_ids: Optional[PublicationItemIdsInput] = Field(
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
                        patch_ops.path_section_item("publications", item_id)
                    )
                )
            result = await apply_section_item_patch(
                client, resume_id, "publications", ops, label="Publications"
            )
            return _reshape_publication_items(result)

        return await execute_rxresume_operation(
            operation_name=f"remove publication: {resume_id}",
            operation_func=_operation,
            ctx=ctx,
        )

    @mcp.tool(
        name="resume.section.publication.item.update",
        description=(
            "Update one or more publication items by id. "
            "item.id is required; other fields are optional."
        ),
    )
    async def update_publication(
        ctx: Context,
        resume_id: str = Field(description="Resume ID"),
        items: Optional[PublicationItemsInput] = Field(
            default=None,
            description="Publication item or list of items to update.",
        ),
    ) -> Dict[str, Any]:
        async def _operation(client: RxResumeClient) -> Any:
            if items is None:
                raise ValueError("items is required")
            ops: List[Dict[str, Any]] = []
            for item in coerce_model_items(items, PublicationItemInput):
                ops.extend(_build_publication_update_ops(item))
            result = await apply_section_item_patch(
                client, resume_id, "publications", ops, label="Publications"
            )
            return _reshape_publication_items(result)

        return await execute_rxresume_operation(
            operation_name=f"update publication: {resume_id}",
            operation_func=_operation,
            ctx=ctx,
        )
