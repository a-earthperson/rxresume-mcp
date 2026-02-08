"""Register tools that operate on resume sections and items."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, cast

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

from rxresume_mcp import patch_ops
from rxresume_mcp.rxresume_client import RxResumeClient

from .core import execute_rxresume_operation
from .normalize import _normalize_url_fields
from .patching import _build_summary
from .sections import (
    _custom_section_exists,
    _ensure_custom_section_type,
    _ensure_item_id,
    _ensure_item_ids,
    _ensure_object_payload,
    _ensure_section_type,
    _extract_section_data,
    _find_custom_section,
    _find_item,
    _require_resume_data,
    _require_resume_object,
)


def register_section_tools(mcp: FastMCP) -> None:
    """Register tools that edit or fetch resume sections."""

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

            # Map high-level actions to the minimal patch ops needed.
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
            "Add/update/remove custom sections using JSON Patch (type must be valid). "
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
