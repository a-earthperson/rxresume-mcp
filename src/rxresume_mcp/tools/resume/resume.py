"""Register resume document tools."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from rxresume_mcp import patch_ops
from rxresume_mcp.client import RxResumeClient

from ..core import execute_rxresume_operation
from .sections.award import AWARD_SPEC
from .sections.basics import BASICS_SPEC, _build_basics_payload
from .sections.certification import CERTIFICATION_SPEC
from .sections.education import EDUCATION_SPEC
from .sections.experience import EXPERIENCE_SPEC
from .sections.field_adapters import ScalarFieldAdapter
from .sections.interest import INTEREST_SPEC
from .sections.item_spec import (
    FieldSpec,
    ItemSpec,
    MappedPatchTarget,
    build_object_model,
    build_spec,
)
from .sections.language import LANGUAGE_SPEC
from .sections.profile import PROFILE_SPEC
from .sections.project import PROJECT_SPEC
from .sections.publication import PUBLICATION_SPEC
from .sections.reference import REFERENCE_SPEC
from .sections.section_item_tools import coerce_object_input, extract_section_items
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


@dataclass(frozen=True)
class BasicsSectionAdapter:
    """Adapter for composing basics into resume sections."""

    def apply_defaults(self, payload: Dict[str, Any]) -> None:
        return None

    def reshape(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return {"basics": BASICS_SPEC.reshape(_build_basics_payload(payload))}

    def build_update_ops(
        self, payload: Dict[str, Any], target: Any
    ) -> List[Dict[str, Any]]:
        return []


@dataclass(frozen=True)
class SectionItemsAdapter:
    """Adapter for composing section items into resume sections."""

    key: str
    spec: ItemSpec

    def apply_defaults(self, payload: Dict[str, Any]) -> None:
        return None

    def reshape(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        items = extract_section_items(payload, self.key)
        return {self.key: self.spec.reshape_items(items)}

    def build_update_ops(
        self, payload: Dict[str, Any], target: Any
    ) -> List[Dict[str, Any]]:
        return []


_SECTION_ITEM_SPEC_MAP = (
    ("profiles", PROFILE_SPEC),
    ("experience", EXPERIENCE_SPEC),
    ("education", EDUCATION_SPEC),
    ("projects", PROJECT_SPEC),
    ("skills", SKILL_SPEC),
    ("languages", LANGUAGE_SPEC),
    ("interests", INTEREST_SPEC),
    ("awards", AWARD_SPEC),
    ("certifications", CERTIFICATION_SPEC),
    ("publications", PUBLICATION_SPEC),
    ("volunteer", VOLUNTEER_SPEC),
    ("references", REFERENCE_SPEC),
)

SECTION_FIELDS: List[FieldSpec] = [
    FieldSpec(name="basics", field_type=Dict[str, Any], adapter=BasicsSectionAdapter()),
]
SECTION_FIELDS.extend(
    [
        FieldSpec(
            name=section,
            field_type=List[Any],
            adapter=SectionItemsAdapter(section, spec),
        )
        for section, spec in _SECTION_ITEM_SPEC_MAP
    ]
)

SECTIONS_SPEC = build_spec("sections", SECTION_FIELDS)


def _compose_resume_sections(resume: Dict[str, Any]) -> Dict[str, Any]:
    return SECTIONS_SPEC.reshape(resume)


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


def _resume_root_path(field: str) -> str:
    return f"/{field}"


RESUME_UPDATE_FIELDS = [
    FieldSpec(
        name="name",
        field_type=str,
        adapter=ScalarFieldAdapter(
            input_key="name", server_key="name", response_key="name"
        ),
    ),
    FieldSpec(
        name="slug",
        field_type=str,
        adapter=ScalarFieldAdapter(
            input_key="slug", server_key="slug", response_key="slug"
        ),
    ),
    FieldSpec(
        name="tags",
        field_type=List[str],
        adapter=ScalarFieldAdapter(
            input_key="tags", server_key="tags", response_key="tags", default=[]
        ),
    ),
    FieldSpec(
        name="data",
        field_type=Dict[str, Any],
        adapter=ScalarFieldAdapter(
            input_key="data", server_key="data", response_key="data", default={}
        ),
    ),
]

ResumeUpdateInput = build_object_model(
    "ResumeUpdateInput", RESUME_UPDATE_FIELDS, populate_by_name=True, module=__name__
)
RESUME_UPDATE_SPEC = build_spec("resume", RESUME_UPDATE_FIELDS)
RESUME_UPDATE_TARGET = MappedPatchTarget(default_builder=_resume_root_path)


def register_resume_doc_tools(mcp: FastMCP) -> None:
    """Register tools that operate on resume documents."""

    @mcp.tool(
        name="resume.doc.list",
        description="List resumes, optionally filtering by tags and sort order",
    )
    async def list_resumes(
        ctx: Context,
        tags: List[str] = Field(
            description="Optional list of tags to filter by",
            default_factory=list,
        ),
        sort: Optional[str] = Field(
            description="Sort order: 'lastUpdatedAt' (desc), 'createdAt', or 'name'",
            default=None,
        ),
    ) -> Dict[str, Any]:
        async def _operation(client: RxResumeClient) -> Any:
            return await client.list_resumes(tags=tags, sort=sort)

        return await execute_rxresume_operation(
            operation_name="resume.list",
            operation_func=_operation,
            ctx=ctx,
        )

    @mcp.tool(name="resume.doc.get", description="Fetch a resume by ID")
    async def get_resume(
        ctx: Context,
        resume_id: str = Field(description="Resume ID"),
    ) -> Dict[str, Any]:
        async def _operation(client: RxResumeClient) -> Any:
            result = await client.get_resume(resume_id=resume_id)
            return _reshape_resume(result)

        return await execute_rxresume_operation(
            operation_name=f"resume.get: {resume_id}",
            operation_func=_operation,
            ctx=ctx,
        )

    @mcp.tool(name="resume.doc.create", description="Create a new resume")
    async def create_resume(
        ctx: Context,
        name: str = Field(description="Resume name"),
        slug: str = Field(description="Resume slug"),
        tags: List[str] = Field(
            description="Tags to assign to resume", default_factory=list
        ),
        with_sample_data: bool = Field(
            description="If true, include sample data on creation", default=False
        ),
    ) -> Dict[str, Any]:
        async def _operation(client: RxResumeClient) -> Any:
            resume_id = await client.create_resume(
                name=name,
                slug=slug,
                tags=tags,
                with_sample_data=with_sample_data,
            )
            resume = await client.get_resume(resume_id=resume_id)
            return {
                "resume_id": resume_id,
                "resume": _reshape_resume(resume),
            }

        return await execute_rxresume_operation(
            operation_name=f"resume.create: {name}",
            operation_func=_operation,
            ctx=ctx,
        )

    @mcp.tool(name="resume.doc.update", description="Update a resume by ID")
    async def update_resume(
        ctx: Context,
        resume_id: str = Field(description="Resume ID"),
        payload: Optional[Any] = Field(
            default=None,
            description=(
                "Resume update payload. Fields map to root resume properties; "
                "data replaces the resume data object."
            ),
        ),
    ) -> Dict[str, Any]:
        async def _operation(client: RxResumeClient) -> Any:
            if payload is None:
                raise ValueError("payload is required")
            normalized = coerce_object_input(payload, ResumeUpdateInput, label="resume")
            payload_dict = normalized.model_dump(exclude_none=True)
            ops = RESUME_UPDATE_SPEC.build_update_ops(
                payload_dict, RESUME_UPDATE_TARGET
            )
            validated_ops = patch_ops.validate_patch_ops(ops)
            result = await client.patch_resume(
                resume_id=resume_id, patch_ops=validated_ops
            )
            return _reshape_resume(result)

        return await execute_rxresume_operation(
            operation_name=f"resume.update: {resume_id}",
            operation_func=_operation,
            ctx=ctx,
        )

    @mcp.tool(name="resume.doc.delete", description="Delete a resume by ID")
    async def delete_resume(
        ctx: Context,
        resume_id: str = Field(description="Resume ID"),
    ) -> Dict[str, Any]:
        async def _operation(client: RxResumeClient) -> Any:
            result = await client.delete_resume(resume_id=resume_id)
            return _reshape_resume(result)

        return await execute_rxresume_operation(
            operation_name=f"resume.delete: {resume_id}",
            operation_func=_operation,
            ctx=ctx,
        )


def register_resume_export_tools(mcp: FastMCP) -> None:
    """Register tools that export resume outputs."""

    @mcp.tool(name="resume.export.pdf", description="Export resume as PDF")
    async def export_resume_pdf(
        ctx: Context,
        resume_id: str = Field(description="Resume ID"),
    ) -> Dict[str, Any]:
        async def _operation(client: RxResumeClient) -> Any:
            result = await client.export_resume_pdf(resume_id=resume_id)
            return _reshape_resume(result)

        return await execute_rxresume_operation(
            operation_name=f"resume.export_pdf: {resume_id}",
            operation_func=_operation,
            ctx=ctx,
        )

    @mcp.tool(
        name="resume.export.screenshot", description="Export resume screenshot"
    )
    async def export_resume_screenshot(
        ctx: Context,
        resume_id: str = Field(description="Resume ID"),
    ) -> Dict[str, Any]:
        async def _operation(client: RxResumeClient) -> Any:
            result = await client.export_resume_screenshot(resume_id=resume_id)
            return _reshape_resume(result)

        return await execute_rxresume_operation(
            operation_name=f"resume.export_screenshot: {resume_id}",
            operation_func=_operation,
            ctx=ctx,
        )
