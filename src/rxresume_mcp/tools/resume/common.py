"""Shared helpers for resume tool responses."""

from __future__ import annotations

from typing import Any, Dict, List

from pydantic import BaseModel

from .sections.award import AWARD_SPEC
from .sections.basics import BASICS_SPEC
from .sections.certification import CERTIFICATION_SPEC
from .sections.education import EDUCATION_SPEC
from .sections.experience import EXPERIENCE_SPEC
from .sections.interest import INTEREST_SPEC
from .sections.language import LANGUAGE_SPEC
from .sections.profile import PROFILE_SPEC
from .sections.project import PROJECT_SPEC
from .sections.publication import PUBLICATION_SPEC
from .sections.reference import REFERENCE_SPEC
from .sections.section_item_tools import extract_section_items
from .sections.sections import _require_resume_object
from .sections.skill import SKILL_SPEC
from .sections.volunteer import VOLUNTEER_SPEC


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


_SECTION_ITEM_SPECS = (
    PROFILE_SPEC,
    EXPERIENCE_SPEC,
    EDUCATION_SPEC,
    PROJECT_SPEC,
    SKILL_SPEC,
    LANGUAGE_SPEC,
    INTEREST_SPEC,
    AWARD_SPEC,
    CERTIFICATION_SPEC,
    PUBLICATION_SPEC,
    VOLUNTEER_SPEC,
    REFERENCE_SPEC,
)


def _compose_resume_sections(resume: Dict[str, Any]) -> Dict[str, Any]:
    basics = BASICS_SPEC.reshape_resume(resume)
    sections: Dict[str, Any] = {"basics": basics}
    for spec in _SECTION_ITEM_SPECS:
        items = extract_section_items(resume, spec.key)
        sections[spec.key] = spec.reshape_items(items)
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
