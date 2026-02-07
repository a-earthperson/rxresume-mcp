"""Tool registration entrypoint."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .docs_tools import register_docs_tools
from .patch_tools import register_patch_tools
from .resume_tools import register_resume_tools
from .schema_tools import register_schema_tools
from .section_tools import register_section_tools


def register_tools(mcp: FastMCP) -> None:
    """Register RxResume MCP tool endpoints."""
    register_resume_tools(mcp)
    register_section_tools(mcp)
    register_patch_tools(mcp)
    register_docs_tools(mcp)
    register_schema_tools(mcp)
