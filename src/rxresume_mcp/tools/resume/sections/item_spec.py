"""Shared item spec wiring."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol, Sequence

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


def build_item_spec(key: str, field_specs: Sequence[FieldSpec]) -> ItemSpec:
    """Create an ItemSpec from field specs."""
    return ItemSpec(key=key, adapters=[spec.adapter for spec in field_specs])
