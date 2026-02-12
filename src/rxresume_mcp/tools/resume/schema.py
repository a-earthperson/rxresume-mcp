"""Schema introspection tools.

The MCP tool surface intentionally uses some `Any`-typed parameters to avoid
pre-handler validation failures that would bypass our structured error envelope.
That makes `list_tools`-provided JSON Schema insufficient for agents to discover
the true expected payload shapes.

`resume.schema.get` exposes a stable, queryable contract with fields, examples,
and semantic constraints tailored for MCP clients.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

from rxresume_mcp.client import RxResumeClient

from ..core import execute_rxresume_operation
from .sections.basics import BasicsInput
from .sections.field_adapters import ParagraphListAdapter
from .sections.generic_section_tools import _SECTION_BINDINGS, _SECTION_ALIASES


def _canonical_json(value: Any) -> str:
    # Stable hash input for schemaVersion; avoid unicode surprises.
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _schema_version(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _resolve_section_name(raw: Any) -> str:
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("target must be a non-empty string")
    name = raw.strip().lower()
    return _SECTION_ALIASES.get(name, name)


def _list_targets() -> Dict[str, Any]:
    sections = sorted(_SECTION_BINDINGS.keys())
    return {
        "targets": ["basics", *sections],
        "notes": [
            "Pass target='basics' for resume.basics payload schema.",
            "Pass target='<section>' for a section item schema (JSON Resume section names).",
        ],
    }


def _build_basics_schema() -> Dict[str, Any]:
    payload_schema = BasicsInput.model_json_schema()
    fields = sorted((payload_schema.get("properties") or {}).keys())

    result: Dict[str, Any] = {
        "kind": "basics",
        "target": "basics",
        "payload": {
            "jsonSchema": payload_schema,
            "fields": fields,
        },
        "constraints": {
            "patchSemantics": {
                "omittedFields": "unchanged",
                "nullOrEmpty": "clears field (writes schema-default placeholders)",
                "profiles": (
                    "basics.profiles replaces the entire profiles list; "
                    "each entry may omit id (a new id will be generated)"
                ),
            },
            "types": {
                "location": "string (not a structured JSON Resume location object)",
                "profiles": "list of profile objects (see patchSemantics.profiles)",
            },
            "responses": {
                "get": "returns a canonical basics object; profiles reflect the current profiles section",
            },
        },
        "operations": {
            "get": {"tool": "resume.basics.get", "args": {"resume_id": "<uuid>"}},
            "update": {
                "tool": "resume.basics.update",
                "args": {
                    "resume_id": "<uuid>",
                    "payload": {"name": "Ada"},
                    "clear_fields": [],
                },
            },
        },
        "examples": {
            "updateMinimal": {
                "resume_id": "<uuid>",
                "payload": {"name": "Ada Lovelace"},
            },
            "updateTypical": {
                "resume_id": "<uuid>",
                "payload": {
                    "name": "Ada Lovelace",
                    "label": "Software Engineer",
                    "email": "ada@example.com",
                    "location": "London, UK",
                    "url": "https://example.com",
                    "summary": "Built analytical engines.",
                },
            },
            "updateProfilesById": {
                "resume_id": "<uuid>",
                "payload": {
                    "profiles": [{"id": "<profile-id>", "url": "https://example.com"}]
                },
            },
        },
    }
    result["schemaVersion"] = _schema_version(result)
    return result


def _example_item_for_section(section: str, fields: List[str]) -> Dict[str, Any]:
    # Heuristic examples, tuned to your canonical external field names.
    ex: Dict[str, Any] = {}
    if "name" in fields:
        ex["name"] = "Example"
    if section == "work":
        ex.update({"name": "Tooling Inc", "position": "Engineer", "location": "Remote"})
    if section == "education":
        ex.update(
            {
                "institution": "Example University",
                "studyType": "BSc",
                "area": "Computer Science",
                "score": "3.8",
            }
        )
    if section == "skills":
        ex.update(
            {
                "name": "Python",
                "level": "Advanced",
                "rating": 4.5,
                "keywords": ["typing", "asyncio"],
            }
        )
    if section == "languages":
        ex.update({"language": "Spanish", "fluency": "Basic", "level": 2})
    if section == "interests":
        ex.update({"name": "Climbing", "keywords": ["bouldering"]})
    if section == "awards":
        if "title" in fields:
            ex["title"] = "Example Award"
        if "awarder" in fields:
            ex["awarder"] = "Org"
        if "date" in fields:
            ex["date"] = "2024"
    if section == "certificates":
        if "name" in fields:
            ex["name"] = "Example Certificate"
        if "issuer" in fields:
            ex["issuer"] = "Issuer"
        if "date" in fields:
            ex["date"] = "2024"
    if section == "publications":
        if "name" in fields:
            ex["name"] = "Example Paper"
        if "publisher" in fields:
            ex["publisher"] = "Publisher"
        if "releaseDate" in fields:
            ex["releaseDate"] = "2024"
    if section == "volunteer":
        if "organization" in fields:
            ex["organization"] = "Nonprofit"
        if "location" in fields:
            ex["location"] = "Remote"
        if "summary" in fields:
            ex["summary"] = "Helped out."
    if section == "references":
        if "name" in fields:
            ex["name"] = "Jane Doe"
        if "position" in fields:
            ex["position"] = "Manager"
        if "contact" in fields:
            ex["contact"] = "jane@example.com"

    if "startDate" in fields and "endDate" in fields:
        ex.setdefault("startDate", "2024-01")
        ex.setdefault("endDate", None)
    if "url" in fields and "url" not in ex:
        ex["url"] = "https://example.com"
    if "description" in fields and "description" not in ex:
        ex["description"] = "Did work."
    if "summary" in fields and "summary" not in ex:
        ex["summary"] = "Did work."
    if "highlights" in fields and "highlights" not in ex:
        ex["highlights"] = ["Shipped feature X", "Improved Y"]
    return ex


def _build_section_schema(section: str) -> Dict[str, Any]:
    binding = _SECTION_BINDINGS[section]
    item_schema = binding.item_model.model_json_schema()
    fields = sorted((item_schema.get("properties") or {}).keys())

    date_fields = [
        field
        for field in ("startDate", "endDate", "date", "releaseDate")
        if field in fields
    ]
    paragraph_pairs = [
        (a.paragraph_key, a.listitems_key)
        for a in binding.spec.adapters
        if isinstance(a, ParagraphListAdapter)
    ]

    example_item = _example_item_for_section(section, fields)

    result: Dict[str, Any] = {
        "kind": "section",
        "target": section,
        "item": {
            "jsonSchema": item_schema,
            "fields": fields,
        },
        "constraints": {
            "create": {
                "itemsShape": (
                    "items must be a non-empty list of objects "
                    "(wrap single items in a list)"
                ),
                "id": "item.id must be omitted or null on create; ids are generated automatically",
                "hidden": "hidden is forced to false on create",
            },
            "update": {
                "id": "item.id is required",
                "noOp": "at least one field update or clear instruction is required",
                "clear": "clear supports {<id>: [fields]} or [{id, fields}]",
            },
            "dates": {
                "format": "string or null",
                "note": (
                    "Date fields ("
                    + ", ".join(date_fields)
                    + ") accept any string or null. Values are trimmed and returned as provided; "
                    "no format validation or hidden canonicalization is performed."
                    if date_fields
                    else "not applicable"
                ),
            },
            "richText": {
                "note": (
                    (
                        "Use "
                        + "; ".join(
                            f"{paragraph_key} (string) + {listitems_key} (list of strings)"
                            for paragraph_key, listitems_key in paragraph_pairs
                        )
                        + " for paragraph text + bullets. "
                        "When updating, provide both fields unless you intend to keep the other unchanged."
                    )
                    if paragraph_pairs
                    else "not applicable"
                )
            },
            "responses": {
                "defaultReturn": (
                    "return_mode defaults to 'delta' for create/update/delete; "
                    "responses always use the envelope shape described below."
                ),
                "returnModes": ["delta", "all", "none"],
                "envelope": {
                    "shape": {
                        "mode": "<all|delta|none>",
                        "items": ["<item>", "..."],
                        "delta": {
                            "created": ["<item>"],
                            "updated": ["<item>"],
                            "deleted": ["<id>"],
                        },
                        "ids": {
                            "created": ["<id>"],
                            "updated": ["<id>"],
                            "deleted": ["<id>"],
                        },
                    },
                    "notes": [
                        "Envelope is always returned; unused lists are empty.",
                        "items is populated only when mode='all'.",
                        "delta is populated only when mode='delta'.",
                        "ids always contains id lists for created/updated/deleted.",
                    ],
                },
            },
        },
        "operations": {
            "generic": {
                "list": {
                    "tool": "resume.section.list",
                    "args": {"resume_id": "<uuid>", "section": section},
                },
                "create": {
                    "tool": "resume.section.create",
                    "args": {
                        "resume_id": "<uuid>",
                        "section": section,
                        "items": [example_item],
                        "return_mode": "delta",
                    },
                },
                "update": {
                    "tool": "resume.section.update",
                    "args": {
                        "resume_id": "<uuid>",
                        "section": section,
                        "items": [
                            {
                                "id": "<item-id>",
                                **{k: v for k, v in example_item.items() if k != "id"},
                            }
                        ],
                        "clear": None,
                        "return_mode": "delta",
                    },
                },
                "delete": {
                    "tool": "resume.section.delete",
                    "args": {
                        "resume_id": "<uuid>",
                        "section": section,
                        "item_ids": ["<item-id>"],
                        "return_mode": "delta",
                    },
                },
            },
            "typed": None,
        },
        "examples": {
            "item": example_item,
            "createArgs": {
                "resume_id": "<uuid>",
                "section": section,
                "items": [example_item],
                "return_mode": "delta",
            },
        },
    }
    result["schemaVersion"] = _schema_version(result)
    return result


def register_resume_schema_tools(mcp: FastMCP) -> None:
    """Register schema introspection tools under the resume namespace."""

    @mcp.tool(
        name="resume.schema.get",
        description=(
            "Get MCP schema docs for basics or a section, including fields, examples, "
            "and usage constraints."
        ),
    )
    async def get_schema(
        ctx: Context,
        target: Any = Field(
            default=None,
            description=(
                "Schema target. Use 'basics' or a section name "
                f"({', '.join(sorted(_SECTION_BINDINGS.keys()))}). "
                "If omitted, returns an index of targets."
            ),
        ),
    ) -> Dict[str, Any]:
        async def _operation(_client: RxResumeClient) -> Any:
            if target is None:
                indexed = _list_targets()
                indexed["schemaVersion"] = _schema_version(indexed)
                return indexed

            resolved = _resolve_section_name(target)
            if resolved == "basics":
                return _build_basics_schema()
            if resolved not in _SECTION_BINDINGS:
                allowed = ", ".join(["basics", *sorted(_SECTION_BINDINGS.keys())])
                raise ValueError(
                    f"Unknown target: {target!r}. Expected one of: {allowed}."
                )
            return _build_section_schema(resolved)

        return await execute_rxresume_operation(
            operation_name="resume.schema.get",
            operation_func=_operation,
            ctx=ctx,
        )
