"""Schema path resolution and summarization helpers."""

from __future__ import annotations

from typing import Any, Dict, List

from .pointers import _parse_json_pointer


def _parse_schema_pointer(path: str | None) -> List[str]:
    """Normalize schema pointers to JSON pointer segments."""
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
    """Resolve a schema node by JSON pointer or dot path."""
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
    """Traverse dot paths that implicitly walk properties/items."""
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
    """Resolve a single dot segment, honoring properties/items and refs."""
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
    """Resolve local $ref entries when requested."""
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
    """Summarize a schema node with optional expansion and constraints."""
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
