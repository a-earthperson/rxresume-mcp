"""
Helpers for building JSON Patch operations.
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Sequence, Union

from pydantic import BaseModel, Field, TypeAdapter, ValidationError

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


class _PatchBase(BaseModel):
    model_config = {"populate_by_name": True, "extra": "forbid"}


class JsonPatchAdd(_PatchBase):
    op: Literal["add"]
    path: str
    value: Any


class JsonPatchReplace(_PatchBase):
    op: Literal["replace"]
    path: str
    value: Any


class JsonPatchRemove(_PatchBase):
    op: Literal["remove"]
    path: str


class JsonPatchTest(_PatchBase):
    op: Literal["test"]
    path: str
    value: Any


class JsonPatchMove(_PatchBase):
    op: Literal["move"]
    from_: str = Field(alias="from")
    path: str

    @property
    def from_path(self) -> str:
        return self.from_


class JsonPatchCopy(_PatchBase):
    op: Literal["copy"]
    from_: str = Field(alias="from")
    path: str

    @property
    def from_path(self) -> str:
        return self.from_


JsonPatchOp = Union[
    JsonPatchAdd,
    JsonPatchReplace,
    JsonPatchRemove,
    JsonPatchTest,
    JsonPatchMove,
    JsonPatchCopy,
]

_patch_ops_adapter = TypeAdapter(List[JsonPatchOp])


def validate_patch_ops(ops: Sequence[JsonPatchOp | Dict[str, Any]]) -> List[Dict[str, Any]]:
    try:
        parsed = _patch_ops_adapter.validate_python(list(ops))
    except ValidationError as exc:
        raise ValueError(f"Invalid JSON Patch operations: {exc}") from exc
    return [op.model_dump(by_alias=True) for op in parsed]


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


def _escape_segment(segment: str) -> str:
    return segment.replace("~", "~0").replace("/", "~1")


def _pointer(*segments: str) -> str:
    return "/" + "/".join(_escape_segment(segment) for segment in segments)


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
    return _pointer("data", "customSections", "id", custom_section_id, "items", "id", item_id)


def path_custom_section_item_field(custom_section_id: str, item_id: str, field: str) -> str:
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

