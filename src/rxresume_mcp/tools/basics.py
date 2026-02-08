"""Register tools for editing resume basics."""

from __future__ import annotations

from typing import Any, Dict, Optional, cast

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

from rxresume_mcp import patch_ops
from rxresume_mcp.rxresume_client import RxResumeClient

from .core import execute_rxresume_operation
from .normalize import _normalize_url_fields
from .sections import _extract_section_data, _require_resume_object
from .tool_helpers import WebsiteInputLike, coerce_website_input


def _build_basics_patch_ops(
    *,
    name: Optional[str],
    label: Optional[str],
    email: Optional[str],
    phone: Optional[str],
    location: Optional[str],
    website: Optional[WebsiteInputLike],
    summary: Optional[str],
) -> list[Dict[str, Any]]:
    """Create patch operations for basics updates."""
    ops: list[Dict[str, Any]] = []
    field_values = {
        "name": name,
        "headline": label,
        "email": email,
        "phone": phone,
        "location": location,
    }
    for field, value in field_values.items():
        if value is None:
            continue
        ops.append(patch_ops.op_replace(patch_ops.path_basics_field(field), value))
    if website is not None:
        website_payload = coerce_website_input(website, require_url=False)
        website_payload = cast(
            Dict[str, str], _normalize_url_fields(website_payload)
        )
        ops.append(
            patch_ops.op_replace(
                patch_ops.path_basics_field("website"), website_payload
            )
        )
    if summary is not None:
        ops.append(
            patch_ops.op_replace(patch_ops.path_summary_field("content"), summary)
        )
    return ops


_BASICS_RESPONSE_MISSING = object()


def _build_basics_response(
    payload: Any, *, summary_content: Any = _BASICS_RESPONSE_MISSING
) -> Any:
    """Normalize basics response payload for MCP clients."""
    if isinstance(payload, dict):
        normalized = dict(payload)
        normalized.pop("customFields", None)
        if "headline" in normalized:
            normalized["label"] = normalized.pop("headline")
        if summary_content is not _BASICS_RESPONSE_MISSING:
            normalized["summary"] = summary_content
        return normalized
    return payload


def register_basics_tools(mcp: FastMCP) -> None:
    """Register tools that edit basics fields."""

    @mcp.tool(
        name="resume.basics.get",
        description="Get resume basics fields.",
    )
    async def get_basics(
        ctx: Context,
        resume_id: str = Field(description="Resume ID"),
    ) -> Dict[str, Any]:
        async def _operation(client: RxResumeClient) -> Any:
            resume = _require_resume_object(await client.get_resume(resume_id))
            basics = _extract_section_data(resume, "basics")["data"]
            summary_data = _extract_section_data(resume, "summary")["data"]
            summary_content = (
                summary_data.get("content")
                if isinstance(summary_data, dict)
                else None
            )
            return _build_basics_response(basics, summary_content=summary_content)

        return await execute_rxresume_operation(
            operation_name=f"get basics: {resume_id}",
            operation_func=_operation,
            ctx=ctx,
        )

    @mcp.tool(
        name="resume.basics.update",
        description=(
            "Update resume basics fields. "
            "All fields are optional; website accepts a string or {url,label}."
        ),
    )
    async def update_basics(
        ctx: Context,
        resume_id: str = Field(description="Resume ID"),
        name: Optional[str] = Field(default=None, description="Person name"),
        label: Optional[str] = Field(default=None, description="Headline/title"),
        email: Optional[str] = Field(default=None, description="Email address"),
        phone: Optional[str] = Field(default=None, description="Phone number"),
        location: Optional[str] = Field(default=None, description="Location string"),
        website: Optional[WebsiteInputLike] = Field(
            default=None,
            description="Website URL string or object with url and optional label.",
        ),
        summary: Optional[str] = Field(
            default=None,
            description="HTML-formatted summary content",
        ),
    ) -> Dict[str, Any]:
        async def _operation(client: RxResumeClient) -> Any:
            ops = _build_basics_patch_ops(
                name=name,
                label=label,
                email=email,
                phone=phone,
                location=location,
                website=website,
                summary=summary,
            )
            if not ops:
                raise ValueError(
                    "No basics fields provided to update."
                )
            ops.append(
                patch_ops.op_replace(
                    patch_ops.path_basics_field("customFields"), []
                )
            )
            validated_ops = patch_ops.validate_patch_ops(ops)
            result = await client.patch_resume(resume_id, patch_ops=validated_ops)
            resume = _require_resume_object(result)
            basics = _extract_section_data(resume, "basics")["data"]
            summary_data = _extract_section_data(resume, "summary")["data"]
            summary_content = (
                summary_data.get("content")
                if isinstance(summary_data, dict)
                else None
            )
            return _build_basics_response(basics, summary_content=summary_content)

        return await execute_rxresume_operation(
            operation_name=f"update basics: {resume_id}",
            operation_func=_operation,
            ctx=ctx,
        )

    @mcp.tool(
        name="resume.basics.create",
        description=(
            "Create resume basics fields. "
            "All fields are optional; website accepts a string or {url,label}."
        ),
    )
    async def create_basics(
        ctx: Context,
        resume_id: str = Field(description="Resume ID"),
        name: Optional[str] = Field(default=None, description="Person name"),
        label: Optional[str] = Field(default=None, description="Headline/title"),
        email: Optional[str] = Field(default=None, description="Email address"),
        phone: Optional[str] = Field(default=None, description="Phone number"),
        location: Optional[str] = Field(default=None, description="Location string"),
        website: Optional[WebsiteInputLike] = Field(
            default=None,
            description="Website URL string or object with url and optional label.",
        ),
        summary: Optional[str] = Field(
            default=None,
            description="HTML-formatted summary content",
        ),
    ) -> Dict[str, Any]:
        return await update_basics(
            ctx=ctx,
            resume_id=resume_id,
            name=name,
            label=label,
            email=email,
            phone=phone,
            location=location,
            website=website,
            summary=summary,
        )

    @mcp.tool(
        name="resume.basics.delete",
        description="Reset resume basics fields to empty values.",
    )
    async def delete_basics(
        ctx: Context,
        resume_id: str = Field(description="Resume ID"),
    ) -> Dict[str, Any]:
        return await update_basics(
            ctx=ctx,
            resume_id=resume_id,
            name="",
            label="",
            email="",
            phone="",
            location="",
            website={"url": "", "label": ""},
            summary="",
        )
