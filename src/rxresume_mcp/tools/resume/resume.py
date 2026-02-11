"""Register resume document tools."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import uuid

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field
from slugify import slugify as _lib_slugify

from rxresume_mcp.client import RxResumeClient

from ..core import execute_rxresume_operation
from ..patching import _build_summary
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
    # JSON Resume: `work` (upstream: sections.experience)
    work: List[Any]
    education: List[Any]
    projects: List[Any]
    skills: List[Any]
    languages: List[Any]
    interests: List[Any]
    awards: List[Any]
    # JSON Resume: `certificates` (upstream: sections.certifications)
    certificates: List[Any]
    publications: List[Any]
    volunteer: List[Any]
    references: List[Any]


class ComposedResume(BaseModel):
    model_config = {"extra": "allow"}

    sections: ComposedSections


def _slugify(value: Any) -> str:
    """Return a URL-safe slug fragment."""
    if not isinstance(value, str):
        return "resume"
    stripped = value.strip()
    if not stripped:
        return "resume"
    # Keep behavior stable: produce a simple, URL-safe fragment with a fallback.
    slug = _lib_slugify(stripped, lowercase=True, separator="-", allow_unicode=False)
    return slug or "resume"


def _generate_resume_slug(name: str) -> str:
    """
    Generate a unique-ish slug for upstream API requirements.

    Upstream requires a `slug`, but MCP intentionally hides it to reduce surface
    friction (and to avoid callers needing global uniqueness coordination).
    """
    # Upstream appears to cap slugs around ~40 chars; keep a stable limit and
    # trim trailing separators after truncation.
    base = _slugify(name)[:40].strip("-") or "resume"
    # UUID suffix makes collisions vanishingly unlikely.
    suffix = uuid.uuid4().hex[:10]
    return f"{base}-{suffix}"


def _strip_slug(payload: Any) -> Any:
    """Remove `slug` keys from arbitrary JSON-ish payloads."""
    if isinstance(payload, dict):
        return {k: _strip_slug(v) for k, v in payload.items() if k != "slug"}
    if isinstance(payload, list):
        return [_strip_slug(item) for item in payload]
    return payload


_STRIP_RESUME_VIEW_FIELDS: frozenset[str] = frozenset({"slug", "isPublic", "isLocked"})


def _strip_resume_view_fields(payload: Any) -> Any:
    """
    Remove internal/undesired fields from all resume views.

    Apply this to both resume summaries (doc.list) and full objects (doc.get),
    so callers never see `isPublic` / `isLocked` (or `slug`) in any response.
    """

    if isinstance(payload, dict):
        return {
            k: _strip_resume_view_fields(v)
            for k, v in payload.items()
            if k not in _STRIP_RESUME_VIEW_FIELDS
        }
    if isinstance(payload, list):
        return [_strip_resume_view_fields(item) for item in payload]
    return payload


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

    source_key: str
    output_key: str
    spec: ItemSpec

    def apply_defaults(self, payload: Dict[str, Any]) -> None:
        return None

    def reshape(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        items = extract_section_items(payload, self.source_key)
        return {self.output_key: self.spec.reshape_items(items)}

    def build_update_ops(
        self, payload: Dict[str, Any], target: Any
    ) -> List[Dict[str, Any]]:
        return []


_SECTION_ITEM_SPEC_MAP = (
    # (output_key, source_key, spec)
    ("profiles", "profiles", PROFILE_SPEC),
    ("work", "experience", EXPERIENCE_SPEC),
    ("education", "education", EDUCATION_SPEC),
    ("projects", "projects", PROJECT_SPEC),
    ("skills", "skills", SKILL_SPEC),
    ("languages", "languages", LANGUAGE_SPEC),
    ("interests", "interests", INTEREST_SPEC),
    ("awards", "awards", AWARD_SPEC),
    ("certificates", "certifications", CERTIFICATION_SPEC),
    ("publications", "publications", PUBLICATION_SPEC),
    ("volunteer", "volunteer", VOLUNTEER_SPEC),
    ("references", "references", REFERENCE_SPEC),
)

SECTION_FIELDS: List[FieldSpec] = [
    FieldSpec(name="basics", field_type=Dict[str, Any], adapter=BasicsSectionAdapter()),
]
SECTION_FIELDS.extend(
    [
        FieldSpec(
            name=output_key,
            field_type=List[Any],
            adapter=SectionItemsAdapter(source_key=source_key, output_key=output_key, spec=spec),
        )
        for output_key, source_key, spec in _SECTION_ITEM_SPEC_MAP
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
        # MCP hides slug; upstream still requires it on create.
        "slug",
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


class ResumeMetaUpdateInput(BaseModel):
    """Document-level metadata update (intentionally limited)."""

    model_config = {"extra": "forbid"}

    name: Optional[str] = None
    tags: Optional[List[str]] = None


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
            result = await client.list_resumes(tags=tags, sort=sort)
            return _strip_resume_view_fields(_strip_slug(result))

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
            return _strip_resume_view_fields(_strip_slug(_reshape_resume(result)))

        return await execute_rxresume_operation(
            operation_name=f"resume.get: {resume_id}",
            operation_func=_operation,
            ctx=ctx,
        )

    @mcp.tool(name="resume.doc.update", description="Update resume name and/or tags")
    async def update_resume(
        ctx: Context,
        resume_id: Any = Field(default=None, description="Resume ID (UUID string)."),
        payload: Any = Field(
            default=None,
            description="Object with optional fields: {name?: string, tags?: string[]}.",
        ),
    ) -> Dict[str, Any]:
        async def _operation(client: RxResumeClient) -> Any:
            if not isinstance(resume_id, str) or not resume_id:
                raise ValueError("resume_id must be a non-empty string")
            if payload is None:
                raise ValueError("payload is required")
            if not isinstance(payload, dict):
                raise ValueError("payload must be an object")
            normalized = ResumeMetaUpdateInput.model_validate(payload)
            if normalized.name is None and normalized.tags is None:
                raise ValueError("payload must include at least one of: name, tags")

            updated = await client.update_resume(
                resume_id=resume_id,
                name=normalized.name,
                tags=normalized.tags,
            )
            # Keep responses compact: return only updated metadata if available.
            if isinstance(updated, dict):
                return _strip_resume_view_fields(
                    {
                        "resume_id": resume_id,
                        "name": updated.get("name"),
                        "tags": updated.get("tags"),
                    }
                )
            return {"resume_id": resume_id}

        return await execute_rxresume_operation(
            operation_name=f"resume.update: {resume_id}",
            operation_func=_operation,
            ctx=ctx,
            resume_id=resume_id if isinstance(resume_id, str) and resume_id else None,
        )

    @mcp.tool(name="resume.doc.create", description="Create a new resume")
    async def create_resume(
        ctx: Context,
        name: str = Field(description="Resume name"),
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
            # Generate a slug server-side; upstream requires it but MCP hides it.
            slug = _generate_resume_slug(name)
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
            # Upstream delete often returns an empty response body. Return a stable
            # patch-summary-shaped response so callers can handle deletes uniformly.
            await client.delete_resume(resume_id=resume_id)
            return _build_summary(
                resume_id,
                ops=[],
                created_ids=[],
                include_result=False,
                result=None,
                extra={"deleted": True},
            )

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
