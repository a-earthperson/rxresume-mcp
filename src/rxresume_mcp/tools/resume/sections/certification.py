"""Register tools for listing and editing certification items."""

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


class CertificationItemInput(BaseModel):
    model_config = {"extra": "forbid", "populate_by_name": True}

    id: Optional[str] = None
    name: Optional[str] = Field(default=None, alias="title")
    issuer: Optional[str] = None
    period: Optional[str] = Field(default=None, alias="date")
    website: Optional[WebsiteInput] = None
    summary: Optional[str] = Field(default=None, alias="description")


CertificationItemsInput = Union[CertificationItemInput, List[CertificationItemInput]]
CertificationItemIdsInput = Union[str, List[str]]


def _reshape_certification_item(payload: Any) -> Any:
    if not isinstance(payload, dict):
        return payload
    normalized: Dict[str, Any] = {
        "id": payload.get("id"),
        "name": payload.get("title", "") or "",
        "issuer": payload.get("issuer", "") or "",
        "period": payload.get("date", "") or "",
        "website": payload.get("website") or normalize_website_payload(None),
        "summary": payload.get("description", "") or "",
    }
    return normalized


def _reshape_certification_items(payload: Any) -> Any:
    if isinstance(payload, list):
        return [_reshape_certification_item(item) for item in payload]
    return payload


def _apply_certification_defaults(payload: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(payload)
    name = normalized.pop("name", None)
    normalized["title"] = ensure_non_empty_string(name)
    normalized.setdefault("issuer", "")
    normalized.setdefault("date", "")
    summary = normalized.pop("summary", None)
    normalized["description"] = summary if summary is not None else ""
    normalized["website"] = normalize_website_payload(normalized.get("website"))
    return normalized


def _prepare_certification_item(
    item: CertificationItemInput, created_ids: List[str]
) -> Dict[str, Any]:
    payload = item.model_dump(exclude_none=True)
    payload = _ensure_object_payload(payload, "item")
    payload["hidden"] = False
    payload = _ensure_item_id(payload, created_ids)
    payload = _apply_certification_defaults(payload)
    payload = cast(Dict[str, Any], _normalize_url_fields(payload))
    return payload


def _build_certification_update_ops(
    item: CertificationItemInput,
) -> List[Dict[str, Any]]:
    payload = item.model_dump(exclude_none=True)
    item_id = payload.pop("id", None)
    if not item_id or not isinstance(item_id, str):
        raise ValueError("item.id is required for update")
    ops: List[Dict[str, Any]] = []

    field_values = {
        "name": ("title", ensure_non_empty_string),
        "issuer": ("issuer", lambda value: value),
        "period": ("date", lambda value: value),
        "summary": ("description", lambda value: value),
    }
    for field, (target, transform) in field_values.items():
        if field not in payload:
            continue
        ops.append(
            patch_ops.op_replace(
                patch_ops.path_section_item_field("certifications", item_id, target),
                transform(payload.pop(field)),
            )
        )

    if "website" in payload:
        website_payload = normalize_website_payload(payload.pop("website"))
        website_payload = cast(Dict[str, Any], _normalize_url_fields(website_payload))
        base = patch_ops.path_section_item_field(
            "certifications", item_id, "website"
        )
        for key, value in website_payload.items():
            ops.append(patch_ops.op_replace(f"{base}/{key}", value))

    if payload:
        raise ValueError(
            f"Unexpected fields in certification update: {sorted(payload)}"
        )
    if not ops:
        raise ValueError(f"No fields provided to update for item id: {item_id}")
    return ops


def register_certification_tools(mcp: FastMCP) -> None:
    """Register tools that list or edit certification items."""

    @mcp.tool(
        name="resume.section.certification.list",
        description="List certification items for a resume.",
    )
    async def list_certification(
        ctx: Context,
        resume_id: str = Field(description="Resume ID"),
    ) -> Dict[str, Any]:
        async def _operation(client: RxResumeClient) -> Any:
            resume = _require_resume_object(await client.get_resume(resume_id))
            items = extract_section_items(
                resume, "certifications", label="Certifications"
            )
            return _reshape_certification_items(items)

        return await execute_rxresume_operation(
            operation_name=f"list certification: {resume_id}",
            operation_func=_operation,
            ctx=ctx,
        )

    @mcp.tool(
        name="resume.section.certification.item.create",
        description=(
            "Add one or more certification items. "
            "All fields are optional; hidden is forced to false."
        ),
    )
    async def add_certification(
        ctx: Context,
        resume_id: str = Field(description="Resume ID"),
        items: Optional[CertificationItemsInput] = Field(
            default=None,
            description="Certification item or list of items to add.",
        ),
    ) -> Dict[str, Any]:
        async def _operation(client: RxResumeClient) -> Any:
            if items is None:
                raise ValueError("items is required")
            created_ids: List[str] = []
            ops: List[Dict[str, Any]] = []
            for item in coerce_model_items(items, CertificationItemInput):
                payload = _prepare_certification_item(item, created_ids)
                ops.append(
                    patch_ops.op_add(
                        patch_ops.path_section_items_append("certifications"),
                        payload,
                    )
                )
            result = await apply_section_item_patch(
                client, resume_id, "certifications", ops, label="Certifications"
            )
            return _reshape_certification_items(result)

        return await execute_rxresume_operation(
            operation_name=f"add certification: {resume_id}",
            operation_func=_operation,
            ctx=ctx,
        )

    @mcp.tool(
        name="resume.section.certification.item.delete",
        description="Remove one or more certification items by id.",
    )
    async def remove_certification(
        ctx: Context,
        resume_id: str = Field(description="Resume ID"),
        item_ids: Optional[CertificationItemIdsInput] = Field(
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
                        patch_ops.path_section_item("certifications", item_id)
                    )
                )
            result = await apply_section_item_patch(
                client, resume_id, "certifications", ops, label="Certifications"
            )
            return _reshape_certification_items(result)

        return await execute_rxresume_operation(
            operation_name=f"remove certification: {resume_id}",
            operation_func=_operation,
            ctx=ctx,
        )

    @mcp.tool(
        name="resume.section.certification.item.update",
        description=(
            "Update one or more certification items by id. "
            "item.id is required; other fields are optional."
        ),
    )
    async def update_certification(
        ctx: Context,
        resume_id: str = Field(description="Resume ID"),
        items: Optional[CertificationItemsInput] = Field(
            default=None,
            description="Certification item or list of items to update.",
        ),
    ) -> Dict[str, Any]:
        async def _operation(client: RxResumeClient) -> Any:
            if items is None:
                raise ValueError("items is required")
            ops: List[Dict[str, Any]] = []
            for item in coerce_model_items(items, CertificationItemInput):
                ops.extend(_build_certification_update_ops(item))
            result = await apply_section_item_patch(
                client, resume_id, "certifications", ops, label="Certifications"
            )
            return _reshape_certification_items(result)

        return await execute_rxresume_operation(
            operation_name=f"update certification: {resume_id}",
            operation_func=_operation,
            ctx=ctx,
        )
