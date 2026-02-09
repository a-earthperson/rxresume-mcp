"""Shared helpers for resume tool responses."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from pydantic import BaseModel

from .sections.award import _reshape_award_items
from .sections.basics import _build_basics_response
from .sections.certification import _reshape_certification_items
from .sections.education import _reshape_education_items
from .sections.experience import _reshape_experience_items
from .sections.interest import _reshape_interest_items
from .sections.language import _reshape_language_items
from .sections.profile import _reshape_profile_items
from .sections.project import _reshape_project_items
from .sections.publication import _reshape_publication_items
from .sections.reference import _reshape_reference_items
from .sections.section_item_tools import extract_section_items
from .sections.sections import _extract_section_data, _require_resume_object
from .sections.skill import _reshape_skill_items
from .sections.volunteer import _reshape_volunteer_items


class ComposedSections(BaseModel):
    model_config = {"extra": "allow"}

    basics: Dict[str, Any]
    profiles: List[Any]
    experience: List[Any]
    education: List[Any]
    projects: List[Any]
    skills: List[Any]
    languages: List[Any]
    interests: List[Any]
    awards: List[Any]
    certifications: List[Any]
    publications: List[Any]
    volunteer: List[Any]
    references: List[Any]


class ComposedResume(BaseModel):
    model_config = {"extra": "allow"}

    sections: ComposedSections


_SECTION_ITEM_RESHAPERS: tuple[tuple[str, Optional[Callable[[Any], Any]]], ...] = (
    ("profiles", _reshape_profile_items),
    ("experience", _reshape_experience_items),
    ("education", _reshape_education_items),
    ("projects", _reshape_project_items),
    ("skills", _reshape_skill_items),
    ("languages", _reshape_language_items),
    ("interests", _reshape_interest_items),
    ("awards", _reshape_award_items),
    ("certifications", _reshape_certification_items),
    ("publications", _reshape_publication_items),
    ("volunteer", _reshape_volunteer_items),
    ("references", _reshape_reference_items),
)


def _compose_resume_sections(resume: Dict[str, Any]) -> Dict[str, Any]:
    basics_data = _extract_section_data(resume, "basics")["data"]
    summary_data = _extract_section_data(resume, "summary")["data"]
    summary_content = (
        summary_data.get("content") if isinstance(summary_data, dict) else None
    )
    basics = _build_basics_response(basics_data, summary_content=summary_content)
    sections: Dict[str, Any] = {"basics": basics}
    for section, reshaper in _SECTION_ITEM_RESHAPERS:
        items = extract_section_items(resume, section)
        sections[section] = reshaper(items) if reshaper else items
    return sections


def _compose_resume_payload(resume: Dict[str, Any]) -> Dict[str, Any]:
    excluded_fields = {
        "customSections",
        "data",
        "hasPassword",
        "isLocked",
        "isPublic",
        "metadata",
        "picture",
    }
    composed = {
        key: value for key, value in resume.items() if key not in excluded_fields
    }
    composed["sections"] = _compose_resume_sections(resume)
    return composed


def _reshape_resume(payload: Any) -> Any:
    if not isinstance(payload, dict) or "data" not in payload:
        return payload
    resume = _require_resume_object(payload)
    composed = _compose_resume_payload(resume)
    return ComposedResume.model_validate(composed).model_dump()
