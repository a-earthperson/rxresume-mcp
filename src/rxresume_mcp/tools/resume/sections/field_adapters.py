"""Field adapters for consistent section item handling."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from rxresume_mcp import patch_ops

from .item_spec import PatchTarget
from .tool_helpers import (
    WebsiteInputLike,
    normalize_website_for_patch,
    normalize_website_payload,
)


@dataclass(frozen=True)
class WebsiteFieldAdapter:
    """Adapter for url fields across inputs, storage, and responses."""

    response_key: str = "url"
    server_key: str | None = None

    def apply_defaults(self, payload: Dict[str, Any]) -> None:
        """Normalize url input and write to the server key."""
        server_key = self.server_key or self.response_key
        if self.response_key in payload:
            value = payload.pop(self.response_key)
            payload[server_key] = normalize_website_payload(value)
            return
        payload.setdefault(server_key, normalize_website_payload(None))

    def reshape(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Return a response-ready url payload."""
        server_key = self.server_key or self.response_key
        value = payload.get(server_key)
        normalized = normalize_website_payload(value)
        if normalized["url"] is None or normalized["url"] == "":
            return {self.response_key: None}
        return {self.response_key: normalized["url"]}

    def build_update_ops(
        self, payload: Dict[str, Any], target: PatchTarget
    ) -> List[Dict[str, Any]]:
        """Build patch ops for url updates."""
        server_key = self.server_key or self.response_key
        if self.response_key not in payload:
            return []
        website_payload = normalize_website_for_patch(payload.pop(self.response_key))
        base = target.field_path(server_key)
        return [patch_ops.op_replace(f"{base}/url", website_payload["url"])]

    @staticmethod
    def normalize_input(value: Optional[WebsiteInputLike]) -> str:
        """Normalize a url input for direct patch usage."""
        return normalize_website_for_patch(value)["url"]


@dataclass(frozen=True)
class ScalarFieldAdapter:
    """Adapter for scalar fields across inputs, storage, and responses."""

    response_key: str
    server_key: str | None = None
    response_default: Any | None = None
    server_default: Any | None = ""
    input_transform: Callable[[Any], Any] | None = None
    response_transform: Callable[[Any], Any] | None = None

    def apply_defaults(self, payload: Dict[str, Any]) -> None:
        """Normalize a scalar input and write to the server key."""
        server_key = self.server_key or self.response_key
        if self.response_key in payload:
            value = payload.pop(self.response_key)
            if value is None:
                value = self.server_default
            if self.input_transform is not None:
                value = self.input_transform(value)
            payload[server_key] = value
            return
        payload.setdefault(server_key, self.server_default)

    def reshape(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Return a response-ready scalar payload."""
        server_key = self.server_key or self.response_key
        value = payload.get(server_key, self.server_default)
        if value is None or value == self.server_default:
            return {self.response_key: self.response_default}

        if self.response_transform is not None:
            value = self.response_transform(value)

        return {self.response_key: value}

    def build_update_ops(
        self, payload: Dict[str, Any], target: PatchTarget
    ) -> List[Dict[str, Any]]:
        """Build patch ops for scalar field updates."""
        server_key = self.server_key or self.response_key
        if self.response_key not in payload:
            return []
        value = payload.pop(self.response_key)
        if value is None:
            value = self.server_default
        if self.input_transform is not None:
            value = self.input_transform(value)
        path = target.field_path(server_key)
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
