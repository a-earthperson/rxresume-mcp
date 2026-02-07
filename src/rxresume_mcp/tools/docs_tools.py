"""Register documentation tools."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

from rxresume_mcp.rxresume_client import RxResumeClient

from .core import execute_rxresume_operation
from .docs import _doc_registry, _hash_content


def register_docs_tools(mcp: FastMCP) -> None:
    """Register tools that expose RxResume docs to MCP clients."""

    @mcp.tool(
        name="get_rxresume_docs",
        description="Fetch RxResume MCP documentation for tool-only clients.",
    )
    async def get_rxresume_docs(
        ctx: Context,
        topics: Optional[List[str]] = Field(
            default=None,
            description=(
                "Doc ids to fetch. Available: tool-semantics, schema-summary, "
                "patch-ops, design-notes, resume-schema."
            ),
        ),
        include_content: bool = Field(
            default=False,
            description="If true, include doc content instead of index-only.",
        ),
        include_schema: bool = Field(
            default=False,
            description="If true, include full JSON schema when resume-schema is selected.",
        ),
        max_chars: Optional[int] = Field(
            default=None,
            description="If set, truncate text content to this many characters.",
        ),
    ) -> Dict[str, Any]:
        async def _operation(client: RxResumeClient) -> Any:
            registry = _doc_registry()
            requested = topics or list(registry.keys())
            docs: List[Dict[str, Any]] = []

            for doc_id in requested:
                entry = registry.get(doc_id)
                if not entry:
                    raise ValueError(f"Unknown doc id: {doc_id}")
                content = entry["content"]
                sha256, size_chars = _hash_content(content)
                doc_info: Dict[str, Any] = {
                    "id": doc_id,
                    "title": entry["title"],
                    "mime_type": entry["mime_type"],
                    "size_chars": size_chars,
                    "sha256": sha256,
                }

                if include_content:
                    if doc_id == "resume-schema" and not include_schema:
                        doc_info["content"] = None
                        doc_info["note"] = "Set include_schema=true to return full JSON schema."
                    elif isinstance(content, str):
                        if max_chars is not None and len(content) > max_chars:
                            doc_info["content"] = content[:max_chars]
                            doc_info["truncated"] = True
                        else:
                            doc_info["content"] = content
                    else:
                        doc_info["content"] = content

                docs.append(doc_info)

            return {"docs": docs}

        return await execute_rxresume_operation(
            operation_name="get rxresume docs",
            operation_func=_operation,
            ctx=ctx,
        )
