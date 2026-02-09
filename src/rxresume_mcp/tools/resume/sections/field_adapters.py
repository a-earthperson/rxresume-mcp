"""Field adapters for consistent section item handling."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from rxresume_mcp import patch_ops

from .section_item_tools import (
    build_summary_highlights_description,
    split_summary_highlights_description,
)
from .item_spec import PatchTarget
from .tool_helpers import (
    WebsiteInputLike,
    normalize_website_for_patch,
    normalize_website_payload,
)


@dataclass(frozen=True)
class WebsiteFieldAdapter:
    """Adapter for website/url fields across inputs, storage, and responses."""

    input_key: str = "url"
    response_key: str = "url"
    server_key: str = "website"
    def apply_defaults(self, payload: Dict[str, Any]) -> None:
        """Normalize website input and write to the server key."""
        value = payload.pop(self.input_key, None)
        payload[self.server_key] = normalize_website_payload(value)

    def reshape(self, payload: Dict[str, Any]) -> Dict[str, Dict[str, str]]:
        """Return a response-ready website payload."""
        value = payload.get(self.server_key) or normalize_website_payload(None)
        return {self.response_key: value}

    def build_update_ops(
        self, payload: Dict[str, Any], target: PatchTarget
    ) -> List[Dict[str, Any]]:
        """Build patch ops for website updates."""
        if self.input_key not in payload:
            return []
        website_payload = normalize_website_for_patch(payload.pop(self.input_key))
        base = target.field_path(self.server_key)
        return [
            patch_ops.op_replace(f"{base}/{key}", value)
            for key, value in website_payload.items()
        ]

    @staticmethod
    def normalize_input(
            value: Optional[WebsiteInputLike]
    ) -> Dict[str, str]:
        """Normalize a website input for direct patch usage."""
        return normalize_website_for_patch(value)


@dataclass(frozen=True)
class ScalarFieldAdapter:
    """Adapter for scalar fields across inputs, storage, and responses."""

    input_key: str
    response_key: str
    server_key: str
    default: Any = ""
    input_transform: Callable[[Any], Any] | None = None
    response_transform: Callable[[Any], Any] | None = None
    def apply_defaults(self, payload: Dict[str, Any]) -> None:
        """Normalize a scalar input and write to the server key."""
        if self.input_key in payload:
            value = payload.pop(self.input_key)
            if self.input_transform is not None:
                value = self.input_transform(value)
            payload[self.server_key] = value
            return
        payload.setdefault(self.server_key, self.default)

    def reshape(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Return a response-ready scalar payload."""
        value = payload.get(self.server_key, self.default)
        if value is None:
            value = self.default
        if self.response_transform is not None:
            value = self.response_transform(value)
        return {self.response_key: value}

    def build_update_ops(
        self, payload: Dict[str, Any], target: PatchTarget
    ) -> List[Dict[str, Any]]:
        """Build patch ops for scalar field updates."""
        if self.input_key not in payload:
            return []
        value = payload.pop(self.input_key)
        if self.input_transform is not None:
            value = self.input_transform(value)
        path = target.field_path(self.server_key)
        return [patch_ops.op_replace(path, value)]


@dataclass(frozen=True)
class SuppressedFieldAdapter:
    """Adapter for fields that should be hidden from MCP input/output."""

    server_key: str
    default: Any = ""
    include_in_model: bool = False
    include_in_response: bool = False

    def apply_defaults(self, payload: Dict[str, Any]) -> None:
        """Force a default value for hidden fields."""
        payload[self.server_key] = self.default

    def reshape(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Return no response payload for hidden fields."""
        return {}

    def build_update_ops(
        self, payload: Dict[str, Any], target: PatchTarget
    ) -> List[Dict[str, Any]]:
        """No update ops for hidden fields."""
        return []


@dataclass(frozen=True)
class SummaryHighlightsFieldAdapter:
    """Adapter for summary/highlights fields backed by description HTML."""

    summary_key: str = "summary"
    highlights_key: str = "highlights"
    response_summary_key: str = "summary"
    response_highlights_key: str = "highlights"
    server_key: str = "description"
    def apply_defaults(self, payload: Dict[str, Any]) -> None:
        """Normalize summary/highlights input into the description field."""
        summary_present = self.summary_key in payload
        highlights_present = self.highlights_key in payload
        if (
            not summary_present
            and not highlights_present
            and self.server_key in payload
        ):
            return
        summary = payload.pop(self.summary_key, None)
        highlights = payload.pop(self.highlights_key, None)
        payload[self.server_key] = build_summary_highlights_description(
            summary, highlights
        )

    def reshape(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Return response-ready summary and highlights fields."""
        summary, highlights = split_summary_highlights_description(
            payload.get(self.server_key)
        )
        return {
            self.response_summary_key: summary or "",
            self.response_highlights_key: highlights or [],
        }

    def build_update_ops(
        self, payload: Dict[str, Any], target: PatchTarget
    ) -> List[Dict[str, Any]]:
        """Build patch ops for description updates."""
        summary_present = self.summary_key in payload
        highlights_present = self.highlights_key in payload
        if not summary_present and not highlights_present:
            return []
        summary = payload.pop(self.summary_key, None) if summary_present else None
        highlights = (
            payload.pop(self.highlights_key, None) if highlights_present else None
        )
        description = build_summary_highlights_description(summary, highlights)
        path = target.field_path(self.server_key)
        return [patch_ops.op_replace(path, description)]