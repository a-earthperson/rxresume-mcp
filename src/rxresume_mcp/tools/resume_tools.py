"""Register resume CRUD and export tools."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

from rxresume_mcp.rxresume_client import RxResumeClient

from .core import execute_rxresume_operation, format_response


def register_resume_tools(mcp: FastMCP) -> None:
    """Register tools that operate on entire resumes."""

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
            return await client.list_resumes(tags=tags, sort=sort)

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
            return await client.get_resume(resume_id=resume_id)

        return await execute_rxresume_operation(
            operation_name=f"resume.get: {resume_id}",
            operation_func=_operation,
            ctx=ctx,
        )

    @mcp.tool(
        name="resume.doc.get.by_username",
        description="Fetch a resume by username and slug",
    )
    async def get_resume_by_username(
        ctx: Context,
        username: str = Field(description="Username"),
        slug: str = Field(description="Resume slug"),
    ) -> Dict[str, Any]:
        async def _operation(client: RxResumeClient) -> Any:
            return await client.get_resume_by_username(username=username, slug=slug)

        return await execute_rxresume_operation(
            operation_name=f"resume.get_by_username: {username}/{slug}",
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
        )
    ) -> Dict[str, Any]:
        async def _operation(client: RxResumeClient) -> Any:
            resume_id = await client.create_resume(
                name=name,
                slug=slug,
                tags=tags,
                with_sample_data=with_sample_data,
            )
            resume = await client.get_resume(resume_id=resume_id)
            return {"resume_id": resume_id, "resume": resume}

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
            description=(
                "Resume data patch merged into existing data. Must conform to the "
                "RxResume schema; top-level keys: picture, basics, summary, "
                "sections, customSections, metadata. Use data.basics.* for person "
                "info. See rxresume://schema/summary."
            ),
            default=None,
        ),
    ) -> Dict[str, Any]:
        if name is None and slug is None and tags is None and data is None:
            return format_response(
                "Update requires at least one field: name, slug, tags, or data",
                is_error=True,
            )

        async def _operation(client: RxResumeClient) -> Any:
            return await client.update_resume_with_patch(
                resume_id=resume_id,
                name=name,
                slug=slug,
                tags=tags,
                data_patch=data,
            )

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
            return await client.delete_resume(resume_id=resume_id)

        return await execute_rxresume_operation(
            operation_name=f"resume.delete: {resume_id}",
            operation_func=_operation,
            ctx=ctx,
        )

    @mcp.tool(name="resume.export.pdf", description="Export resume as PDF")
    async def export_resume_pdf(
        ctx: Context,
        resume_id: str = Field(description="Resume ID"),
    ) -> Dict[str, Any]:
        async def _operation(client: RxResumeClient) -> Any:
            return await client.export_resume_pdf(resume_id=resume_id)

        return await execute_rxresume_operation(
            operation_name=f"resume.export_pdf: {resume_id}",
            operation_func=_operation,
            ctx=ctx,
        )

    @mcp.tool(
        name="resume.export.screenshot", description="Export resume screenshot"
    )
    async def export_resume_screenshot(
        ctx: Context,
        resume_id: str = Field(description="Resume ID"),
    ) -> Dict[str, Any]:
        async def _operation(client: RxResumeClient) -> Any:
            return await client.export_resume_screenshot(resume_id=resume_id)

        return await execute_rxresume_operation(
            operation_name=f"resume.export_screenshot: {resume_id}",
            operation_func=_operation,
            ctx=ctx,
        )
