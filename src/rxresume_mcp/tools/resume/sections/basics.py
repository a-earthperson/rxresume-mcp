"""Register tools for editing resume basics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List
import uuid

from mcp.server.fastmcp import FastMCP

from rxresume_mcp import patch_ops

from .profile import PROFILE_SPEC
from .field_adapters import ScalarFieldAdapter, WebsiteFieldAdapter
from .item_spec import FieldSpec, MappedPatchTarget, PatchTarget, build_object_model, build_spec
from .sections import _extract_section_data
from .section_item_tools import ensure_non_empty_string, extract_section_items, register_object_tools
from .tool_helpers import normalize_website_for_patch


@dataclass(frozen=True)
class BasicsProfilesAdapter:
    """Expose profiles via basics while storing them in sections.profiles.items."""

    response_key: str = "profiles"
    section: str = "profiles"

    def apply_defaults(self, payload: Dict[str, Any]) -> None:
        return None

    def reshape(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return {self.response_key: payload.get(self.response_key)}

    def build_update_ops(
        self, payload: Dict[str, Any], target: PatchTarget
    ) -> List[Dict[str, Any]]:
        if self.response_key not in payload:
            return []
        raw = payload.pop(self.response_key)
        if raw is None:
            raw = []
        if not isinstance(raw, list):
            raise ValueError("basics.profiles must be a list of objects (or null to clear)")

        items: List[Dict[str, Any]] = []
        for entry in raw:
            if not isinstance(entry, dict):
                raise ValueError("basics.profiles entries must be objects")
            entry_id = entry.get("id")
            if not isinstance(entry_id, str) or not entry_id:
                entry_id = str(uuid.uuid4())

            network = ensure_non_empty_string(entry.get("network"), fallback=" ")
            username = entry.get("username") if entry.get("username") is not None else ""
            if not isinstance(username, str):
                raise ValueError("basics.profiles[].username must be a string or null")

            website = normalize_website_for_patch(entry.get("url"))

            items.append(
                {
                    "id": entry_id,
                    "hidden": False,
                    "icon": "",
                    "network": network,
                    "username": username,
                    "website": website,
                }
            )

        # Replace the entire profiles section items array (JSON Merge Patch semantics).
        return [
            patch_ops.op_replace(patch_ops.path_section_items(self.section), items)
        ]


BASICS_FIELDS = [
    FieldSpec(
        name="name",
        field_type=str,
        adapter=ScalarFieldAdapter(response_key="name"),
    ),
    FieldSpec(
        name="label",
        field_type=str,
        adapter=ScalarFieldAdapter(response_key="label", server_key="headline"),
    ),
    FieldSpec(
        name="email",
        field_type=str,
        adapter=ScalarFieldAdapter(response_key="email"),
    ),
    FieldSpec(
        name="phone",
        field_type=str,
        adapter=ScalarFieldAdapter(response_key="phone"),
    ),
    FieldSpec(
        name="location",
        field_type=str,
        adapter=ScalarFieldAdapter(response_key="location"),
    ),
    FieldSpec(
        name="url",
        field_type=str,
        adapter=WebsiteFieldAdapter(response_key="url", server_key="website"),
    ),
    FieldSpec(
        name="summary",
        field_type=str,
        adapter=ScalarFieldAdapter(response_key="summary"),
    ),
    # Provide an alternate access path for profiles: basics.profiles (JSON Resume-compatible),
    # while upstream stores them in sections.profiles.items.
    FieldSpec(
        name="profiles",
        field_type=List[Dict[str, Any]],
        adapter=BasicsProfilesAdapter(),
    ),
]

BasicsInput = build_object_model(
    "BasicsInput", BASICS_FIELDS, populate_by_name=True, module=__name__
)
BASICS_SPEC = build_spec("basics", BASICS_FIELDS)
BASICS_TARGET = MappedPatchTarget(
    default_builder=patch_ops.path_basics_field,
    overrides={"summary": patch_ops.path_summary_field("content")},
)

BASICS_RESET = BasicsInput(
    name="",
    label="",
    email="",
    phone="",
    location="",
    url="",
    summary="",
)


def _build_basics_payload(resume: Dict[str, Any]) -> Any:
    basics = _extract_section_data(resume, "basics")["data"]
    if not isinstance(basics, dict):
        return basics
    payload = dict(basics)
    payload.pop("customFields", None)
    summary_data = _extract_section_data(resume, "summary")["data"]
    if isinstance(summary_data, dict):
        payload["summary"] = summary_data.get("content")
    # Mirror profiles under basics for convenience/JSON Resume alignment.
    try:
        items = extract_section_items(resume, "profiles", label="Profiles")
        reshaped = PROFILE_SPEC.reshape_items(items)
        # Keep empty resumes "all-null" per contract: [] -> null.
        payload["profiles"] = reshaped if reshaped else None
    except Exception:
        # If the section is missing/malformed, leave profiles absent.
        pass
    return payload


def register_basics_tools(mcp: FastMCP) -> None:
    """Register tools that edit basics fields."""
    register_object_tools(
        mcp,
        tool_prefix="resume.basics",
        name="basics",
        spec=BASICS_SPEC,
        target=BASICS_TARGET,
        model=BasicsInput,
        payload_type=BasicsInput,
        payload_description=(
            "Basics object with any subset of fields to patch. "
            "Omitted fields are unchanged; null/empty values clear fields. "
            "Prefer clear_fields to clear without sending nulls."
        ),
        build_payload=_build_basics_payload,
        extra_update_ops=lambda _payload: [
            patch_ops.op_replace(patch_ops.path_basics_field("customFields"), [])
        ],
        reset_payload=BASICS_RESET,
        include_delete=False,
    )
