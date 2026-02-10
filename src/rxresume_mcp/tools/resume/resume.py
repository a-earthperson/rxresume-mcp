"""Register resume document tools."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import uuid

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from rxresume_mcp.client import RxResumeClient

from ..core import execute_rxresume_operation
from .sections.award import AWARD_SPEC
from .sections.basics import (
    BASICS_SPEC,
    BASICS_TARGET,
    BasicsInput,
    _build_basics_payload,
)
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
from .sections.section_item_tools import extract_section_items
from .sections.sections import _require_resume_object
from .sections.skill import SKILL_SPEC
from .sections.volunteer import VOLUNTEER_SPEC
from rxresume_mcp import patch_ops


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


def _coerce_created_resume_id(create_result: Any) -> str:
    """Normalize create response into a resume id string."""
    if isinstance(create_result, str) and create_result:
        return create_result
    if isinstance(create_result, dict):
        # Most common shapes first.
        direct_resume_id = create_result.get("resume_id")
        if isinstance(direct_resume_id, str) and direct_resume_id:
            return direct_resume_id

        direct_id = create_result.get("id")
        if isinstance(direct_id, str) and direct_id:
            return direct_id

        # Some APIs return nested envelopes like:
        # {"result": {"status": "...", "response": {"id": "..."}}}
        # {"status": "...", "data": {"id": "..."}}
        for key in ("response", "result", "data", "resume", "payload"):
            if key in create_result:
                nested = create_result.get(key)
                try:
                    return _coerce_created_resume_id(nested)
                except ValueError:
                    continue

        # As a last resort, scan shallow values for UUID-like strings.
        for value in create_result.values():
            if isinstance(value, str) and value:
                try:
                    uuid.UUID(value)
                    return value
                except ValueError:
                    continue

    raise ValueError(
        "Unable to extract resume_id from create response. "
        "Expected a non-empty string or object containing id/resume_id. "
        f"Received: {create_result!r}"
    )


RESUME_UPDATE_FIELDS = [
    FieldSpec(
        name="name",
        field_type=str,
        adapter=ScalarFieldAdapter(response_key="name"),
    ),
    FieldSpec(
        name="slug",
        field_type=str,
        adapter=ScalarFieldAdapter(response_key="slug"),
    ),
    FieldSpec(
        name="tags",
        field_type=List[str],
        adapter=ScalarFieldAdapter(
            response_key="tags", response_default=[], server_default=[]
        ),
    ),
    FieldSpec(
        name="data",
        field_type=Dict[str, Any],
        adapter=ScalarFieldAdapter(
            response_key="data", response_default={}, server_default={}
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
        basics: Optional[Dict[str, Any]] = Field(
            default=None,
            description=(
                "Optional basics object to apply immediately after creation. "
                "Uses canonical MCP basics fields: name, label, email, phone, location, url, summary."
            ),
        ),
    ) -> Dict[str, Any]:
        async def _operation(client: RxResumeClient) -> Any:
            created = await client.create_resume(
                name=name,
                slug=slug,
                tags=tags,
            )
            resume_id = _coerce_created_resume_id(created)
            if basics is None:
                return {"resume_id": resume_id}

            if not isinstance(basics, dict):
                raise ValueError("basics must be an object when provided")
            if not basics:
                return {"resume_id": resume_id}

            normalized = BasicsInput.model_validate(basics)
            payload_dict = normalized.model_dump(exclude_unset=True)
            ops = BASICS_SPEC.build_update_ops(payload_dict, BASICS_TARGET)
            # Keep internal customFields stable (canonical schema does not surface it).
            ops.append(
                patch_ops.op_replace(patch_ops.path_basics_field("customFields"), [])
            )
            validated_ops = patch_ops.validate_patch_ops(ops)
            patched = await client.patch_resume(resume_id, patch_ops=validated_ops)
            resume = _require_resume_object(patched)
            basics_payload = BASICS_SPEC.reshape(_build_basics_payload(resume))
            return {"resume_id": resume_id, "basics": basics_payload}

        return await execute_rxresume_operation(
            operation_name=f"resume.create: {name}",
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

    @mcp.tool(name="resume.export.screenshot", description="Export resume screenshot")
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
