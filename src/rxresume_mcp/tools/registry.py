"""Tool registration entrypoint."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .resume import register_resume_tools

from .resume.sections.generic_section_tools import register_generic_section_tools

from .resume.sections.basics import register_basics_tools


def register_tools(mcp: FastMCP) -> None:
    """Register RxResume MCP tool endpoints."""
    register_resume_tools(mcp)

    # Additive generic section CRUD (does not replace per-section tools).
    register_generic_section_tools(mcp)
    register_basics_tools(mcp)
