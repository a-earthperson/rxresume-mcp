"""Tool registration entrypoint."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .resume import register_resume_tools

from .resume.sections.award import register_award_tools
from .resume.sections.basics import register_basics_tools
from .resume.sections.reference import register_reference_tools
from .resume.sections.certification import register_certification_tools
from .resume.sections.education import register_education_tools
from .resume.sections.experience import register_experience_tools
from .resume.sections.interest import register_interest_tools
from .resume.sections.language import register_language_tools
from .patch_tools import register_patch_tools
from .resume.sections.project import register_project_tools
from .resume.sections.profile import register_profile_tools
from .resume.sections.publication import register_publication_tools
from .schema_tools import register_schema_tools
from .section_tools import register_section_tools
from .resume.sections.skill import register_skill_tools
from .resume.sections.volunteer import register_volunteer_tools


def register_tools(mcp: FastMCP) -> None:
    """Register RxResume MCP tool endpoints."""
    register_resume_tools(mcp)

    register_basics_tools(mcp)
    register_award_tools(mcp)
    register_certification_tools(mcp)
    register_experience_tools(mcp)
    register_education_tools(mcp)
    register_project_tools(mcp)
    register_profile_tools(mcp)
    register_publication_tools(mcp)
    register_skill_tools(mcp)
    register_language_tools(mcp)
    register_interest_tools(mcp)
    register_volunteer_tools(mcp)
    register_reference_tools(mcp)
    register_section_tools(mcp)
    register_patch_tools(mcp)
    register_schema_tools(mcp)
