"""Resume tool modules grouped by MCP namespace."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .doc import register_resume_doc_tools
from .export import register_resume_export_tools


def register_resume_tools(mcp: FastMCP) -> None:
    """Register tools that operate on entire resumes."""
    register_resume_doc_tools(mcp)
    register_resume_export_tools(mcp)


__all__ = [
    "register_resume_tools",
]
