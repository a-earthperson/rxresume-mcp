"""Shared item spec wiring."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Protocol, Sequence

from pydantic import BaseModel, ConfigDict, Field, create_model


class FieldAdapter(Protocol):
    """Protocol for field adapters used by ItemSpec."""

    def apply_defaults(self, payload: Dict[str, Any]) -> None: ...

    def reshape(self, payload: Dict[str, Any]) -> Dict[str, Any]: ...

    def build_update_ops(
        self, section: str, item_id: str, payload: Dict[str, Any]
    ) -> List[Dict[str, Any]]: ...


@dataclass(frozen=True)
class FieldSpec:
    """Specification for an item field and its adapter."""

    name: str
    field_type: Any
    adapter: FieldAdapter
    alias: str | None = None
    source_path: Sequence[str] | None = None
    source_getter: Callable[[Dict[str, Any]], Any] | None = None
    source_key: str | None = None


@dataclass(frozen=True)
class ItemSpec:
    """Specification for mapping item payloads to/from MCP data."""

    key: str
    adapters: Sequence[FieldAdapter]

    def apply_defaults(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Apply adapter defaults and return a normalized payload."""
        normalized = dict(payload)
        for adapter in self.adapters:
            adapter.apply_defaults(normalized)
        return normalized

    def reshape_item(self, payload: Any) -> Any:
        """Return a response-ready item payload."""
        if not isinstance(payload, dict):
            return payload
        normalized: Dict[str, Any] = {"id": payload.get("id")}
        for adapter in self.adapters:
            normalized.update(adapter.reshape(payload))
        return normalized

    def reshape_items(self, payload: Any) -> Any:
        """Return a response-ready items payload."""
        if isinstance(payload, list):
            return [self.reshape_item(item) for item in payload]
        return payload

    def build_update_ops(
        self, item_id: str, payload: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Build patch ops for item updates."""
        ops: List[Dict[str, Any]] = []
        for adapter in self.adapters:
            ops.extend(adapter.build_update_ops(self.key, item_id, payload))
        if payload:
            raise ValueError(
                f"Unexpected fields in {self.key} update: {sorted(payload)}"
            )
        if not ops:
            raise ValueError(f"No fields provided to update for item id: {item_id}")
        return ops


@dataclass(frozen=True)
class ObjectSpec:
    """Specification for mapping object payloads to/from MCP data."""

    name: str
    field_specs: Sequence[FieldSpec]
    adapters: Sequence[FieldAdapter]
    source_root: Sequence[str] | None = None
    context_section: str = ""
    context_item_id: str = ""

    def apply_defaults(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Apply adapter defaults and return a normalized payload."""
        normalized = dict(payload)
        for adapter in self.adapters:
            adapter.apply_defaults(normalized)
        return normalized

    def reshape(self, payload: Any) -> Any:
        """Return a response-ready object payload."""
        if not isinstance(payload, dict):
            return payload
        normalized: Dict[str, Any] = {}
        for adapter in self.adapters:
            normalized.update(adapter.reshape(payload))
        return normalized

    def build_payload(self, resume: Dict[str, Any]) -> Dict[str, Any]:
        """Build a server-keyed payload from a resume document."""
        if not isinstance(resume, dict):
            return {}
        payload: Dict[str, Any] = {}
        for spec in self.field_specs:
            value = _resolve_source_value(resume, spec, self.source_root)
            if value is _MISSING:
                continue
            payload_key = _resolve_payload_key(spec)
            payload[payload_key] = value
        return payload

    def reshape_resume(self, resume: Dict[str, Any]) -> Any:
        """Return a response-ready object payload from a resume document."""
        return self.reshape(self.build_payload(resume))

    def build_update_ops(self, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Build patch ops for object updates."""
        ops: List[Dict[str, Any]] = []
        for adapter in self.adapters:
            ops.extend(
                adapter.build_update_ops(self.context_section, self.context_item_id, payload)
            )
        if payload:
            raise ValueError(
                f"Unexpected fields in {self.name} update: {sorted(payload)}"
            )
        if not ops:
            raise ValueError(f"No fields provided to update for {self.name}.")
        return ops


def build_item_model(
    model_name: str,
    field_specs: Sequence[FieldSpec],
    *,
    populate_by_name: bool = True,
    extra: str = "forbid",
    module: str | None = None,
) -> type[BaseModel]:
    """Create a Pydantic model for item input from field specs."""
    field_definitions: Dict[str, tuple[Any, Any]] = {
        "id": (Optional[str], Field(default=None))
    }
    for spec in field_specs:
        if not getattr(spec.adapter, "include_in_model", True):
            continue
        field_info = (
            Field(default=None, alias=spec.alias)
            if spec.alias
            else Field(default=None)
        )
        field_definitions[spec.name] = (Optional[spec.field_type], field_info)
    return create_model(
        model_name,
        __config__=ConfigDict(extra=extra, populate_by_name=populate_by_name),
        __module__=module or __name__,
        **field_definitions,
    )


def build_object_model(
    model_name: str,
    field_specs: Sequence[FieldSpec],
    *,
    populate_by_name: bool = True,
    extra: str = "forbid",
    module: str | None = None,
) -> type[BaseModel]:
    """Create a Pydantic model for object input from field specs."""
    field_definitions: Dict[str, tuple[Any, Any]] = {}
    for spec in field_specs:
        if not getattr(spec.adapter, "include_in_model", True):
            continue
        field_info = (
            Field(default=None, alias=spec.alias)
            if spec.alias
            else Field(default=None)
        )
        field_definitions[spec.name] = (Optional[spec.field_type], field_info)
    return create_model(
        model_name,
        __config__=ConfigDict(extra=extra, populate_by_name=populate_by_name),
        __module__=module or __name__,
        **field_definitions,
    )


def build_item_spec(key: str, field_specs: Sequence[FieldSpec]) -> ItemSpec:
    """Create an ItemSpec from field specs."""
    return ItemSpec(key=key, adapters=[spec.adapter for spec in field_specs])


def build_object_spec(
    name: str,
    field_specs: Sequence[FieldSpec],
    *,
    source_root: Sequence[str] | None = None,
    context_section: str = "",
    context_item_id: str = "",
) -> ObjectSpec:
    """Create an ObjectSpec from field specs."""
    return ObjectSpec(
        name=name,
        field_specs=field_specs,
        adapters=[spec.adapter for spec in field_specs],
        source_root=source_root,
        context_section=context_section,
        context_item_id=context_item_id,
    )


def resume_path(*parts: str) -> Callable[[Dict[str, Any]], Any]:
    """Create a getter for a nested resume path."""
    def _get(resume: Dict[str, Any]) -> Any:
        current: Any = resume
        for key in parts:
            if not isinstance(current, dict):
                return None
            current = current.get(key)
        return current
    return _get


def resume_data_path(*parts: str) -> Callable[[Dict[str, Any]], Any]:
    """Create a getter rooted at resume.data."""
    return resume_path("data", *parts)


_MISSING = object()


def _resolve_payload_key(spec: FieldSpec) -> str:
    if spec.source_key:
        return spec.source_key
    if hasattr(spec.adapter, "server_key"):
        return getattr(spec.adapter, "server_key")
    return spec.name


def _resolve_source_value(
    resume: Dict[str, Any],
    spec: FieldSpec,
    source_root: Sequence[str] | None,
) -> Any:
    if spec.source_getter is not None:
        return spec.source_getter(resume)
    if spec.source_path is not None:
        return resume_path(*spec.source_path)(resume)
    if source_root is None:
        return _MISSING
    payload_key = _resolve_payload_key(spec)
    return resume_path(*source_root, payload_key)(resume)
