"""Shared spec wiring."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Mapping, Optional, Protocol, Sequence

from pydantic import BaseModel, ConfigDict, Field, create_model

from rxresume_mcp import patch_ops


class PatchTarget(Protocol):
    """Protocol for resolving patch paths for fields."""

    def field_path(self, field: str) -> str: ...


@dataclass(frozen=True)
class MappedPatchTarget:
    """Patch target with explicit field path overrides."""

    default_builder: Callable[[str], str]
    overrides: Mapping[str, str] = field(default_factory=dict)

    def field_path(self, field: str) -> str:
        override = self.overrides.get(field)
        if override is not None:
            return override
        return self.default_builder(field)


@dataclass(frozen=True)
class SectionItemPatchTarget:
    """Patch target for section item fields."""

    section: str
    item_id: str

    def field_path(self, field: str) -> str:
        return patch_ops.path_section_item_field(self.section, self.item_id, field)


class FieldAdapter(Protocol):
    """Protocol for field adapters used by specs."""

    def apply_defaults(self, payload: Dict[str, Any]) -> None: ...

    def reshape(self, payload: Dict[str, Any]) -> Dict[str, Any]: ...

    def build_update_ops(
        self, payload: Dict[str, Any], target: PatchTarget
    ) -> List[Dict[str, Any]]: ...


@dataclass(frozen=True)
class FieldSpec:
    """Specification for an item field and its adapter."""

    name: str
    field_type: Any
    adapter: FieldAdapter
    alias: str | None = None


@dataclass(frozen=True)
class Spec:
    """Specification for mapping object payloads to/from MCP data."""

    name: str
    adapters: Sequence[FieldAdapter]

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

    def build_update_ops(
        self, payload: Dict[str, Any], target: PatchTarget
    ) -> List[Dict[str, Any]]:
        """Build patch ops for updates."""
        ops: List[Dict[str, Any]] = []
        for adapter in self.adapters:
            ops.extend(adapter.build_update_ops(payload, target))
        if payload:
            raise ValueError(
                f"Unexpected fields in {self.name} update: {sorted(payload)}"
            )
        if not ops:
            raise ValueError(f"No fields provided to update for {self.name}.")
        return ops


@dataclass(frozen=True)
class ItemSpec:
    """Specification for mapping item payloads to/from MCP data."""

    key: str
    spec: Spec

    @property
    def adapters(self) -> Sequence[FieldAdapter]:
        return self.spec.adapters

    def apply_defaults(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Apply adapter defaults and return a normalized payload."""
        return self.spec.apply_defaults(payload)

    def reshape_item(self, payload: Any) -> Any:
        """Return a response-ready item payload."""
        if not isinstance(payload, dict):
            return payload
        normalized: Dict[str, Any] = {"id": payload.get("id")}
        normalized.update(self.spec.reshape(payload))
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
        target = SectionItemPatchTarget(section=self.key, item_id=item_id)
        try:
            return self.spec.build_update_ops(payload, target)
        except ValueError as exc:
            message = str(exc)
            if message.startswith("No fields provided to update for"):
                raise ValueError(
                    f"No fields provided to update for item id: {item_id}"
                ) from exc
            raise


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
    return ItemSpec(key=key, spec=build_spec(key, field_specs))


def build_spec(name: str, field_specs: Sequence[FieldSpec]) -> Spec:
    """Create a Spec from field specs."""
    return Spec(name=name, adapters=[spec.adapter for spec in field_specs])
