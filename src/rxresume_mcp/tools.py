"""
MCP tool definitions for RxResume.
"""

from __future__ import annotations

import base64
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, cast

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

from rxresume_mcp import config
from rxresume_mcp.rxresume_client import RxResumeClient

logger = logging.getLogger(__name__)


def _encode_binary(content_type: str, data: bytes) -> Dict[str, Any]:
    encoded = base64.b64encode(data).decode("ascii")
    return {
        "content_type": content_type,
        "content_base64": encoded,
        "size_bytes": len(data),
    }


def format_response(result: Any, is_error: bool = False) -> Dict[str, Any]:
    """
    Formats response in standard format.

    Args:
        result: Operation result
        is_error: Error flag

    Returns:
        Dict[str, Any]: Standardized response
    """
    if is_error:
        if isinstance(result, str):
            return {"status": "error", "error": result}
        return {"status": "error", "error": str(result)}

    if isinstance(result, tuple) and len(result) == 2:
        content_type, payload = result
        if isinstance(content_type, str) and isinstance(payload, (bytes, bytearray)):
            return {
                "status": "success",
                "response": _encode_binary(content_type, bytes(payload)),
            }

    if isinstance(result, (bytes, bytearray)):
        return {
            "status": "success",
            "response": _encode_binary("application/octet-stream", bytes(result)),
        }

    if isinstance(result, dict):
        return {"status": "success", "response": result}

    if isinstance(result, list):
        return {"status": "success", "response": result}

    if hasattr(result, "model_dump") and callable(getattr(result, "model_dump")):
        return {"status": "success", "response": result.model_dump()}
    if hasattr(result, "dict") and callable(getattr(result, "dict")):
        return {"status": "success", "response": result.dict()}
    if hasattr(result, "__dict__"):
        return {"status": "success", "response": result.__dict__}
    if hasattr(result, "to_dict") and callable(getattr(result, "to_dict")):
        return {"status": "success", "response": result.to_dict()}

    return {"status": "success", "response": str(result)}


@dataclass
class AppContext:
    """Application context with typed resources."""

    rxresume_client: RxResumeClient


@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
    """
    Manages application lifecycle with typed context.
    Initializes RxResume API client at startup and closes it at shutdown.
    """
    rxresume_client = RxResumeClient(
        base_url=config.RXRESUME.base_url,
        api_key=config.RXRESUME.api_key,
        timeout=config.RXRESUME.timeout,
        user_agent=config.RXRESUME.user_agent,
    )

    try:
        yield AppContext(rxresume_client=rxresume_client)
    finally:
        await rxresume_client.close()
        logger.info("RxResume MCP Server stopped")


async def execute_rxresume_operation(
    operation_name: str, operation_func: Callable, ctx: Context
) -> Dict[str, Any]:
    """
    Universal wrapper function for executing operations with RxResume API.

    Automatically handles:
    - Getting client from context
    - Type casting
    - Exception handling
    - Response formatting
    """
    try:
        if (
            not ctx
            or not ctx.request_context
            or not ctx.request_context.lifespan_context
        ):
            return format_response(
                f"Error: Request context is not available for {operation_name}",
                is_error=True,
            )

        app_ctx = cast(AppContext, ctx.request_context.lifespan_context)
        client = app_ctx.rxresume_client

        logger.info("Executing operation: %s", operation_name)
        result = await operation_func(client)

        return format_response(result)
    except Exception as e:
        logger.exception("Error during %s: %s", operation_name, str(e))
        return format_response(str(e), is_error=True)


def register_tools(mcp: FastMCP) -> None:
    """Register RxResume MCP tool endpoints."""

    @mcp.tool(
        name="list_resumes",
        description="List resumes, optionally filtering by tags and sort order",
    )
    async def list_resumes(
        ctx: Context,
        tags: List[str] = Field(
            description="Optional list of tags to filter by",
            default_factory=list,
        ),
        sort: Optional[str] = Field(
            description="Sort order, e.g. 'updatedAt' or '-updatedAt'",
            default=None,
        ),
    ) -> Dict[str, Any]:
        async def _operation(client: RxResumeClient) -> Any:
            return await client.list_resumes(tags=tags, sort=sort)

        return await execute_rxresume_operation(
            operation_name="list resumes",
            operation_func=_operation,
            ctx=ctx,
        )

    @mcp.tool(name="get_resume", description="Fetch a resume by ID")
    async def get_resume(
        ctx: Context,
        resume_id: str = Field(description="Resume ID"),
    ) -> Dict[str, Any]:
        async def _operation(client: RxResumeClient) -> Any:
            return await client.get_resume(resume_id=resume_id)

        return await execute_rxresume_operation(
            operation_name=f"get resume: {resume_id}",
            operation_func=_operation,
            ctx=ctx,
        )

    @mcp.tool(
        name="get_resume_by_username",
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
            operation_name=f"get resume by username: {username}/{slug}",
            operation_func=_operation,
            ctx=ctx,
        )

    @mcp.tool(name="create_resume", description="Create a new resume")
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
            return await client.create_resume(
                name=name,
                slug=slug,
                tags=tags,
                with_sample_data=with_sample_data,
            )

        return await execute_rxresume_operation(
            operation_name=f"create resume: {name}",
            operation_func=_operation,
            ctx=ctx,
        )

    @mcp.tool(name="update_resume", description="Update a resume by ID")
    async def update_resume(
        ctx: Context,
        resume_id: str = Field(description="Resume ID"),
        name: Optional[str] = Field(description="New resume name", default=None),
        slug: Optional[str] = Field(description="New resume slug", default=None),
        tags: Optional[List[str]] = Field(
            description="Tags to set (pass [] to clear)", default=None
        ),
        data: Optional[Dict[str, Any]] = Field(
            description="Resume data payload", default=None
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
            operation_name=f"update resume: {resume_id}",
            operation_func=_operation,
            ctx=ctx,
        )

    @mcp.tool(name="delete_resume", description="Delete a resume by ID")
    async def delete_resume(
        ctx: Context,
        resume_id: str = Field(description="Resume ID"),
    ) -> Dict[str, Any]:
        async def _operation(client: RxResumeClient) -> Any:
            return await client.delete_resume(resume_id=resume_id)

        return await execute_rxresume_operation(
            operation_name=f"delete resume: {resume_id}",
            operation_func=_operation,
            ctx=ctx,
        )

    @mcp.tool(name="export_resume_pdf", description="Export resume as PDF")
    async def export_resume_pdf(
        ctx: Context,
        resume_id: str = Field(description="Resume ID"),
    ) -> Dict[str, Any]:
        async def _operation(client: RxResumeClient) -> Any:
            return await client.export_resume_pdf(resume_id=resume_id)

        return await execute_rxresume_operation(
            operation_name=f"export resume pdf: {resume_id}",
            operation_func=_operation,
            ctx=ctx,
        )

    @mcp.tool(name="export_resume_screenshot", description="Export resume screenshot")
    async def export_resume_screenshot(
        ctx: Context,
        resume_id: str = Field(description="Resume ID"),
    ) -> Dict[str, Any]:
        async def _operation(client: RxResumeClient) -> Any:
            return await client.export_resume_screenshot(resume_id=resume_id)

        return await execute_rxresume_operation(
            operation_name=f"export resume screenshot: {resume_id}",
            operation_func=_operation,
            ctx=ctx,
        )
