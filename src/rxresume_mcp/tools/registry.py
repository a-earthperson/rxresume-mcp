"""Tool registration entrypoint."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .award import register_award_tools
from .basics import register_basics_tools
from .reference import register_reference_tools
from .certification import register_certification_tools
from .education import register_education_tools
from .experience import register_experience_tools
from .interest import register_interest_tools
from .language import register_language_tools
from .patch_tools import register_patch_tools
from .project import register_project_tools
from .publication import register_publication_tools
from .resume_tools import register_resume_tools
from .schema_tools import register_schema_tools
from .section_tools import register_section_tools
from .skill import register_skill_tools
from .volunteer import register_volunteer_tools


def register_tools(mcp: FastMCP) -> None:
    """Register RxResume MCP tool endpoints."""
    register_resume_tools(mcp)
    register_basics_tools(mcp)
    register_award_tools(mcp)
    register_certification_tools(mcp)
    register_experience_tools(mcp)
    register_education_tools(mcp)
    register_project_tools(mcp)
    register_publication_tools(mcp)
    register_skill_tools(mcp)
    register_language_tools(mcp)
    register_interest_tools(mcp)
    register_volunteer_tools(mcp)
    register_reference_tools(mcp)
    register_section_tools(mcp)
    register_patch_tools(mcp)
    register_schema_tools(mcp)
