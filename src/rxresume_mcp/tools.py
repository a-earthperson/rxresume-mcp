"""
MCP tool definitions for RxResume.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import re
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, cast

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

from rxresume_mcp import config
from rxresume_mcp import patch_ops, resources as rx_resources
from rxresume_mcp.rxresume_client import RxResumeClient

logger = logging.getLogger(__name__)

_URL_SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")


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
        allowed = ", ".join(patch_ops.SECTION_TYPES)
        raise ValueError(f"Unknown section type: {section}. Expected one of: {allowed}")


def _ensure_custom_section_type(section_type: Any) -> str:
    if not isinstance(section_type, str) or not section_type:
        raise ValueError("section.type must be a non-empty string")
    if section_type not in patch_ops.SECTION_TYPES:
        allowed = ", ".join(patch_ops.SECTION_TYPES)
        raise ValueError(f"section.type must be one of: {allowed}")
    return section_type


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


def _parse_json_pointer(path: str) -> List[str]:
    if not path.startswith("/"):
        return []
    return [
        segment.replace("~1", "/").replace("~0", "~")
        for segment in path[1:].split("/")
    ]


def _auto_id_patch_ops(
    ops: List[Dict[str, Any]],
) -> tuple[List[Dict[str, Any]], List[str]]:
    created_ids: List[str] = []
    normalized_ops: List[Dict[str, Any]] = []

    for op in ops:
        if op.get("op") == "add":
            path = op.get("path")
            value = op.get("value")
            if isinstance(path, str) and isinstance(value, dict):
                segments = _parse_json_pointer(path)
                is_section_item_append = (
                    len(segments) == 5
                    and segments[0] == "data"
                    and segments[1] == "sections"
                    and segments[3] == "items"
                    and segments[4] == "-"
                )
                is_custom_section_append = (
                    len(segments) == 3
                    and segments[0] == "data"
                    and segments[1] == "customSections"
                    and segments[2] == "-"
                )
                is_custom_section_item_append = (
                    len(segments) == 6
                    and segments[0] == "data"
                    and segments[1] == "customSections"
                    and segments[2] == "id"
                    and segments[4] == "items"
                    and segments[5] == "-"
                )
                is_custom_field_append = (
                    len(segments) == 4
                    and segments[0] == "data"
                    and segments[1] == "basics"
                    and segments[2] == "customFields"
                    and segments[3] == "-"
                )

                if (
                    is_section_item_append
                    or is_custom_section_append
                    or is_custom_section_item_append
                    or is_custom_field_append
                ):
                    if not value.get("id"):
                        new_id = str(uuid.uuid4())
                        value = dict(value)
                        value["id"] = new_id
                        created_ids.append(new_id)
                        op = dict(op)
                        op["value"] = value
        normalized_ops.append(op)

    return normalized_ops, created_ids


def _summarize_custom_sections(custom_sections: List[Any]) -> List[Dict[str, Any]]:
    summaries: List[Dict[str, Any]] = []
    for section in custom_sections:
        if not isinstance(section, dict):
            continue
        items = section.get("items")
        summaries.append(
            {
                "id": section.get("id"),
                "title": section.get("title"),
                "type": section.get("type"),
                "hidden": section.get("hidden"),
                "columns": section.get("columns"),
                "item_count": len(items) if isinstance(items, list) else 0,
            }
        )
    return summaries


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


def _ensure_item_ids(items: Any, created_ids: List[str]) -> Any:
    if not isinstance(items, list):
        return items
    normalized: List[Any] = []
    for item in items:
        if isinstance(item, dict):
            normalized.append(_ensure_item_id(item, created_ids))
        else:
            normalized.append(item)
    return normalized


def _normalize_url(value: str) -> str:
    if not value:
        return value
    if _URL_SCHEME_RE.match(value):
        return value
    if value.startswith("//"):
        return f"https:{value}"
    return f"https://{value}"


def _normalize_url_fields(payload: Any) -> Any:
    if isinstance(payload, dict):
        normalized: Dict[str, Any] = {}
        for key, value in payload.items():
            if key == "url" and isinstance(value, str):
                normalized[key] = _normalize_url(value)
            else:
                normalized[key] = _normalize_url_fields(value)
        return normalized
    if isinstance(payload, list):
        return [_normalize_url_fields(item) for item in payload]
    return payload


def _build_summary(
    resume_id: str,
    ops: List[Dict[str, Any]],
    created_ids: List[str],
    *,
    include_result: bool,
    result: Any,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    summary = {
        "resume_id": resume_id,
        "applied_ops": ops,
        "changed_paths": [op.get("path") for op in ops if "path" in op],
        "created_ids": created_ids,
    }
    if include_result:
        summary["resume"] = result
    if extra:
        summary.update(extra)
    return summary


def _extract_section_data(resume: Dict[str, Any], section_path: str) -> Dict[str, Any]:
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
    elif parts == ["customSections"]:
        custom_sections = data.get("customSections")
        if not isinstance(custom_sections, list):
            raise ValueError("Resume customSections is not an array")
        section_data = _summarize_custom_sections(custom_sections)
    elif len(parts) == 2 and parts[0] == "customSections":
        section_data = _find_custom_section(data, parts[1])
    else:
        raise ValueError(
            "Invalid section_path. Use basics, summary, picture, metadata, "
            "sections.<type>, customSections, or customSections.<id>."
        )

    if section_data is None:
        raise ValueError(f"Section not found for path: {section_path}")

    return {
        "section_path": section_path,
        "data": section_data,
    }


def _doc_registry() -> Dict[str, Dict[str, Any]]:
    return {
        "tool-semantics": {
            "title": "RxResume MCP Tool Semantics",
            "mime_type": "text/markdown",
            "content": rx_resources.TOOL_SEMANTICS_DOC,
        },
        "schema-summary": {
            "title": "RxResume Resume Schema Summary",
            "mime_type": "text/markdown",
            "content": rx_resources.SCHEMA_SUMMARY_DOC,
        },
        "patch-ops": {
            "title": "RxResume JSON Patch Paths",
            "mime_type": "text/markdown",
            "content": rx_resources.PATCH_OPS_DOC,
        },
        "design-notes": {
            "title": "RxResume Design Notes",
            "mime_type": "text/markdown",
            "content": rx_resources.DESIGN_NOTES_DOC,
        },
        "resume-schema": {
            "title": "RxResume Resume Schema (JSON Schema)",
            "mime_type": "application/schema+json",
            "content": rx_resources._load_resume_schema(),
        },
    }


def _hash_content(content: Any) -> tuple[str, int]:
    if isinstance(content, str):
        payload = content.encode("utf-8")
        return hashlib.sha256(payload).hexdigest(), len(content)
    payload = json.dumps(content, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest(), len(payload.decode("utf-8"))


def _parse_schema_pointer(path: str | None) -> List[str]:
    if not path or path in {"#", "/"}:
        return []
    if path.startswith("#/"):
        path = path[1:]
    if path.startswith("/"):
        return _parse_json_pointer(path)
    return ["properties", *path.split(".")]


def _resolve_schema_path(
    schema: Dict[str, Any],
    path: str | None,
    resolve_refs: bool,
) -> Any:
    if not path or path in {"#", "/"}:
        return schema
    if path.startswith("#/") or path.startswith("/"):
        node: Any = schema
        for segment in _parse_schema_pointer(path):
            if not isinstance(node, dict):
                raise ValueError(f"Schema path not found: {path}")
            node = node.get(segment)
            if node is None:
                raise ValueError(f"Schema path not found: {path}")
        return node
    return _resolve_schema_dot_path(schema, path, resolve_refs)


def _resolve_schema_dot_path(
    schema: Dict[str, Any],
    path: str,
    resolve_refs: bool,
) -> Any:
    node: Any = schema
    seen_refs: set[str] = set()
    for segment in path.split("."):
        node = _resolve_schema_dot_segment(schema, node, segment, resolve_refs, seen_refs)
        if node is None:
            raise ValueError(f"Schema path not found: {path}")
    return node


def _resolve_schema_dot_segment(
    schema: Dict[str, Any],
    node: Any,
    segment: str,
    resolve_refs: bool,
    seen_refs: set[str],
) -> Any:
    if isinstance(node, dict) and "$ref" in node:
        resolved_node, resolved = _resolve_schema_ref(schema, node["$ref"], resolve_refs, seen_refs)
        if resolved_node and resolved:
            node = resolved_node

    if not isinstance(node, dict):
        return None

    if segment in node:
        return node[segment]

    properties = node.get("properties")
    if isinstance(properties, dict) and segment in properties:
        return properties[segment]

    items = node.get("items")
    if segment == "items" and items is not None:
        return items

    if isinstance(items, dict):
        if segment in items:
            return items[segment]
        item_properties = items.get("properties")
        if isinstance(item_properties, dict) and segment in item_properties:
            return item_properties[segment]
        if "$ref" in items:
            resolved_node, resolved = _resolve_schema_ref(schema, items["$ref"], resolve_refs, seen_refs)
            if resolved_node and resolved:
                return _resolve_schema_dot_segment(
                    schema, resolved_node, segment, resolve_refs, seen_refs
                )

    return None


def _resolve_schema_ref(
    schema: Dict[str, Any],
    ref: str,
    resolve_refs: bool,
    seen: set[str],
) -> tuple[Dict[str, Any] | None, bool]:
    if not resolve_refs or not ref.startswith("#/"):
        return None, False
    if ref in seen:
        return None, False
    seen.add(ref)
    node: Any = schema
    for segment in _parse_schema_pointer(ref):
        if not isinstance(node, dict):
            return None, False
        node = node.get(segment)
        if node is None:
            return None, False
    if isinstance(node, dict) and "$ref" in node:
        return _resolve_schema_ref(schema, node["$ref"], resolve_refs, seen)
    if isinstance(node, dict):
        return node, True
    return None, False


def _summarize_schema_node(
    node: Any,
    schema: Dict[str, Any],
    *,
    depth: int,
    include_descriptions: bool,
    include_constraints: bool,
    include_required: bool,
    include_examples: bool,
    max_properties: int,
    resolve_refs: bool,
    seen_refs: set[str],
) -> Dict[str, Any]:
    if not isinstance(node, dict):
        return {"type": type(node).__name__}

    resolved = False
    if "$ref" in node:
        resolved_node, resolved = _resolve_schema_ref(schema, node["$ref"], resolve_refs, seen_refs)
        if resolved_node:
            node = resolved_node

    summary: Dict[str, Any] = {}
    if "$ref" in node and not resolved:
        summary["$ref"] = node["$ref"]

    for key in ("title", "type", "format", "const", "default"):
        if key in node:
            summary[key] = node[key]
    if include_descriptions and "description" in node:
        summary["description"] = node["description"]
    if "enum" in node:
        summary["enum"] = node["enum"]
    if include_required and "required" in node:
        summary["required"] = node["required"]

    if include_constraints:
        for key in (
            "minimum",
            "maximum",
            "exclusiveMinimum",
            "exclusiveMaximum",
            "minLength",
            "maxLength",
            "pattern",
            "minItems",
            "maxItems",
            "uniqueItems",
        ):
            if key in node:
                summary[key] = node[key]

    if include_examples:
        for key in ("examples", "example"):
            if key in node:
                summary[key] = node[key]

    if "additionalProperties" in node:
        summary["additionalProperties"] = node["additionalProperties"]

    if depth > 0 and "properties" in node and isinstance(node["properties"], dict):
        properties: Dict[str, Any] = {}
        for idx, (name, prop) in enumerate(node["properties"].items()):
            if idx >= max_properties:
                break
            properties[name] = _summarize_schema_node(
                prop,
                schema,
                depth=depth - 1,
                include_descriptions=include_descriptions,
                include_constraints=include_constraints,
                include_required=include_required,
                include_examples=include_examples,
                max_properties=max_properties,
                resolve_refs=resolve_refs,
                seen_refs=seen_refs,
            )
        summary["properties"] = properties
        if len(node["properties"]) > max_properties:
            summary["properties_truncated"] = True

    if depth > 0 and "items" in node:
        summary["items"] = _summarize_schema_node(
            node["items"],
            schema,
            depth=depth - 1,
            include_descriptions=include_descriptions,
            include_constraints=include_constraints,
            include_required=include_required,
            include_examples=include_examples,
            max_properties=max_properties,
            resolve_refs=resolve_refs,
            seen_refs=seen_refs,
        )

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
            description="Sort order: 'lastUpdatedAt' (desc), 'createdAt', or 'name'",
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
        include_resume: bool = Field(
            description="If true, fetch and return the created resume object.",
            default=False,
        ),
    ) -> Dict[str, Any]:
        async def _operation(client: RxResumeClient) -> Any:
            resume_id = await client.create_resume(
                name=name,
                slug=slug,
                tags=tags,
                with_sample_data=with_sample_data,
            )
            if not include_resume:
                return resume_id
            resume = await client.get_resume(resume_id=resume_id)
            return {"resume_id": resume_id, "resume": resume}

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
            "(basics | summary | picture | metadata | sections.<type> | "
            "customSections | customSections.<id>). "
            "customSections returns summary entries."
        ),
    )
    async def get_resume_section(
        ctx: Context,
        resume_id: str = Field(description="Resume ID"),
        section_path: str = Field(
            description=(
                "Section path: basics | summary | picture | metadata | sections.<type> | "
                "customSections | customSections.<id>. "
                "customSections returns id/title/type/hidden/columns/item_count."
            )
        ),
    ) -> Dict[str, Any]:
        async def _operation(client: RxResumeClient) -> Any:
            resume = _require_resume_object(await client.get_resume(resume_id))
            return {
                "resume_id": resume_id,
                **_extract_section_data(resume, section_path),
            }

        return await execute_rxresume_operation(
            operation_name=f"get resume section: {resume_id}",
            operation_func=_operation,
            ctx=ctx,
        )

    @mcp.tool(
        name="edit_section_items",
        description=(
            "Add/update/remove items in a built-in section or custom section using JSON Patch. "
            "Generates missing item ids on add and can normalize url fields."
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
        result_section_path: Optional[str] = Field(
            default=None,
            description=(
                "If set, include only this subtree from the patch result "
                "(basics | summary | picture | metadata | sections.<type> | "
                "customSections | customSections.<id>)."
            ),
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
                item_payload = cast(Dict[str, Any], _normalize_url_fields(item_payload))
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
                item_payload = cast(Dict[str, Any], _normalize_url_fields(item_payload))
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
            extra: Dict[str, Any] = {}
            if result_section_path:
                extra["result_section"] = _extract_section_data(result, result_section_path)
            if action_value == "add" and created_ids:
                extra["created_item_ids"] = created_ids
            return _build_summary(
                resume_id,
                validated_ops,
                created_ids,
                include_result=include_result,
                result=result,
                extra=extra if extra else None,
            )

        return await execute_rxresume_operation(
            operation_name=f"edit section items: {resume_id}",
            operation_func=_operation,
            ctx=ctx,
        )

    @mcp.tool(
        name="edit_custom_sections",
        description=(
            "Add/update/remove custom sections using JSON Patch (type is fixed). "
            "You can include items on add and omit ids to auto-generate."
        ),
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
        result_section_path: Optional[str] = Field(
            default=None,
            description=(
                "If set, include only this subtree from the patch result "
                "(basics | summary | picture | metadata | sections.<type> | "
                "customSections | customSections.<id>)."
            ),
        ),
    ) -> Dict[str, Any]:
        async def _operation(client: RxResumeClient) -> Any:
            resume = _require_resume_object(await client.get_resume(resume_id))
            data = _require_resume_data(resume)
            custom_sections = data.get("customSections")
            if not isinstance(custom_sections, list):
                raise ValueError("Resume customSections is not an array")

            created_ids: List[str] = []
            created_item_ids: List[str] = []
            created_custom_section_id: Optional[str] = None
            ops: List[Dict[str, Any]] = []
            action_value = action.lower()

            if action_value == "add":
                section_payload = _ensure_object_payload(section, "section")
                section_payload = cast(Dict[str, Any], _normalize_url_fields(section_payload))
                if not section_payload.get("type"):
                    raise ValueError("section.type is required for custom section add")
                section_payload["type"] = _ensure_custom_section_type(section_payload["type"])
                if custom_section_id:
                    if "id" in section_payload and section_payload["id"] != custom_section_id:
                        raise ValueError("section.id does not match custom_section_id")
                    section_payload.setdefault("id", custom_section_id)
                section_payload = _ensure_item_id(section_payload, created_ids)
                if created_ids:
                    created_custom_section_id = section_payload.get("id")
                if "items" in section_payload:
                    section_payload["items"] = _ensure_item_ids(
                        section_payload.get("items"), created_item_ids
                    )
                if created_item_ids:
                    created_ids.extend(created_item_ids)
                if _custom_section_exists(data, section_payload["id"]):
                    raise ValueError(f"Custom section id already exists: {section_payload['id']}")
                ops = [patch_ops.op_add(patch_ops.path_custom_sections_append(), section_payload)]
            elif action_value == "update":
                if not custom_section_id:
                    raise ValueError("custom_section_id is required for update")
                existing_section = _find_custom_section(data, custom_section_id)
                section_payload = _ensure_object_payload(section, "section")
                section_payload = cast(Dict[str, Any], _normalize_url_fields(section_payload))
                if "type" in section_payload:
                    section_payload["type"] = _ensure_custom_section_type(section_payload["type"])
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
            extra: Dict[str, Any] = {}
            if result_section_path:
                extra["result_section"] = _extract_section_data(result, result_section_path)
            if created_custom_section_id:
                extra["created_custom_section_id"] = created_custom_section_id
            if created_item_ids:
                extra["created_item_ids"] = created_item_ids
            return _build_summary(
                resume_id,
                validated_ops,
                created_ids,
                include_result=include_result,
                result=result,
                extra=extra if extra else None,
            )

        return await execute_rxresume_operation(
            operation_name=f"edit custom sections: {resume_id}",
            operation_func=_operation,
            ctx=ctx,
        )

    @mcp.tool(
        name="patch_resume",
        description="Apply RxResume JSON Patch (RFC 6902 + id-path extensions).",
    )
    async def patch_resume(
        ctx: Context,
        resume_id: str = Field(description="Resume ID"),
        patch: List[patch_ops.JsonPatchOp] = Field(
            description="JSON Patch operations list (RFC 6902 + RxResume id paths).",
        ),
        include_result: bool = Field(
            default=False,
            description="If true, include the full resume in the response.",
        ),
        result_section_path: Optional[str] = Field(
            default=None,
            description=(
                "If set, include only this subtree from the patch result "
                "(basics | summary | picture | metadata | sections.<type> | "
                "customSections | customSections.<id>)."
            ),
        ),
    ) -> Dict[str, Any]:
        async def _operation(client: RxResumeClient) -> Any:
            _require_resume_object(await client.get_resume(resume_id))
            validated_ops = patch_ops.validate_patch_ops(patch)
            normalized_ops, created_ids = _auto_id_patch_ops(validated_ops)
            result = await client.patch_resume(resume_id, patch_ops=normalized_ops)
            extra: Dict[str, Any] = {}
            if result_section_path:
                extra["result_section"] = _extract_section_data(result, result_section_path)
            return _build_summary(
                resume_id,
                normalized_ops,
                created_ids,
                include_result=include_result,
                result=result,
                extra=extra if extra else None,
            )

        return await execute_rxresume_operation(
            operation_name=f"patch resume: {resume_id}",
            operation_func=_operation,
            ctx=ctx,
        )

    @mcp.tool(
        name="get_rxresume_docs",
        description="Fetch RxResume MCP documentation for tool-only clients.",
    )
    async def get_rxresume_docs(
        ctx: Context,
        topics: Optional[List[str]] = Field(
            default=None,
            description=(
                "Doc ids to fetch. Available: tool-semantics, schema-summary, "
                "patch-ops, design-notes, resume-schema."
            ),
        ),
        include_content: bool = Field(
            default=False,
            description="If true, include doc content instead of index-only.",
        ),
        include_schema: bool = Field(
            default=False,
            description="If true, include full JSON schema when resume-schema is selected.",
        ),
        max_chars: Optional[int] = Field(
            default=None,
            description="If set, truncate text content to this many characters.",
        ),
    ) -> Dict[str, Any]:
        async def _operation(client: RxResumeClient) -> Any:
            registry = _doc_registry()
            requested = topics or list(registry.keys())
            docs: List[Dict[str, Any]] = []

            for doc_id in requested:
                entry = registry.get(doc_id)
                if not entry:
                    raise ValueError(f"Unknown doc id: {doc_id}")
                content = entry["content"]
                sha256, size_chars = _hash_content(content)
                doc_info: Dict[str, Any] = {
                    "id": doc_id,
                    "title": entry["title"],
                    "mime_type": entry["mime_type"],
                    "size_chars": size_chars,
                    "sha256": sha256,
                }

                if include_content:
                    if doc_id == "resume-schema" and not include_schema:
                        doc_info["content"] = None
                        doc_info["note"] = "Set include_schema=true to return full JSON schema."
                    elif isinstance(content, str):
                        if max_chars is not None and len(content) > max_chars:
                            doc_info["content"] = content[:max_chars]
                            doc_info["truncated"] = True
                        else:
                            doc_info["content"] = content
                    else:
                        doc_info["content"] = content

                docs.append(doc_info)

            return {"docs": docs}

        return await execute_rxresume_operation(
            operation_name="get rxresume docs",
            operation_func=_operation,
            ctx=ctx,
        )

    @mcp.tool(
        name="get_resume_schema_fragment",
        description="Fetch a summarized fragment of the RxResume JSON schema.",
    )
    async def get_resume_schema_fragment(
        ctx: Context,
        path: Optional[str] = Field(
            default=None,
            description=(
                "JSON pointer or dot path into the schema. "
                "Dot paths traverse properties/items (e.g., sections.experience "
                "or customSections.items). Example: /properties/basics or basics.website."
            ),
        ),
        depth: int = Field(
            default=1,
            ge=0,
            le=6,
            description="How deep to expand nested properties/items.",
        ),
        include_descriptions: bool = Field(
            default=False,
            description="If true, include description fields.",
        ),
        include_constraints: bool = Field(
            default=False,
            description="If true, include numeric/string/array constraints.",
        ),
        include_required: bool = Field(
            default=True,
            description="If true, include required field lists where present.",
        ),
        include_examples: bool = Field(
            default=False,
            description="If true, include example(s) when present.",
        ),
        resolve_refs: bool = Field(
            default=False,
            description="If true, resolve local $ref entries.",
        ),
        max_properties: int = Field(
            default=50,
            ge=1,
            le=500,
            description="Max properties to include per object node.",
        ),
    ) -> Dict[str, Any]:
        async def _operation(client: RxResumeClient) -> Any:
            schema = rx_resources._load_resume_schema()
            node = _resolve_schema_path(schema, path, resolve_refs)

            summary = _summarize_schema_node(
                node,
                schema,
                depth=depth,
                include_descriptions=include_descriptions,
                include_constraints=include_constraints,
                include_required=include_required,
                include_examples=include_examples,
                max_properties=max_properties,
                resolve_refs=resolve_refs,
                seen_refs=set(),
            )

            return {
                "path": path or "#",
                "depth": depth,
                "summary": summary,
            }

        return await execute_rxresume_operation(
            operation_name="get resume schema fragment",
            operation_func=_operation,
            ctx=ctx,
        )
