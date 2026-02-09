"""Register schema inspection tools."""

from __future__ import annotations

from typing import Any, Dict, Optional

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

from rxresume_mcp.client import RxResumeClient, _load_resume_schema

from .core import execute_rxresume_operation
from .schema import _resolve_schema_path, _summarize_schema_node


def register_schema_tools(mcp: FastMCP) -> None:
    """Register tools that expose schema fragments."""

    @mcp.tool(
        name="get_resume_schema_fragment",
        description="Fetch a summarized fragment of the RxResume JSON schema.",
    )
    async def get_resume_schema_fragment(
        ctx: Context,
        path: Optional[str] = Field(
            default=None,
            description=(
                "JSON pointer or dot path into the schema. "
                "Dot paths traverse properties/items (e.g., sections.experience "
                "or customSections.items). Example: /properties/basics or basics.website."
            ),
        ),
        depth: int = Field(
            default=1,
            ge=0,
            le=6,
            description="How deep to expand nested properties/items.",
        ),
        include_descriptions: bool = Field(
            default=False,
            description="If true, include description fields.",
        ),
        include_constraints: bool = Field(
            default=False,
            description="If true, include numeric/string/array constraints.",
        ),
        include_required: bool = Field(
            default=True,
            description="If true, include required field lists where present.",
        ),
        include_examples: bool = Field(
            default=False,
            description="If true, include example(s) when present.",
        ),
        resolve_refs: bool = Field(
            default=False,
            description="If true, resolve local $ref entries.",
        ),
        max_properties: int = Field(
            default=50,
            ge=1,
            le=500,
            description="Max properties to include per object node.",
        ),
    ) -> Dict[str, Any]:
        async def _operation(client: RxResumeClient) -> Any:
            schema = _load_resume_schema()
            node = _resolve_schema_path(schema, path, resolve_refs)

            summary = _summarize_schema_node(
                node,
                schema,
                depth=depth,
                include_descriptions=include_descriptions,
                include_constraints=include_constraints,
                include_required=include_required,
                include_examples=include_examples,
                max_properties=max_properties,
                resolve_refs=resolve_refs,
                seen_refs=set(),
            )

            return {
                "path": path or "#",
                "depth": depth,
                "summary": summary,
            }

        return await execute_rxresume_operation(
            operation_name="get resume schema fragment",
            operation_func=_operation,
            ctx=ctx,
        )
