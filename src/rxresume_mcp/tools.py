"""
MCP tool definitions for RxResume.
"""

from __future__ import annotations

import base64
import logging
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, cast

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

from rxresume_mcp import config
from rxresume_mcp import patch_ops
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


def _require_resume_object(payload: Any) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("Resume payload is not a JSON object")
    return payload


def _require_resume_data(resume: Dict[str, Any]) -> Dict[str, Any]:
    data = resume.get("data")
    if not isinstance(data, dict):
        raise ValueError("Resume data is not a JSON object")
    return data


def _ensure_section_type(section: str) -> None:
    if section not in patch_ops.SECTION_TYPES:
        raise ValueError(f"Unknown section type: {section}")


def _find_custom_section(data: Dict[str, Any], custom_section_id: str) -> Dict[str, Any]:
    custom_sections = data.get("customSections")
    if not isinstance(custom_sections, list):
        raise ValueError("Resume customSections is not an array")
    for section in custom_sections:
        if isinstance(section, dict) and section.get("id") == custom_section_id:
            return section
    raise ValueError(f"Custom section not found: {custom_section_id}")


def _custom_section_exists(data: Dict[str, Any], custom_section_id: str) -> bool:
    custom_sections = data.get("customSections")
    if not isinstance(custom_sections, list):
        return False
    for section in custom_sections:
        if isinstance(section, dict) and section.get("id") == custom_section_id:
            return True
    return False


def _find_item(items: Any, item_id: str) -> Optional[Dict[str, Any]]:
    if not isinstance(items, list):
        return None
    for item in items:
        if isinstance(item, dict) and item.get("id") == item_id:
            return item
    return None


def _ensure_object_payload(value: Any, label: str) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return dict(value)


def _ensure_item_id(item: Dict[str, Any], created_ids: List[str]) -> Dict[str, Any]:
    if "id" not in item or not item.get("id"):
        new_id = str(uuid.uuid4())
        item = dict(item)
        item["id"] = new_id
        created_ids.append(new_id)
    return item


def _build_summary(
    resume_id: str,
    ops: List[Dict[str, Any]],
    created_ids: List[str],
    *,
    include_result: bool,
    result: Any,
) -> Dict[str, Any]:
    summary = {
        "resume_id": resume_id,
        "applied_ops": ops,
        "changed_paths": [op.get("path") for op in ops if "path" in op],
        "created_ids": created_ids,
    }
    if include_result:
        summary["resume"] = result
    return summary


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

    @mcp.tool(
        name="get_resume_section",
        description=(
            "Fetch a focused resume subtree by section path "
            "(basics | summary | picture | metadata | sections.<type> | customSections.<id>)."
        ),
    )
    async def get_resume_section(
        ctx: Context,
        resume_id: str = Field(description="Resume ID"),
        section_path: str = Field(
            description="Section path: basics | summary | picture | metadata | sections.<type> | customSections.<id>"
        ),
    ) -> Dict[str, Any]:
        async def _operation(client: RxResumeClient) -> Any:
            resume = _require_resume_object(await client.get_resume(resume_id))
            data = _require_resume_data(resume)
            parts = section_path.split(".")
            if parts == ["basics"]:
                section_data = data.get("basics")
            elif parts == ["summary"]:
                section_data = data.get("summary")
            elif parts == ["picture"]:
                section_data = data.get("picture")
            elif parts == ["metadata"]:
                section_data = data.get("metadata")
            elif len(parts) == 2 and parts[0] == "sections":
                section_type = parts[1]
                _ensure_section_type(section_type)
                section_data = data.get("sections", {}).get(section_type)
            elif len(parts) == 2 and parts[0] == "customSections":
                section_data = _find_custom_section(data, parts[1])
            else:
                raise ValueError(
                    "Invalid section_path. Use basics, summary, sections.<type>, or customSections.<id>."
                )

            if section_data is None:
                raise ValueError(f"Section not found for path: {section_path}")

            return {
                "resume_id": resume_id,
                "section_path": section_path,
                "data": section_data,
            }

        return await execute_rxresume_operation(
            operation_name=f"get resume section: {resume_id}",
            operation_func=_operation,
            ctx=ctx,
        )

    @mcp.tool(
        name="edit_section_items",
        description=(
            "Add/update/remove items in a built-in section or custom section using JSON Patch."
        ),
    )
    async def edit_section_items(
        ctx: Context,
        resume_id: str = Field(description="Resume ID"),
        action: str = Field(description="Operation: add | update | remove"),
        section: Optional[str] = Field(
            default=None,
            description="Built-in section type (experience, education, projects, etc).",
        ),
        custom_section_id: Optional[str] = Field(
            default=None,
            description="Custom section id to target (use instead of section).",
        ),
        item_id: Optional[str] = Field(
            default=None,
            description="Item id for update/remove. Optional for add.",
        ),
        item: Optional[Dict[str, Any]] = Field(
            default=None,
            description="Item payload for add/update. For update (replace=false), keys update top-level fields.",
        ),
        replace: bool = Field(
            default=False,
            description="For update only: replace the entire item object.",
        ),
        include_result: bool = Field(
            default=False,
            description="If true, include the full resume in the response.",
        ),
    ) -> Dict[str, Any]:
        async def _operation(client: RxResumeClient) -> Any:
            resume = _require_resume_object(await client.get_resume(resume_id))
            data = _require_resume_data(resume)

            if (section and custom_section_id) or (not section and not custom_section_id):
                raise ValueError("Provide either section or custom_section_id, but not both.")

            created_ids: List[str] = []
            ops: List[Dict[str, Any]] = []
            target_items: Any

            if custom_section_id:
                custom_section = _find_custom_section(data, custom_section_id)
                target_items = custom_section.get("items", [])
            else:
                section_name = cast(str, section)
                _ensure_section_type(section_name)
                section_obj = data.get("sections", {}).get(section_name)
                if not isinstance(section_obj, dict):
                    raise ValueError(f"Section not found: {section_name}")
                target_items = section_obj.get("items", [])

            action_value = action.lower()

            if action_value == "add":
                item_payload = _ensure_object_payload(item, "item")
                if item_id:
                    if "id" in item_payload and item_payload["id"] != item_id:
                        raise ValueError("item.id does not match item_id")
                    item_payload.setdefault("id", item_id)
                item_payload = _ensure_item_id(item_payload, created_ids)
                if _find_item(target_items, item_payload["id"]):
                    raise ValueError(f"Item id already exists: {item_payload['id']}")
                if custom_section_id:
                    path = patch_ops.path_custom_section_items_append(custom_section_id)
                else:
                    path = patch_ops.path_section_items_append(cast(str, section))
                ops = [patch_ops.op_add(path, item_payload)]
            elif action_value == "update":
                if not item_id:
                    raise ValueError("item_id is required for update")
                if not _find_item(target_items, item_id):
                    raise ValueError(f"Item not found: {item_id}")
                item_payload = _ensure_object_payload(item, "item")
                if "id" in item_payload and item_payload["id"] != item_id:
                    raise ValueError("item.id does not match item_id")

                if replace:
                    if custom_section_id:
                        path = patch_ops.path_custom_section_item(custom_section_id, item_id)
                    else:
                        path = patch_ops.path_section_item(cast(str, section), item_id)
                    item_payload.setdefault("id", item_id)
                    ops = [patch_ops.op_replace(path, item_payload)]
                else:
                    for key, value in item_payload.items():
                        if key == "id":
                            raise ValueError("item.id cannot be updated; remove and add instead")
                        if custom_section_id:
                            path = patch_ops.path_custom_section_item_field(custom_section_id, item_id, key)
                        else:
                            path = patch_ops.path_section_item_field(cast(str, section), item_id, key)
                        ops.append(patch_ops.op_replace(path, value))
                    if not ops:
                        raise ValueError("No fields provided to update")
            elif action_value == "remove":
                if not item_id:
                    raise ValueError("item_id is required for remove")
                if not _find_item(target_items, item_id):
                    raise ValueError(f"Item not found: {item_id}")
                if custom_section_id:
                    path = patch_ops.path_custom_section_item(custom_section_id, item_id)
                else:
                    path = patch_ops.path_section_item(cast(str, section), item_id)
                ops = [patch_ops.op_remove(path)]
            else:
                raise ValueError("action must be add, update, or remove")

            validated_ops = patch_ops.validate_patch_ops(ops)
            result = await client.patch_resume(resume_id, patch_ops=validated_ops)
            return _build_summary(
                resume_id,
                validated_ops,
                created_ids,
                include_result=include_result,
                result=result,
            )

        return await execute_rxresume_operation(
            operation_name=f"edit section items: {resume_id}",
            operation_func=_operation,
            ctx=ctx,
        )

    @mcp.tool(
        name="edit_custom_sections",
        description="Add/update/remove custom sections using JSON Patch.",
    )
    async def edit_custom_sections(
        ctx: Context,
        resume_id: str = Field(description="Resume ID"),
        action: str = Field(description="Operation: add | update | remove"),
        custom_section_id: Optional[str] = Field(
            default=None,
            description="Custom section id for update/remove (or to set id on add).",
        ),
        section: Optional[Dict[str, Any]] = Field(
            default=None,
            description="Custom section payload for add/update.",
        ),
        replace: bool = Field(
            default=False,
            description="For update only: replace the entire custom section object.",
        ),
        include_result: bool = Field(
            default=False,
            description="If true, include the full resume in the response.",
        ),
    ) -> Dict[str, Any]:
        async def _operation(client: RxResumeClient) -> Any:
            resume = _require_resume_object(await client.get_resume(resume_id))
            data = _require_resume_data(resume)
            custom_sections = data.get("customSections")
            if not isinstance(custom_sections, list):
                raise ValueError("Resume customSections is not an array")

            created_ids: List[str] = []
            ops: List[Dict[str, Any]] = []
            action_value = action.lower()

            if action_value == "add":
                section_payload = _ensure_object_payload(section, "section")
                if not section_payload.get("type"):
                    raise ValueError("section.type is required for custom section add")
                if custom_section_id:
                    if "id" in section_payload and section_payload["id"] != custom_section_id:
                        raise ValueError("section.id does not match custom_section_id")
                    section_payload.setdefault("id", custom_section_id)
                section_payload = _ensure_item_id(section_payload, created_ids)
                if _custom_section_exists(data, section_payload["id"]):
                    raise ValueError(f"Custom section id already exists: {section_payload['id']}")
                ops = [patch_ops.op_add(patch_ops.path_custom_sections_append(), section_payload)]
            elif action_value == "update":
                if not custom_section_id:
                    raise ValueError("custom_section_id is required for update")
                existing_section = _find_custom_section(data, custom_section_id)
                section_payload = _ensure_object_payload(section, "section")
                if "id" in section_payload and section_payload["id"] != custom_section_id:
                    raise ValueError("section.id does not match custom_section_id")
                if replace:
                    section_payload.setdefault("id", custom_section_id)
                    section_payload.setdefault("type", existing_section.get("type"))
                    ops = [
                        patch_ops.op_replace(
                            patch_ops.path_custom_section(custom_section_id),
                            section_payload,
                        )
                    ]
                else:
                    for key, value in section_payload.items():
                        if key == "id":
                            raise ValueError("section.id cannot be updated; remove and add instead")
                        ops.append(
                            patch_ops.op_replace(
                                patch_ops.path_custom_section_field(custom_section_id, key),
                                value,
                            )
                        )
                    if not ops:
                        raise ValueError("No fields provided to update")
            elif action_value == "remove":
                if not custom_section_id:
                    raise ValueError("custom_section_id is required for remove")
                _find_custom_section(data, custom_section_id)
                ops = [patch_ops.op_remove(patch_ops.path_custom_section(custom_section_id))]
            else:
                raise ValueError("action must be add, update, or remove")

            validated_ops = patch_ops.validate_patch_ops(ops)
            result = await client.patch_resume(resume_id, patch_ops=validated_ops)
            return _build_summary(
                resume_id,
                validated_ops,
                created_ids,
                include_result=include_result,
                result=result,
            )

        return await execute_rxresume_operation(
            operation_name=f"edit custom sections: {resume_id}",
            operation_func=_operation,
            ctx=ctx,
        )

    @mcp.tool(
        name="patch_resume",
        description="Apply a raw JSON Patch document to a resume.",
    )
    async def patch_resume(
        ctx: Context,
        resume_id: str = Field(description="Resume ID"),
        patch: List[Dict[str, Any]] = Field(
            description="JSON Patch operations list (RFC 6902).",
        ),
        include_result: bool = Field(
            default=False,
            description="If true, include the full resume in the response.",
        ),
    ) -> Dict[str, Any]:
        async def _operation(client: RxResumeClient) -> Any:
            _require_resume_object(await client.get_resume(resume_id))
            validated_ops = patch_ops.validate_patch_ops(patch)
            result = await client.patch_resume(resume_id, patch_ops=validated_ops)
            return _build_summary(
                resume_id,
                validated_ops,
                [],
                include_result=include_result,
                result=result,
            )

        return await execute_rxresume_operation(
            operation_name=f"patch resume: {resume_id}",
            operation_func=_operation,
            ctx=ctx,
        )
