"""Shared helpers for section item tools."""

from __future__ import annotations

import re
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar, cast

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from rxresume_mcp import patch_ops
from rxresume_mcp.client import RxResumeClient

from ...core import execute_rxresume_operation
from .normalize import _normalize_url_fields
from .sections import (
    _ensure_item_id,
    _ensure_object_payload,
    _extract_section_data,
    _require_resume_object,
)
from .item_spec import ItemSpec, PatchTarget, Spec

ModelT = TypeVar("ModelT", bound=BaseModel)

_DESCRIPTION_UL_RE = re.compile(r"<ul[^>]*>.*?</ul>", re.IGNORECASE | re.DOTALL)
_DESCRIPTION_LI_RE = re.compile(r"<li[^>]*>(.*?)</li>", re.IGNORECASE | re.DOTALL)
_DESCRIPTION_TAG_RE = re.compile(r"<[^>]+>")


def ensure_non_empty_string(value: Any, fallback: str = " ") -> str:
    """Return value if it is a non-empty string; otherwise fallback."""
    if isinstance(value, str) and value.strip() != "":
        return value
    return fallback


def _strip_html_tags(value: str) -> str:
    """Remove HTML tags from a string."""
    return _DESCRIPTION_TAG_RE.sub("", value).strip()


def build_summary_highlights_description(
    summary: Optional[str], highlights: Optional[List[str]]
) -> str:
    """Build a description HTML string from summary and highlights."""
    summary_value = summary.strip() if isinstance(summary, str) else ""
    highlight_items = [
        item.strip()
        for item in (highlights or [])
        if isinstance(item, str) and item.strip()
    ]
    if not summary_value and not highlight_items:
        return ""
    parts: List[str] = []
    if summary_value:
        if "<" in summary_value and ">" in summary_value:
            parts.append(summary_value)
        else:
            parts.append(f"<p>{summary_value}</p>")
    if highlight_items:
        list_items = "".join(f"<li><p>{item}</p></li>" for item in highlight_items)
        parts.append(f"<ul>{list_items}</ul>")
    return "".join(parts)


def split_summary_highlights_description(
    description: Any,
) -> tuple[Optional[str], Optional[List[str]]]:
    """Split a description HTML string into summary and highlights."""
    if not isinstance(description, str) or not description:
        return None, None
    highlights = [
        _strip_html_tags(item) for item in _DESCRIPTION_LI_RE.findall(description)
    ]
    highlights = [item for item in highlights if item]
    summary = _DESCRIPTION_UL_RE.sub("", description).strip()
    if not _strip_html_tags(summary):
        summary = ""
    summary_value = summary or None
    highlights_value = highlights or None
    return summary_value, highlights_value


def coerce_item_ids(item_ids: Any, label: str = "item_ids") -> List[str]:
    """Normalize an id or list of ids into a list of non-empty strings."""
    if isinstance(item_ids, str):
        if not item_ids:
            raise ValueError(f"{label} must not be empty")
        return [item_ids]
    if isinstance(item_ids, list):
        if not item_ids:
            raise ValueError(f"{label} list must not be empty")
        ids: List[str] = []
        for item_id in item_ids:
            if not isinstance(item_id, str) or not item_id:
                raise ValueError(f"{label} must be non-empty strings")
            ids.append(item_id)
        return ids
    raise ValueError(f"{label} must be a string or a list of strings")


def coerce_clear_fields(value: Any, *, label: str = "clear_fields") -> List[str]:
    """Normalize clear field names into a list of non-empty strings."""
    if value is None:
        return []
    if isinstance(value, str):
        if not value:
            raise ValueError(f"{label} must not be empty")
        return [value]
    if isinstance(value, list):
        fields: List[str] = []
        for item in value:
            if not isinstance(item, str) or not item:
                raise ValueError(f"{label} must contain non-empty strings only")
            fields.append(item)
        return fields
    raise ValueError(f"{label} must be a string or a list of strings")


def coerce_clear_instructions(value: Any) -> List[Dict[str, Any]]:
    """
    Normalize clear instructions into:
      [{"id": "<item_id>", "fields": ["field1", ...]}, ...]
    Accepts:
      - None
      - {"<id>": ["field", ...], ...}
      - [{"id": "...", "fields": [...]}, ...]
    """
    if value is None:
        return []
    if isinstance(value, dict):
        instructions: List[Dict[str, Any]] = []
        for item_id, fields in value.items():
            if not isinstance(item_id, str) or not item_id:
                raise ValueError("clear keys must be non-empty strings (item ids)")
            instructions.append(
                {
                    "id": item_id,
                    "fields": coerce_clear_fields(fields, label="clear.fields"),
                }
            )
        return instructions
    if isinstance(value, list):
        instructions = []
        for entry in value:
            if not isinstance(entry, dict):
                raise ValueError("clear entries must be objects like {id, fields}")
            item_id = entry.get("id")
            fields = entry.get("fields")
            if not isinstance(item_id, str) or not item_id:
                raise ValueError("clear.id must be a non-empty string")
            instructions.append(
                {
                    "id": item_id,
                    "fields": coerce_clear_fields(fields, label="clear.fields"),
                }
            )
        return instructions
    raise ValueError(
        "clear must be an object mapping id->fields or a list of {id, fields}"
    )


def coerce_model_items(
    items: Any, model_cls: Type[ModelT], label: str = "items"
) -> List[ModelT]:
    """Normalize an item or list of items into a list of model instances."""
    if isinstance(items, model_cls):
        return [items]
    if isinstance(items, list):
        if not items:
            raise ValueError(f"{label} list must not be empty")
        normalized: List[ModelT] = []
        for item in items:
            if isinstance(item, model_cls):
                normalized.append(item)
            elif isinstance(item, dict):
                normalized.append(model_cls.model_validate(item))
            else:
                raise ValueError(f"{label} must contain objects only")
        return normalized
    if isinstance(items, dict):
        return [model_cls.model_validate(items)]
    raise ValueError(f"{label} must be an object or a list of objects")


def coerce_object_input(
    value: Any, model_cls: Type[ModelT], label: str = "payload"
) -> ModelT:
    """Normalize an object input into a model instance."""
    if isinstance(value, model_cls):
        return value
    if isinstance(value, dict):
        return model_cls.model_validate(value)
    raise ValueError(f"{label} must be an object")


def extract_section_items(
    resume: Dict[str, Any], section: str, *, label: str | None = None
) -> List[Any]:
    """Return the items array for a section or raise if malformed."""
    label_value = label or section.capitalize()
    section_data = _extract_section_data(resume, f"sections.{section}")["data"]
    if not isinstance(section_data, dict):
        raise ValueError(f"{label_value} section is not a JSON object")
    items = section_data.get("items")
    if not isinstance(items, list):
        raise ValueError(f"{label_value} items is not an array")
    return items


def prepare_item_with_spec(
    item: BaseModel, created_ids: List[str], spec: ItemSpec
) -> Dict[str, Any]:
    """Prepare an item payload using an ItemSpec."""
    payload = item.model_dump(exclude_unset=True)
    payload = _ensure_object_payload(payload, "item")
    # Proposal C: client-supplied ids are not allowed on create. We still tolerate
    # `id=None` (common in callers) but we never persist/forward it.
    if "id" in payload:
        provided = payload.get("id")
        if provided not in (None, ""):
            raise ValueError("item.id must not be provided when creating items")
        payload.pop("id", None)
    payload["hidden"] = False
    payload = _ensure_item_id(payload, created_ids)
    payload = spec.apply_defaults(payload)
    payload = cast(Dict[str, Any], _normalize_url_fields(payload))
    return payload


def build_update_ops_with_spec(item: BaseModel, spec: ItemSpec) -> List[Dict[str, Any]]:
    """Build update ops using an ItemSpec."""
    payload = item.model_dump(exclude_unset=True)
    item_id = payload.pop("id", None)
    if not item_id or not isinstance(item_id, str):
        raise ValueError("item.id is required for update")
    return spec.build_update_ops(item_id, payload)


def register_section_item_tools(
    mcp: FastMCP,
    *,
    tool_prefix: str,
    section: str,
    label: str,
    noun: str,
    spec: ItemSpec,
    item_model: Type[ModelT],
    items_type: Any,
    item_ids_type: Any,
) -> None:
    """Register standard list/create/delete/update tools for a section."""
    if spec.key != section:
        raise ValueError(f"ItemSpec key must match section: {spec.key} != {section}")

    async def _list(
        ctx: Context,
        resume_id: Any = Field(default=None, description="Resume ID (UUID string)."),
    ) -> Dict[str, Any]:
        async def _operation(client: RxResumeClient) -> Any:
            if not isinstance(resume_id, str) or not resume_id:
                raise ValueError("resume_id must be a non-empty string")
            resume = _require_resume_object(await client.get_resume(resume_id))
            items = extract_section_items(resume, section, label=label)
            return spec.reshape_items(items)

        return await execute_rxresume_operation(
            operation_name=f"list {noun}: {resume_id}",
            operation_func=_operation,
            ctx=ctx,
            resume_id=resume_id if isinstance(resume_id, str) and resume_id else None,
        )

    mcp.tool(
        name=f"{tool_prefix}.list",
        description=f"List {noun} items for a resume.",
    )(_list)

    async def _create(
        ctx: Context,
        resume_id: Any = Field(default=None, description="Resume ID (UUID string)."),
        items: Any = Field(
            default=None, description=f"{noun.title()} item or list of items to add."
        ),
    ) -> Dict[str, Any]:
        async def _operation(client: RxResumeClient) -> Any:
            if not isinstance(resume_id, str) or not resume_id:
                raise ValueError("resume_id must be a non-empty string")
            if items is None:
                raise ValueError("items is required")
            created_ids: List[str] = []
            ops: List[Dict[str, Any]] = []
            for item in coerce_model_items(items, item_model):
                payload = prepare_item_with_spec(item, created_ids, spec)
                ops.append(
                    patch_ops.op_add(
                        patch_ops.path_section_items_append(section), payload
                    )
                )
            result = await apply_section_item_patch(
                client, resume_id, section, ops, label=label
            )
            return spec.reshape_items(result)

        return await execute_rxresume_operation(
            operation_name=f"add {noun}: {resume_id}",
            operation_func=_operation,
            ctx=ctx,
            resume_id=resume_id if isinstance(resume_id, str) and resume_id else None,
        )

    mcp.tool(
        name=f"{tool_prefix}.item.create",
        description=(
            f"Add one or more {noun} items. "
            "All fields are optional; hidden is forced to false."
        ),
    )(_create)

    async def _delete(
        ctx: Context,
        resume_id: Any = Field(default=None, description="Resume ID (UUID string)."),
        item_ids: Any = Field(
            default=None, description="Item id or list of item ids to remove."
        ),
    ) -> Dict[str, Any]:
        async def _operation(client: RxResumeClient) -> Any:
            if not isinstance(resume_id, str) or not resume_id:
                raise ValueError("resume_id must be a non-empty string")
            if item_ids is None:
                raise ValueError("item_ids is required")
            ops: List[Dict[str, Any]] = []
            for item_id in coerce_item_ids(item_ids):
                ops.append(
                    patch_ops.op_remove(patch_ops.path_section_item(section, item_id))
                )
            result = await apply_section_item_patch(
                client, resume_id, section, ops, label=label
            )
            return spec.reshape_items(result)

        return await execute_rxresume_operation(
            operation_name=f"remove {noun}: {resume_id}",
            operation_func=_operation,
            ctx=ctx,
            resume_id=resume_id if isinstance(resume_id, str) and resume_id else None,
        )

    mcp.tool(
        name=f"{tool_prefix}.item.delete",
        description=f"Remove one or more {noun} items by id.",
    )(_delete)

    async def _update(
        ctx: Context,
        resume_id: Any = Field(default=None, description="Resume ID (UUID string)."),
        items: Any = Field(
            default=None, description=f"{noun.title()} item or list of items to update."
        ),
        clear: Any = Field(
            default=None,
            description=(
                "Optional clear instructions. Shape: "
                "`[{id: <item_id>, fields: [<field>, ...]}, ...]` "
                "or `{<item_id>: [<field>, ...], ...}`. "
                "Clearing is performed by writing schema-default placeholder values."
            ),
        ),
    ) -> Dict[str, Any]:
        async def _operation(client: RxResumeClient) -> Any:
            if not isinstance(resume_id, str) or not resume_id:
                raise ValueError("resume_id must be a non-empty string")
            if items is None:
                raise ValueError("items is required")
            ops: List[Dict[str, Any]] = []
            for item in coerce_model_items(items, item_model):
                ops.extend(build_update_ops_with_spec(item, spec))
            # Apply explicit clears (useful to avoid "null spraying" in item payloads).
            for instruction in coerce_clear_instructions(clear):
                item_id = instruction["id"]
                fields = instruction["fields"]
                if not fields:
                    continue
                ops.extend(
                    spec.build_update_ops(item_id, {field: None for field in fields})
                )
            result = await apply_section_item_patch(
                client, resume_id, section, ops, label=label
            )
            return spec.reshape_items(result)

        return await execute_rxresume_operation(
            operation_name=f"update {noun}: {resume_id}",
            operation_func=_operation,
            ctx=ctx,
            resume_id=resume_id if isinstance(resume_id, str) and resume_id else None,
        )

    mcp.tool(
        name=f"{tool_prefix}.item.update",
        description=(
            f"Update one or more {noun} items by id. "
            "item.id is required; other fields are optional."
        ),
    )(_update)


def register_object_tools(
    mcp: FastMCP,
    *,
    tool_prefix: str,
    name: str,
    spec: Spec,
    target: PatchTarget,
    model: Type[ModelT],
    payload_type: Any,
    payload_description: str,
    build_payload: Callable[[Dict[str, Any]], Any],
    extra_update_ops: Optional[Callable[[Dict[str, Any]], List[Dict[str, Any]]]] = None,
    reset_payload: Optional[Any] = None,
    include_delete: bool = True,
) -> None:
    """Register standard get/patch/delete tools for an object."""

    async def _get(
        ctx: Context,
        resume_id: Any = Field(default=None, description="Resume ID (UUID string)."),
    ) -> Dict[str, Any]:
        async def _operation(client: RxResumeClient) -> Any:
            if not isinstance(resume_id, str) or not resume_id:
                raise ValueError("resume_id must be a non-empty string")
            resume = _require_resume_object(await client.get_resume(resume_id))
            return spec.reshape(build_payload(resume))

        return await execute_rxresume_operation(
            operation_name=f"get {name}: {resume_id}",
            operation_func=_operation,
            ctx=ctx,
            resume_id=resume_id if isinstance(resume_id, str) and resume_id else None,
        )

    mcp.tool(
        name=f"{tool_prefix}.get",
        description=f"Get resume {name} fields.",
    )(_get)

    async def _patch(
        ctx: Context,
        resume_id: Any = Field(default=None, description="Resume ID (UUID string)."),
        payload: Any = Field(
            default=None,
            description=payload_description,
        ),
        clear_fields: Any = Field(
            default=None,
            description=(
                "Optional list of field names to clear. "
                "Clearing is performed by writing schema-default placeholder values."
            ),
        ),
    ) -> Dict[str, Any]:
        async def _operation(client: RxResumeClient) -> Any:
            if not isinstance(resume_id, str) or not resume_id:
                raise ValueError("resume_id must be a non-empty string")
            fields_to_clear = coerce_clear_fields(clear_fields)
            if payload is None and not fields_to_clear:
                raise ValueError(f"{name} payload is required")
            payload_dict: Dict[str, Any] = {}
            if payload is not None:
                normalized = coerce_object_input(payload, model, label=name)
                payload_dict = normalized.model_dump(exclude_unset=True)
            for field_name in fields_to_clear:
                payload_dict.setdefault(field_name, None)
            extra_ops = extra_update_ops(dict(payload_dict)) if extra_update_ops else []
            ops = spec.build_update_ops(payload_dict, target)
            ops.extend(extra_ops)
            validated_ops = patch_ops.validate_patch_ops(ops)
            result = await client.patch_resume(resume_id, patch_ops=validated_ops)
            resume = _require_resume_object(result)
            return spec.reshape(build_payload(resume))

        return await execute_rxresume_operation(
            operation_name=f"patch {name}: {resume_id}",
            operation_func=_operation,
            ctx=ctx,
            resume_id=resume_id if isinstance(resume_id, str) and resume_id else None,
        )

    mcp.tool(
        name=f"{tool_prefix}.patch",
        description=f"Patch resume {name} fields (merge semantics). All fields are optional.",
    )(_patch)

    if include_delete:

        async def _delete(
            ctx: Context,
            resume_id: Any = Field(
                default=None, description="Resume ID (UUID string)."
            ),
        ) -> Dict[str, Any]:
            if reset_payload is None:
                raise ValueError(f"No reset payload configured for {name}.")

            async def _operation(client: RxResumeClient) -> Any:
                if not isinstance(resume_id, str) or not resume_id:
                    raise ValueError("resume_id must be a non-empty string")
                # Reuse the same patch building logic, but with the reset payload.
                normalized = coerce_object_input(reset_payload, model, label=name)
                payload_dict = normalized.model_dump(exclude_unset=True)
                extra_ops = (
                    extra_update_ops(dict(payload_dict)) if extra_update_ops else []
                )
                ops = spec.build_update_ops(payload_dict, target)
                ops.extend(extra_ops)
                validated_ops = patch_ops.validate_patch_ops(ops)
                result = await client.patch_resume(resume_id, patch_ops=validated_ops)
                resume = _require_resume_object(result)
                return spec.reshape(build_payload(resume))

            return await execute_rxresume_operation(
                operation_name=f"reset {name}: {resume_id}",
                operation_func=_operation,
                ctx=ctx,
                resume_id=(
                    resume_id if isinstance(resume_id, str) and resume_id else None
                ),
            )

        mcp.tool(
            name=f"{tool_prefix}.delete",
            description=f"Reset resume {name} fields to empty values.",
        )(_delete)


async def apply_section_item_patch(
    client: RxResumeClient,
    resume_id: str,
    section: str,
    ops: List[Dict[str, Any]],
    *,
    label: str | None = None,
) -> List[Any]:
    """Patch a resume and return the updated section items."""
    validated_ops = patch_ops.validate_patch_ops(ops)
    result = await client.patch_resume(resume_id, patch_ops=validated_ops)
    resume = _require_resume_object(result)
    return extract_section_items(resume, section, label=label)
