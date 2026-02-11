"""
Helpers for building JSON Patch operations.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Sequence

import jsonpatch
from jsonpointer import JsonPointer

SECTION_TYPES: tuple[str, ...] = (
    "profiles",
    "experience",
    "education",
    "projects",
    "skills",
    "languages",
    "interests",
    "awards",
    "certifications",
    "publications",
    "volunteer",
    "references",
)

JsonPatchOp = Dict[str, Any]

_OP_ALLOWED_KEYS: dict[str, frozenset[str]] = {
    "add": frozenset({"op", "path", "value"}),
    "remove": frozenset({"op", "path"}),
    "replace": frozenset({"op", "path", "value"}),
    "move": frozenset({"op", "from", "path"}),
    "copy": frozenset({"op", "from", "path"}),
    "test": frozenset({"op", "path", "value"}),
}

_OP_REQUIRED_KEYS: dict[str, frozenset[str]] = {
    "add": frozenset({"op", "path", "value"}),
    "remove": frozenset({"op", "path"}),
    "replace": frozenset({"op", "path", "value"}),
    "move": frozenset({"op", "from", "path"}),
    "copy": frozenset({"op", "from", "path"}),
    "test": frozenset({"op", "path", "value"}),
}


def validate_patch_ops(
    ops: Sequence[Mapping[str, Any] | Any],
) -> List[Dict[str, Any]]:
    """
    Validate JSON Patch ops (RFC 6902-ish) and normalize aliases.

    This is intentionally strict:
    - forbids unknown keys (mirrors prior Pydantic `extra="forbid"` behavior)
    - normalizes `from_` -> `from` for move/copy ops
    - ensures `op/path/from` are strings where required
    """
    if not isinstance(ops, Sequence):
        raise ValueError("Invalid JSON Patch operations: expected a sequence")

    normalized_ops: List[Dict[str, Any]] = []
    for raw in list(ops):
        if isinstance(raw, dict):
            op = dict(raw)
        elif hasattr(raw, "model_dump") and callable(getattr(raw, "model_dump")):
            # Support any pydantic-ish inputs while keeping stable wire keys.
            op = raw.model_dump(by_alias=True)
        elif hasattr(raw, "dict") and callable(getattr(raw, "dict")):
            op = raw.dict()
        else:
            raise ValueError(
                "Invalid JSON Patch operations: each operation must be a dict-like object"
            )

        # Normalize common alias forms.
        if "from_" in op and "from" not in op:
            op["from"] = op.pop("from_")

        op_name = op.get("op")
        if not isinstance(op_name, str) or not op_name:
            raise ValueError(
                "Invalid JSON Patch operations: each operation must have a non-empty 'op' string"
            )

        allowed = _OP_ALLOWED_KEYS.get(op_name)
        required = _OP_REQUIRED_KEYS.get(op_name)
        if allowed is None or required is None:
            # Let jsonpatch generate the canonical error string too, but keep the
            # error message prefix stable for callers/tests.
            raise ValueError(f"Invalid JSON Patch operations: unknown op '{op_name}'")

        extra_keys = sorted(set(op.keys()) - set(allowed))
        if extra_keys:
            raise ValueError(
                f"Invalid JSON Patch operations: unexpected keys for op '{op_name}': {extra_keys}"
            )

        missing_keys = sorted(set(required) - set(op.keys()))
        if missing_keys:
            raise ValueError(
                f"Invalid JSON Patch operations: missing keys for op '{op_name}': {missing_keys}"
            )

        path = op.get("path")
        if not isinstance(path, str) or not path:
            raise ValueError(
                "Invalid JSON Patch operations: 'path' must be a non-empty string"
            )
        if op_name in {"move", "copy"}:
            from_path = op.get("from")
            if not isinstance(from_path, str) or not from_path:
                raise ValueError(
                    "Invalid JSON Patch operations: 'from' must be a non-empty string for move/copy ops"
                )

        normalized_ops.append(op)

    try:
        # Structural validation. We do *not* apply patches here because that would
        # incorrectly reject paths that are valid for the upstream resume object.
        jsonpatch.JsonPatch(normalized_ops)
    except Exception as exc:
        raise ValueError(f"Invalid JSON Patch operations: {exc}") from exc

    return normalized_ops


def op_add(path: str, value: Any) -> Dict[str, Any]:
    return {"op": "add", "path": path, "value": value}


def op_replace(path: str, value: Any) -> Dict[str, Any]:
    return {"op": "replace", "path": path, "value": value}


def op_remove(path: str) -> Dict[str, Any]:
    return {"op": "remove", "path": path}


def op_test(path: str, value: Any) -> Dict[str, Any]:
    return {"op": "test", "path": path, "value": value}


def op_move(from_path: str, path: str) -> Dict[str, Any]:
    return {"op": "move", "from": from_path, "path": path}


def op_copy(from_path: str, path: str) -> Dict[str, Any]:
    return {"op": "copy", "from": from_path, "path": path}


def _pointer(*segments: str) -> str:
    # RFC 6901 encoding/escaping is delegated to jsonpointer.
    return JsonPointer.from_parts(list(segments)).path


def path_basics_field(field: str) -> str:
    return _pointer("data", "basics", field)


def path_summary_field(field: str) -> str:
    return _pointer("data", "summary", field)


def path_section_items(section: str) -> str:
    return _pointer("data", "sections", section, "items")


def path_section_items_append(section: str) -> str:
    return _pointer("data", "sections", section, "items", "-")


def path_section_item(section: str, item_id: str) -> str:
    return _pointer("data", "sections", section, "items", "id", item_id)


def path_section_item_field(section: str, item_id: str, field: str) -> str:
    return _pointer("data", "sections", section, "items", "id", item_id, field)


def path_custom_sections() -> str:
    return _pointer("data", "customSections")


def path_custom_sections_append() -> str:
    return _pointer("data", "customSections", "-")


def path_custom_section(custom_section_id: str) -> str:
    return _pointer("data", "customSections", "id", custom_section_id)


def path_custom_section_field(custom_section_id: str, field: str) -> str:
    return _pointer("data", "customSections", "id", custom_section_id, field)


def path_custom_section_items(custom_section_id: str) -> str:
    return _pointer("data", "customSections", "id", custom_section_id, "items")


def path_custom_section_items_append(custom_section_id: str) -> str:
    return _pointer("data", "customSections", "id", custom_section_id, "items", "-")


def path_custom_section_item(custom_section_id: str, item_id: str) -> str:
    return _pointer(
        "data", "customSections", "id", custom_section_id, "items", "id", item_id
    )


def path_custom_section_item_field(
    custom_section_id: str, item_id: str, field: str
) -> str:
    return _pointer(
        "data",
        "customSections",
        "id",
        custom_section_id,
        "items",
        "id",
        item_id,
        field,
    )
