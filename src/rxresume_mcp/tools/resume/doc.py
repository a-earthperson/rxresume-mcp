"""Register resume document tools."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

from rxresume_mcp.client import RxResumeClient

from ..core import execute_rxresume_operation, format_response
from .common import _reshape_resume


def _build_resume_list_params(
    tags: List[str], sort: Optional[str]
) -> Dict[str, Any]:
    return {"tags": tags, "sort": sort}


def _reshape_resume_list(payload: Any) -> Any:
    return payload


def _prepare_resume_create_payload(
    name: str, slug: str, tags: List[str], with_sample_data: bool
) -> Dict[str, Any]:
    return {
        "name": name,
        "slug": slug,
        "tags": tags,
        "with_sample_data": with_sample_data,
    }


def _apply_resume_create_defaults(payload: Dict[str, Any]) -> Dict[str, Any]:
    return dict(payload)


def _build_resume_update_payload(
    name: Optional[str],
    slug: Optional[str],
    tags: Optional[List[str]],
    data: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    return {"name": name, "slug": slug, "tags": tags, "data_patch": data}


def _apply_resume_update_defaults(payload: Dict[str, Any]) -> Dict[str, Any]:
    return dict(payload)


def _reshape_resume_create_response(payload: Dict[str, Any]) -> Dict[str, Any]:
    return payload


def register_resume_doc_tools(mcp: FastMCP) -> None:
    """Register tools that operate on resume documents."""

    @mcp.tool(
        name="resume.doc.list",
        description="List resumes, optionally filtering by tags and sort order",
    )
    async def list_resumes(
        ctx: Context,
        tags: List[str] = Field(
            description="Optional list of tags to filter by",
            default_factory=list,
        ),
        sort: Optional[str] = Field(
            description="Sort order: 'lastUpdatedAt' (desc), 'createdAt', or 'name'",
            default=None,
        ),
    ) -> Dict[str, Any]:
        async def _operation(client: RxResumeClient) -> Any:
            params = _build_resume_list_params(tags, sort)
            result = await client.list_resumes(**params)
            return _reshape_resume_list(result)

        return await execute_rxresume_operation(
            operation_name="resume.list",
            operation_func=_operation,
            ctx=ctx,
        )

    @mcp.tool(name="resume.doc.get", description="Fetch a resume by ID")
    async def get_resume(
        ctx: Context,
        resume_id: str = Field(description="Resume ID"),
    ) -> Dict[str, Any]:
        async def _operation(client: RxResumeClient) -> Any:
            result = await client.get_resume(resume_id=resume_id)
            return _reshape_resume(result)

        return await execute_rxresume_operation(
            operation_name=f"resume.get: {resume_id}",
            operation_func=_operation,
            ctx=ctx,
        )

    @mcp.tool(name="resume.doc.create", description="Create a new resume")
    async def create_resume(
        ctx: Context,
        name: str = Field(description="Resume name"),
        slug: str = Field(description="Resume slug"),
        tags: List[str] = Field(
            description="Tags to assign to resume", default_factory=list
        ),
        with_sample_data: bool = Field(
            description="If true, include sample data on creation", default=False
        ),
    ) -> Dict[str, Any]:
        async def _operation(client: RxResumeClient) -> Any:
            payload = _prepare_resume_create_payload(
                name=name,
                slug=slug,
                tags=tags,
                with_sample_data=with_sample_data,
            )
            payload = _apply_resume_create_defaults(payload)
            resume_id = await client.create_resume(**payload)
            resume = await client.get_resume(resume_id=resume_id)
            response = {
                "resume_id": resume_id,
                "resume": _reshape_resume(resume),
            }
            return _reshape_resume_create_response(response)

        return await execute_rxresume_operation(
            operation_name=f"resume.create: {name}",
            operation_func=_operation,
            ctx=ctx,
        )

    @mcp.tool(name="resume.doc.update", description="Update a resume by ID")
    async def update_resume(
        ctx: Context,
        resume_id: str = Field(description="Resume ID"),
        name: Optional[str] = Field(
            description="New resume title (not the person's name; use data.basics.name)",
            default=None,
        ),
        slug: Optional[str] = Field(description="New resume slug", default=None),
        tags: Optional[List[str]] = Field(
            description="Tags to set (pass [] to clear)", default=None
        ),
        data: Optional[Dict[str, Any]] = Field(
            # TODO:: Add a meaningful description
            description="", 
            default=None,
        ),
    ) -> Dict[str, Any]:
        if name is None and slug is None and tags is None and data is None:
            return format_response(
                "Update requires at least one field: name, slug, tags, or data",
                is_error=True,
            )

        async def _operation(client: RxResumeClient) -> Any:
            payload = _build_resume_update_payload(
                name=name,
                slug=slug,
                tags=tags,
                data=data,
            )
            payload = _apply_resume_update_defaults(payload)
            result = await client.update_resume_with_patch(
                resume_id=resume_id, **payload
            )
            return _reshape_resume(result)

        return await execute_rxresume_operation(
            operation_name=f"resume.update: {resume_id}",
            operation_func=_operation,
            ctx=ctx,
        )

    @mcp.tool(name="resume.doc.delete", description="Delete a resume by ID")
    async def delete_resume(
        ctx: Context,
        resume_id: str = Field(description="Resume ID"),
    ) -> Dict[str, Any]:
        async def _operation(client: RxResumeClient) -> Any:
            result = await client.delete_resume(resume_id=resume_id)
            return _reshape_resume(result)

        return await execute_rxresume_operation(
            operation_name=f"resume.delete: {resume_id}",
            operation_func=_operation,
            ctx=ctx,
        )
