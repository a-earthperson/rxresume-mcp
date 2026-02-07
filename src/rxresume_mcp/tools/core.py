"""Core primitives for RxResume MCP tools."""

from __future__ import annotations

import base64
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, Callable, Dict, cast

from mcp.server.fastmcp import Context, FastMCP

from rxresume_mcp import config
from rxresume_mcp.rxresume_client import RxResumeClient

logger = logging.getLogger(__name__)


def _encode_binary(content_type: str, data: bytes) -> Dict[str, Any]:
    """Encode binary payloads for JSON-only responses."""
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
    """Create and tear down shared app resources for tool handlers."""
    # FastMCP passes the server for lifecycle hooks; we don't need it here.
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
