"""Field adapters for consistent section item handling."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Callable, Dict, List, Optional, Tuple

from rxresume_mcp import patch_ops

from .item_spec import PatchTarget
from .tool_helpers import (
    WebsiteInputLike,
    normalize_website_for_patch,
    normalize_website_payload,
)

_ISO8601_LOOSE_RE = re.compile(
    r"^([1-2][0-9]{3}-[0-1][0-9]-[0-3][0-9]|[1-2][0-9]{3}-[0-1][0-9]|[1-2][0-9]{3})$"
)


def _normalize_iso8601_loose(value: Any) -> Optional[str]:
    """
    Normalize ISO8601-like date strings used by JSON Resume schema.

    Accepts YYYY, YYYY-MM, YYYY-MM-DD.
    Returns None for null-ish/empty.
    """
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        if stripped == "":
            return None
        if not _ISO8601_LOOSE_RE.match(stripped):
            raise ValueError(
                "Dates must be ISO8601-like strings: YYYY, YYYY-MM, or YYYY-MM-DD"
            )
        return stripped
    raise ValueError("Dates must be strings or null")


def parse_period_bounds(period: Any) -> Tuple[Optional[str], Optional[str]]:
    """
    Best-effort parse upstream `period` strings into (startDate, endDate).

    Reversible for MCP-managed values produced by `format_period_bounds`, and
    tolerant for legacy free-form values when possible.
    """
    if not isinstance(period, str):
        return None, None
    value = period.strip()
    if not value:
        return None, None

    # Canonical MCP-managed form: "<iso> - <iso>" or "<iso> - Present"
    # (Spaces around the dash are required so we don't conflict with date hyphens.)
    m = re.match(
        r"^\s*(?P<start>[0-9]{4}(?:-[0-9]{2})?(?:-[0-9]{2})?)\s+-\s+(?P<end>[0-9]{4}(?:-[0-9]{2})?(?:-[0-9]{2})?|Present|Now|Current)\s*$",
        value,
        flags=re.IGNORECASE,
    )
    if m:
        start = m.group("start")
        end_raw = m.group("end")
        end = None
        if end_raw and end_raw.lower() not in ("present", "now", "current"):
            end = end_raw
        # Validate extracted values to keep downstream consistent.
        try:
            start_norm = _normalize_iso8601_loose(start)
            end_norm = _normalize_iso8601_loose(end) if end is not None else None
        except ValueError:
            return None, None
        return start_norm, end_norm

    # "Until <iso>" is used when only an end date exists.
    m = re.match(
        r"^\s*(?:until|till|through)\s+(?P<end>[0-9]{4}(?:-[0-9]{2})?(?:-[0-9]{2})?)\s*$",
        value,
        flags=re.IGNORECASE,
    )
    if m:
        end = m.group("end")
        try:
            end_norm = _normalize_iso8601_loose(end)
        except ValueError:
            return None, None
        return None, end_norm

    # Single ISO-ish token.
    if _ISO8601_LOOSE_RE.match(value):
        try:
            return _normalize_iso8601_loose(value), None
        except ValueError:
            return None, None

    return None, None


def format_period_bounds(start_date: Optional[str], end_date: Optional[str]) -> str:
    """
    Encode (startDate, endDate) into upstream `period` string.

    This is the *reversible* MCP-managed representation:
      - start+end   -> "<start> - <end>"
      - start only  -> "<start> - Present"
      - end only    -> "Until <end>"
      - neither     -> ""
    """
    start_norm = _normalize_iso8601_loose(start_date)
    end_norm = _normalize_iso8601_loose(end_date)
    if start_norm and end_norm:
        return f"{start_norm} - {end_norm}"
    if start_norm and not end_norm:
        return f"{start_norm} - Present"
    if end_norm and not start_norm:
        return f"Until {end_norm}"
    return ""


@dataclass(frozen=True)
class NoopFieldAdapter:
    """
    Adapter used only to expose fields in Pydantic models.

    Real storage/reshaping for those fields is handled by a different adapter
    (e.g. `PeriodRangeAdapter`) that runs later in the spec adapter chain.
    """

    def apply_defaults(self, payload: Dict[str, Any]) -> None:
        return None

    def reshape(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return {}

    def build_update_ops(
        self, payload: Dict[str, Any], target: PatchTarget
    ) -> List[Dict[str, Any]]:
        return []


@dataclass(frozen=True)
class PeriodRangeAdapter:
    """
    Adapter that exposes JSON Resume `startDate`/`endDate` while storing upstream `period`.

    Important: `build_update_ops` requires BOTH keys to be present in the payload
    whenever either is updated. Tool handlers fill the missing side from existing
    upstream data to avoid corrupting partial updates.
    """

    server_key: str = "period"
    start_key: str = "startDate"
    end_key: str = "endDate"
    include_in_model: bool = False

    def apply_defaults(self, payload: Dict[str, Any]) -> None:
        start = payload.pop(self.start_key, None) if self.start_key in payload else None
        end = payload.pop(self.end_key, None) if self.end_key in payload else None
        # Always ensure upstream field exists (upstream schemas require it).
        payload.setdefault(self.server_key, format_period_bounds(start, end))

    def reshape(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        start, end = parse_period_bounds(payload.get(self.server_key))
        return {self.start_key: start, self.end_key: end}

    def build_update_ops(
        self, payload: Dict[str, Any], target: PatchTarget
    ) -> List[Dict[str, Any]]:
        has_start = self.start_key in payload
        has_end = self.end_key in payload
        if not has_start and not has_end:
            return []
        if not has_start or not has_end:
            raise ValueError(
                "startDate/endDate must be updated together (the tool fills the untouched side "
                "from existing period to prevent corruption)."
            )
        start_raw = payload.pop(self.start_key)
        end_raw = payload.pop(self.end_key)
        period_value = format_period_bounds(start_raw, end_raw)
        path = target.field_path(self.server_key)
        return [patch_ops.op_replace(path, period_value)]


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
