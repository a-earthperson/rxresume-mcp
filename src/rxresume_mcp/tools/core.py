"""Core primitives for RxResume MCP tools."""

from __future__ import annotations

import base64
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, cast

from pydantic import ValidationError

from mcp.server.fastmcp import Context, FastMCP

from rxresume_mcp import config
from rxresume_mcp.client import RxResumeAPIError, RxResumeClient

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ToolError(Exception):
    """
    A structured error suitable for returning to MCP clients.

    This is intentionally small and stable so constrained agents can reliably
    pattern-match and recover.
    """

    code: str
    message: str
    http_status: int = 400
    details: Optional[List[Dict[str, Any]]] = None
    retryable: bool = False

    def to_dict(self) -> Dict[str, Any]:
        issues = list(self.details or [])
        return {
            "httpStatus": self.http_status,
            "code": self.code,
            "message": self.message,
            # Provide both keys to avoid client churn; prefer details.
            "details": issues,
            "issues": issues,
            "retryable": self.retryable,
        }


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
        if isinstance(result, ToolError):
            return {"status": "error", "error": result.to_dict()}
        if isinstance(result, dict):
            # Allow passing a pre-structured error dict.
            return {"status": "error", "error": result}
        return {
            "status": "error",
            "error": ToolError(
                code="INTERNAL_ERROR",
                message=str(result) if result is not None else "Unknown error",
                http_status=500,
                retryable=False,
            ).to_dict(),
        }

    if result is None:
        # Avoid "None" stringification; keep JSON null.
        return {"status": "success", "response": None}

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
    operation_name: str,
    operation_func: Callable,
    ctx: Context,
    *,
    resume_id: str | None = None,
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
            payload = format_response(
                ToolError(
                    code="CONTEXT_UNAVAILABLE",
                    message=f"Request context is not available for {operation_name}",
                    http_status=500,
                    retryable=True,
                ),
                is_error=True,
            )
            if resume_id:
                payload["resume_id"] = resume_id
            return payload

        app_ctx = cast(AppContext, ctx.request_context.lifespan_context)
        client = app_ctx.rxresume_client

        logger.info("Executing operation: %s", operation_name)
        result = await operation_func(client)
        payload = format_response(result)
        if resume_id:
            payload["resume_id"] = resume_id
        return payload
    except ToolError as exc:
        logger.info("Tool error during %s: %s", operation_name, exc.message)
        payload = format_response(exc, is_error=True)
        if resume_id:
            payload["resume_id"] = resume_id
        return payload
    except RxResumeAPIError as exc:
        http_status = getattr(exc, "status_code", 500)
        code = "UPSTREAM_ERROR"
        retryable = http_status >= 500
        if http_status == 404:
            code = "NOT_FOUND"
        elif http_status in (401, 403):
            code = "UNAUTHORIZED"
        elif http_status == 400:
            code = "BAD_REQUEST"
        message = "Reactive Resume API request failed"
        details: List[Dict[str, Any]] = []
        payload_value = getattr(exc, "payload", None)
        if payload_value is not None:
            details.append({"field": "upstream", "received": payload_value})
        tool_exc = ToolError(
            code=code,
            message=message,
            http_status=int(http_status) if isinstance(http_status, int) else 500,
            details=details or None,
            retryable=retryable,
        )
        logger.info("Upstream error during %s: %s", operation_name, tool_exc.to_dict())
        payload = format_response(tool_exc, is_error=True)
        if resume_id:
            payload["resume_id"] = resume_id
        return payload
    except ValidationError as exc:
        details = []
        for err in exc.errors():
            loc = ".".join(str(p) for p in (err.get("loc") or []))
            details.append(
                {
                    "field": loc or "<root>",
                    "message": err.get("msg") or "Invalid value",
                    "type": err.get("type"),
                }
            )
        tool_exc = ToolError(
            code="VALIDATION_ERROR",
            message="Invalid tool arguments",
            http_status=400,
            details=details or None,
            retryable=False,
        )
        payload = format_response(tool_exc, is_error=True)
        if resume_id:
            payload["resume_id"] = resume_id
        return payload
    except ValueError as exc:
        tool_exc = ToolError(
            code="VALIDATION_ERROR",
            message=str(exc),
            http_status=400,
            details=None,
            retryable=False,
        )
        payload = format_response(tool_exc, is_error=True)
        if resume_id:
            payload["resume_id"] = resume_id
        return payload
    except Exception as exc:
        logger.exception("Unhandled error during %s: %s", operation_name, str(exc))
        tool_exc = ToolError(
            code="INTERNAL_ERROR",
            message="Unexpected server error",
            http_status=500,
            details=[{"field": "exception", "received": str(exc)}],
            retryable=True,
        )
        payload = format_response(tool_exc, is_error=True)
        if resume_id:
            payload["resume_id"] = resume_id
        return payload
