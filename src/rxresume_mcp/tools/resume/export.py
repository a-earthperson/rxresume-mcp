"""Register resume export tools."""

from __future__ import annotations

from typing import Any, Dict

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

from rxresume_mcp.client import RxResumeClient

from ..core import execute_rxresume_operation
from .common import _reshape_resume


def register_resume_export_tools(mcp: FastMCP) -> None:
    """Register tools that export resume outputs."""

    @mcp.tool(name="resume.export.pdf", description="Export resume as PDF")
    async def export_resume_pdf(
        ctx: Context,
        resume_id: str = Field(description="Resume ID"),
    ) -> Dict[str, Any]:
        async def _operation(client: RxResumeClient) -> Any:
            result = await client.export_resume_pdf(resume_id=resume_id)
            return _reshape_resume(result)

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
            result = await client.export_resume_screenshot(resume_id=resume_id)
            return _reshape_resume(result)

        return await execute_rxresume_operation(
            operation_name=f"resume.export_screenshot: {resume_id}",
            operation_func=_operation,
            ctx=ctx,
        )
