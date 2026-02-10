"""Generic section CRUD tools.

These tools provide a small, uniform surface area over the existing per-section
spec/model wiring (field adapters, URL normalization, id handling, etc).

They are additive: existing `resume.section.<name>.*` tools remain available.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Type

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from rxresume_mcp import patch_ops
from rxresume_mcp.client import RxResumeClient

from ...core import execute_rxresume_operation
from .award import AWARD_SPEC, AwardItemInput
from .certification import CERTIFICATION_SPEC, CertificationItemInput
from .education import EDUCATION_SPEC, EducationItemInput
from .experience import EXPERIENCE_SPEC, ExperienceItemInput
from .interest import INTEREST_SPEC, InterestItemInput
from .item_spec import ItemSpec
from .language import LANGUAGE_SPEC, LanguageItemInput
from .profile import PROFILE_SPEC, ProfileItemInput
from .project import PROJECT_SPEC, ProjectItemInput
from .publication import PUBLICATION_SPEC, PublicationItemInput
from .reference import REFERENCE_SPEC, ReferenceItemInput
from .section_item_tools import (
    apply_section_item_patch,
    build_update_ops_with_spec,
    coerce_clear_instructions,
    extract_section_items,
    prepare_item_with_spec,
)
from .sections import _require_resume_object
from .skill import SKILL_SPEC, SkillItemInput
from .volunteer import VOLUNTEER_SPEC, VolunteerItemInput


@dataclass(frozen=True)
class _SectionBinding:
    section: str
    label: str
    spec: ItemSpec
    item_model: Type[BaseModel]


_SECTION_BINDINGS: Dict[str, _SectionBinding] = {
    "profiles": _SectionBinding(
        section="profiles",
        label="Profiles",
        spec=PROFILE_SPEC,
        item_model=ProfileItemInput,
    ),
    "experience": _SectionBinding(
        section="experience",
        label="Experience",
        spec=EXPERIENCE_SPEC,
        item_model=ExperienceItemInput,
    ),
    "education": _SectionBinding(
        section="education",
        label="Education",
        spec=EDUCATION_SPEC,
        item_model=EducationItemInput,
    ),
    "projects": _SectionBinding(
        section="projects",
        label="Projects",
        spec=PROJECT_SPEC,
        item_model=ProjectItemInput,
    ),
    "skills": _SectionBinding(
        section="skills",
        label="Skills",
        spec=SKILL_SPEC,
        item_model=SkillItemInput,
    ),
    "languages": _SectionBinding(
        section="languages",
        label="Languages",
        spec=LANGUAGE_SPEC,
        item_model=LanguageItemInput,
    ),
    "interests": _SectionBinding(
        section="interests",
        label="Interests",
        spec=INTEREST_SPEC,
        item_model=InterestItemInput,
    ),
    "awards": _SectionBinding(
        section="awards",
        label="Awards",
        spec=AWARD_SPEC,
        item_model=AwardItemInput,
    ),
    "certifications": _SectionBinding(
        section="certifications",
        label="Certifications",
        spec=CERTIFICATION_SPEC,
        item_model=CertificationItemInput,
    ),
    "publications": _SectionBinding(
        section="publications",
        label="Publications",
        spec=PUBLICATION_SPEC,
        item_model=PublicationItemInput,
    ),
    "volunteer": _SectionBinding(
        section="volunteer",
        label="Volunteer",
        spec=VOLUNTEER_SPEC,
        item_model=VolunteerItemInput,
    ),
    "references": _SectionBinding(
        section="references",
        label="References",
        spec=REFERENCE_SPEC,
        item_model=ReferenceItemInput,
    ),
}

_SECTION_ALIASES: Dict[str, str] = {
    # Tolerate singular forms (often inferred from existing per-section tool names).
    "profile": "profiles",
    "project": "projects",
    "skill": "skills",
    "language": "languages",
    "interest": "interests",
    "award": "awards",
    "certification": "certifications",
    "publication": "publications",
    "reference": "references",
}


def _resolve_section(section: Any) -> _SectionBinding:
    if not isinstance(section, str) or not section.strip():
        raise ValueError("section must be a non-empty string")
    raw = section.strip()
    normalized = raw.lower()
    canonical = _SECTION_ALIASES.get(normalized, normalized)
    binding = _SECTION_BINDINGS.get(canonical)
    if binding is None:
        allowed = ", ".join(patch_ops.SECTION_TYPES)
        raise ValueError(f"Unknown section: {raw}. Expected one of: {allowed}.")
    return binding


def _section_param_description() -> str:
    allowed = ", ".join(patch_ops.SECTION_TYPES)
    return f"Section type. Allowed: {allowed}."


def register_generic_section_tools(mcp: FastMCP) -> None:
    """Register the generic `resume.section.*` endpoints."""

    @mcp.tool(
        name="resume.section.list",
        description="List items for a resume section.",
    )
    async def _list(
        ctx: Context,
        resume_id: Any = Field(default=None, description="Resume ID (UUID string)."),
        section: Any = Field(default=None, description=_section_param_description()),
    ) -> Dict[str, Any]:
        async def _operation(client: RxResumeClient) -> Any:
            if not isinstance(resume_id, str) or not resume_id:
                raise ValueError("resume_id must be a non-empty string")
            binding = _resolve_section(section)
            resume = _require_resume_object(await client.get_resume(resume_id))
            items = extract_section_items(resume, binding.section, label=binding.label)
            return binding.spec.reshape_items(items)

        return await execute_rxresume_operation(
            operation_name=f"list section {section}: {resume_id}",
            operation_func=_operation,
            ctx=ctx,
            resume_id=resume_id if isinstance(resume_id, str) and resume_id else None,
        )

    @mcp.tool(
        name="resume.section.create",
        description="Add one or more items to a resume section.",
    )
    async def _create(
        ctx: Context,
        resume_id: Any = Field(default=None, description="Resume ID (UUID string)."),
        section: Any = Field(default=None, description=_section_param_description()),
        items: Any = Field(
            default=None,
            description="List of item objects to add (wrap single items in a list).",
        ),
    ) -> Dict[str, Any]:
        async def _operation(client: RxResumeClient) -> Any:
            if not isinstance(resume_id, str) or not resume_id:
                raise ValueError("resume_id must be a non-empty string")
            binding = _resolve_section(section)
            if items is None:
                raise ValueError("items is required")
            if not isinstance(items, list) or not items:
                raise ValueError("items must be a non-empty list of objects")
            created_ids: List[str] = []
            ops: List[Dict[str, Any]] = []
            for raw in items:
                if not isinstance(raw, dict):
                    raise ValueError("items must be a list of objects")
                model_item = binding.item_model.model_validate(raw)
                payload = prepare_item_with_spec(model_item, created_ids, binding.spec)
                ops.append(
                    patch_ops.op_add(
                        patch_ops.path_section_items_append(binding.section), payload
                    )
                )
            result = await apply_section_item_patch(
                client, resume_id, binding.section, ops, label=binding.label
            )
            return binding.spec.reshape_items(result)

        return await execute_rxresume_operation(
            operation_name=f"create section items {section}: {resume_id}",
            operation_func=_operation,
            ctx=ctx,
            resume_id=resume_id if isinstance(resume_id, str) and resume_id else None,
        )

    @mcp.tool(
        name="resume.section.update",
        description="Update one or more items in a resume section by id.",
    )
    async def _update(
        ctx: Context,
        resume_id: Any = Field(default=None, description="Resume ID (UUID string)."),
        section: Any = Field(default=None, description=_section_param_description()),
        items: Any = Field(
            default=None,
            description="List of item objects to update; each item must include id.",
        ),
        clear: Any = Field(
            default=None,
            description=(
                "Optional clear instructions. Shape: "
                "`[{id: <item_id>, fields: [<field>, ...]}, ...]` "
                "or `{<item_id>: [<field>, ...], ...}`."
            ),
        ),
    ) -> Dict[str, Any]:
        async def _operation(client: RxResumeClient) -> Any:
            if not isinstance(resume_id, str) or not resume_id:
                raise ValueError("resume_id must be a non-empty string")
            binding = _resolve_section(section)
            if items is None:
                raise ValueError("items is required")
            if not isinstance(items, list) or not items:
                raise ValueError("items must be a non-empty list of objects")
            ops: List[Dict[str, Any]] = []
            for raw in items:
                if not isinstance(raw, dict):
                    raise ValueError("items must be a list of objects")
                model_item = binding.item_model.model_validate(raw)
                ops.extend(build_update_ops_with_spec(model_item, binding.spec))
            for instruction in coerce_clear_instructions(clear):
                item_id = instruction["id"]
                fields = instruction["fields"]
                if not fields:
                    continue
                ops.extend(
                    binding.spec.build_update_ops(
                        item_id, {field: None for field in fields}
                    )
                )
            result = await apply_section_item_patch(
                client, resume_id, binding.section, ops, label=binding.label
            )
            return binding.spec.reshape_items(result)

        return await execute_rxresume_operation(
            operation_name=f"update section items {section}: {resume_id}",
            operation_func=_operation,
            ctx=ctx,
            resume_id=resume_id if isinstance(resume_id, str) and resume_id else None,
        )

    @mcp.tool(
        name="resume.section.delete",
        description="Delete one or more items from a resume section by id.",
    )
    async def _delete(
        ctx: Context,
        resume_id: Any = Field(default=None, description="Resume ID (UUID string)."),
        section: Any = Field(default=None, description=_section_param_description()),
        item_ids: Any = Field(
            default=None,
            description="List of item ids to remove (wrap single ids in a list).",
        ),
    ) -> Dict[str, Any]:
        async def _operation(client: RxResumeClient) -> Any:
            if not isinstance(resume_id, str) or not resume_id:
                raise ValueError("resume_id must be a non-empty string")
            binding = _resolve_section(section)
            if item_ids is None:
                raise ValueError("item_ids is required")
            if not isinstance(item_ids, list) or not item_ids:
                raise ValueError("item_ids must be a non-empty list of strings")
            for item_id in item_ids:
                if not isinstance(item_id, str) or not item_id:
                    raise ValueError("item_ids must contain non-empty strings only")
            ops: List[Dict[str, Any]] = [
                patch_ops.op_remove(
                    patch_ops.path_section_item(binding.section, item_id)
                )
                for item_id in item_ids
            ]
            result = await apply_section_item_patch(
                client, resume_id, binding.section, ops, label=binding.label
            )
            return binding.spec.reshape_items(result)

        return await execute_rxresume_operation(
            operation_name=f"delete section items {section}: {resume_id}",
            operation_func=_operation,
            ctx=ctx,
            resume_id=resume_id if isinstance(resume_id, str) and resume_id else None,
        )
