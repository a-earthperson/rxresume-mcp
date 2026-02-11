"""Shared helpers for section item tools."""

from __future__ import annotations

import re
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar, cast

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from rxresume_mcp import patch_ops
from rxresume_mcp.client import RxResumeClient

from ...core import execute_rxresume_operation
from .field_adapters import parse_period_bounds
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


_RETURN_MODES = ("all", "delta", "none")


def coerce_return_mode(value: Any, *, default: str = "all") -> str:
    """Normalize return_mode values for mutation tools."""
    if value is None:
        value = default
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"return_mode must be one of: {', '.join(_RETURN_MODES)}")
    normalized = value.strip().lower()
    if normalized not in _RETURN_MODES:
        raise ValueError(f"return_mode must be one of: {', '.join(_RETURN_MODES)}")
    return normalized


def _select_items_by_ids(items: Any, ids: set[str]) -> List[Any]:
    """Filter an items list to dict entries with id in ids."""
    if not isinstance(items, list) or not ids:
        return []
    selected: List[Any] = []
    for item in items:
        if isinstance(item, dict) and item.get("id") in ids:
            selected.append(item)
    return selected


def shape_mutation_result(
    *,
    all_items: Any,
    return_mode: str,
    created_ids: List[str] | None = None,
    updated_ids: List[str] | None = None,
    deleted_ids: List[str] | None = None,
) -> Any:
    """
    Shape mutation responses to avoid returning O(N) lists when not needed.

    - all:   return the full (current) items list (back-compat).
    - delta: return only created/updated items and deleted ids.
    - none:  return ids only (no items payloads).
    """
    mode = coerce_return_mode(return_mode)
    created = list(created_ids or [])
    updated = list(updated_ids or [])
    deleted = list(deleted_ids or [])
    if mode == "all":
        return all_items
    if mode == "none":
        return {"created_ids": created, "updated_ids": updated, "deleted_ids": deleted}
    # delta
    created_items = _select_items_by_ids(all_items, set(created))
    updated_items = _select_items_by_ids(all_items, set(updated))
    return {"created": created_items, "updated": updated_items, "deleted": deleted}


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


_PERIOD_BOUND_KEYS = ("startDate", "endDate")


def _fill_period_bounds_from_existing(
    payload: Dict[str, Any],
    *,
    existing_item: Optional[Dict[str, Any]],
    section_label: str = "item",
) -> None:
    """
    If payload partially updates startDate/endDate, fill the missing side from existing `period`.

    This keeps patch semantics safe: mutating one bound doesn't clobber the other.
    """
    has_start = _PERIOD_BOUND_KEYS[0] in payload
    has_end = _PERIOD_BOUND_KEYS[1] in payload
    if not has_start and not has_end:
        return
    if has_start and has_end:
        return

    if not existing_item:
        raise ValueError(
            f"{section_label} updates to startDate/endDate require an existing item to preserve the untouched bound"
        )
    existing_period = existing_item.get("period")
    start_existing, end_existing = parse_period_bounds(existing_period)
    if (
        isinstance(existing_period, str)
        and existing_period.strip()
        and start_existing is None
        and end_existing is None
    ):
        raise ValueError(
            f"Cannot partially update {section_label} startDate/endDate because the existing upstream period "
            "is not parseable. Provide both startDate and endDate to overwrite it."
        )
    if not has_start:
        payload[_PERIOD_BOUND_KEYS[0]] = start_existing
    if not has_end:
        payload[_PERIOD_BOUND_KEYS[1]] = end_existing


def build_update_ops_for_payload(
    spec: ItemSpec,
    *,
    item_id: str,
    payload: Dict[str, Any],
    existing_item: Optional[Dict[str, Any]] = None,
    section_label: str = "item",
) -> List[Dict[str, Any]]:
    """Build update ops for a raw payload dict with period-safe semantics."""
    normalized = dict(payload)
    _fill_period_bounds_from_existing(
        normalized, existing_item=existing_item, section_label=section_label
    )
    return spec.build_update_ops(item_id, normalized)


def build_update_ops_with_spec(
    item: BaseModel,
    spec: ItemSpec,
    *,
    existing_items_by_id: Optional[Dict[str, Dict[str, Any]]] = None,
    section_label: str = "item",
) -> List[Dict[str, Any]]:
    """Build update ops using an ItemSpec."""
    payload = item.model_dump(exclude_unset=True)
    item_id = payload.pop("id", None)
    if not item_id or not isinstance(item_id, str):
        raise ValueError("item.id is required for update")
    existing_item = existing_items_by_id.get(item_id) if existing_items_by_id else None
    return build_update_ops_for_payload(
        spec,
        item_id=item_id,
        payload=payload,
        existing_item=existing_item,
        section_label=section_label,
    )


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
        return_mode: Any = Field(
            default="delta",
            description="Return mode for mutations: delta (default), all, or none.",
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
            reshaped = spec.reshape_items(result)
            return shape_mutation_result(
                all_items=reshaped,
                return_mode=return_mode,
                created_ids=created_ids,
            )

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
        return_mode: Any = Field(
            default="all",
            description="Return mode for mutations: all (default), delta, or none.",
        ),
    ) -> Dict[str, Any]:
        async def _operation(client: RxResumeClient) -> Any:
            if not isinstance(resume_id, str) or not resume_id:
                raise ValueError("resume_id must be a non-empty string")
            if item_ids is None:
                raise ValueError("item_ids is required")
            deleted_ids = coerce_item_ids(item_ids)
            ops: List[Dict[str, Any]] = []
            for item_id in deleted_ids:
                ops.append(
                    patch_ops.op_remove(patch_ops.path_section_item(section, item_id))
                )
            result = await apply_section_item_patch(
                client, resume_id, section, ops, label=label
            )
            reshaped = spec.reshape_items(result)
            return shape_mutation_result(
                all_items=reshaped,
                return_mode=return_mode,
                deleted_ids=deleted_ids,
            )

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
        return_mode: Any = Field(
            default="all",
            description="Return mode for mutations: all (default), delta, or none.",
        ),
    ) -> Dict[str, Any]:
        async def _operation(client: RxResumeClient) -> Any:
            if not isinstance(resume_id, str) or not resume_id:
                raise ValueError("resume_id must be a non-empty string")
            clear_instructions = coerce_clear_instructions(clear)
            if items is None or (isinstance(items, list) and not items):
                # Allow "clear-only" updates: callers can clear fields without
                # also providing items payloads (Issue 9 in the report).
                if not clear_instructions:
                    raise ValueError("items is required unless clear is provided")
                model_items: List[ModelT] = []
            else:
                model_items = coerce_model_items(items, item_model)

            updated_ids: List[str] = []
            for model_item in model_items:
                dumped = model_item.model_dump(exclude_unset=True)
                item_id = dumped.get("id")
                if isinstance(item_id, str) and item_id:
                    updated_ids.append(item_id)
            for instruction in clear_instructions:
                item_id = instruction.get("id")
                if isinstance(item_id, str) and item_id:
                    updated_ids.append(item_id)

            # If any update touches only one bound (startDate/endDate), we need
            # existing upstream state so we can preserve the untouched bound.
            needs_existing_period = False
            for model_item in model_items:
                dumped = model_item.model_dump(exclude_unset=True)
                has_start = "startDate" in dumped
                has_end = "endDate" in dumped
                if has_start ^ has_end:
                    needs_existing_period = True
                    break
            if not needs_existing_period:
                for instruction in clear_instructions:
                    fields = instruction.get("fields") or []
                    if ("startDate" in fields) ^ ("endDate" in fields):
                        needs_existing_period = True
                        break

            existing_by_id: Optional[Dict[str, Dict[str, Any]]] = None
            if needs_existing_period:
                resume = _require_resume_object(await client.get_resume(resume_id))
                existing_items = extract_section_items(resume, section, label=label)
                existing_by_id = {
                    item.get("id"): item
                    for item in existing_items
                    if isinstance(item, dict) and isinstance(item.get("id"), str)
                }

            ops: List[Dict[str, Any]] = []
            for model_item in model_items:
                ops.extend(
                    build_update_ops_with_spec(
                        model_item,
                        spec,
                        existing_items_by_id=existing_by_id,
                        section_label=noun,
                    )
                )

            # Apply explicit clears (useful to avoid "null spraying" in item payloads).
            for instruction in clear_instructions:
                item_id = instruction["id"]
                fields = instruction["fields"]
                if not fields:
                    continue
                existing_item = existing_by_id.get(item_id) if existing_by_id else None
                ops.extend(
                    build_update_ops_for_payload(
                        spec,
                        item_id=item_id,
                        payload={field: None for field in fields},
                        existing_item=existing_item,
                        section_label=noun,
                    )
                )

            if not ops:
                raise ValueError("No updates provided (provide items and/or clear fields).")
            result = await apply_section_item_patch(
                client, resume_id, section, ops, label=label
            )
            reshaped = spec.reshape_items(result)
            return shape_mutation_result(
                all_items=reshaped,
                return_mode=return_mode,
                updated_ids=updated_ids,
            )

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
