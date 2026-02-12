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

_PL_UL_RE = re.compile(r"<ul[^>]*>.*?</ul>", re.IGNORECASE | re.DOTALL)
_PL_LI_RE = re.compile(r"<li[^>]*>(.*?)</li>", re.IGNORECASE | re.DOTALL)
_PL_TAG_RE = re.compile(r"<[^>]+>")
_PERIOD_OPEN_MARKER = "Present"


def _strip_tags(value: str) -> str:
    return _PL_TAG_RE.sub("", value).strip()


def parse_paragraph_list_html(value: Any) -> tuple[Optional[str], Optional[List[str]]]:
    """
    Parse an HTML-ish string into (paragraph_text, list_items).

    Intended for the reversible representation produced by `format_paragraph_list_html`,
    but tolerant of legacy/plain-text values.
    """
    if not isinstance(value, str) or not value.strip():
        return None, None

    text = value.strip()
    items = [_strip_tags(item) for item in _PL_LI_RE.findall(text)]
    items = [item for item in items if item]

    paragraph_html = _PL_UL_RE.sub("", text).strip()
    paragraph = _strip_tags(paragraph_html)
    paragraph_value = paragraph or None
    items_value = items or None
    return paragraph_value, items_value


def format_paragraph_list_html(paragraph: Any, items: Any) -> str:
    """
    Format (paragraph, list_items) into a stable HTML-ish string:
      <p>{paragraph}</p><ul><li>{item}</li>...</ul>
    """
    paragraph_value = paragraph.strip() if isinstance(paragraph, str) else ""

    list_items: List[str] = []
    if items is None:
        list_items = []
    elif isinstance(items, list):
        for item in items:
            if not isinstance(item, str):
                raise ValueError("list items must be strings")
            stripped = item.strip()
            if stripped:
                list_items.append(stripped)
    else:
        raise ValueError("list items must be a list of strings or null")

    parts: List[str] = []
    if paragraph_value:
        # Preserve raw HTML if the caller provides it.
        if "<" in paragraph_value and ">" in paragraph_value:
            parts.append(paragraph_value)
        else:
            parts.append(f"<p>{paragraph_value}</p>")
    if list_items:
        li = "".join(f"<li>{item}</li>" for item in list_items)
        parts.append(f"<ul>{li}</ul>")
    return "".join(parts)


@dataclass(frozen=True)
class ParagraphListAdapter:
    """
    Adapter that exposes (paragraph_key, listitems_key) while storing `text_key`.

    - Input: accepts either/both paragraph_key and listitems_key.
    - Storage: writes a composed HTML-ish string to text_key.
    - Output: parses text_key into paragraph_key/listitems_key and removes text_key.

    Important update semantics:
    - If only one of (paragraph_key, listitems_key) is updated, tool handlers must
      fill the missing side from existing upstream `text_key` to avoid clobbering.
    """

    paragraph_key: str
    listitems_key: str
    text_key: str
    include_in_model: bool = False

    def apply_defaults(self, payload: Dict[str, Any]) -> None:
        paragraph_present = self.paragraph_key in payload
        items_present = self.listitems_key in payload

        paragraph = payload.pop(self.paragraph_key, None) if paragraph_present else None
        items = payload.pop(self.listitems_key, None) if items_present else None

        # If neither was provided, just ensure the upstream text field exists.
        if not paragraph_present and not items_present:
            payload.setdefault(self.text_key, "")
            return

        html = format_paragraph_list_html(paragraph or "", items)
        payload[self.text_key] = html

    def reshape(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        # Remove the backing field first to avoid key collisions downstream.
        raw = payload.pop(self.text_key, None)
        paragraph, items = parse_paragraph_list_html(raw)
        return {
            self.paragraph_key: paragraph,
            self.listitems_key: items,
        }

    def build_update_ops(
        self, payload: Dict[str, Any], target: PatchTarget
    ) -> List[Dict[str, Any]]:
        has_paragraph = self.paragraph_key in payload
        has_items = self.listitems_key in payload
        if not has_paragraph and not has_items:
            return []

        if has_paragraph ^ has_items:
            raise ValueError(
                f"{self.paragraph_key}/{self.listitems_key} must be updated together "
                "(the tool fills the untouched side from existing upstream text to prevent clobbering)."
            )

        paragraph = payload.pop(self.paragraph_key)
        items = payload.pop(self.listitems_key)

        paragraph_value = "" if paragraph is None else paragraph
        if not isinstance(paragraph_value, str):
            raise ValueError(f"{self.paragraph_key} must be a string or null")

        html = format_paragraph_list_html(paragraph_value, items)
        path = target.field_path(self.text_key)
        return [patch_ops.op_replace(path, html)]


def _normalize_date_string(value: Any) -> Optional[str]:
    """
    Normalize date-like values as plain strings.

    Accepts any non-empty string or null. Returns None for null-ish/empty.
    """
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        if stripped == "":
            return None
        return stripped
    raise ValueError("Dates must be strings or null")


def normalize_date_input(value: Any) -> str:
    """Normalize date input to a string; null/empty clears."""
    normalized = _normalize_date_string(value)
    return normalized or ""


def parse_period_bounds(period: Any) -> Tuple[Optional[str], Optional[str]]:
    """
    Best-effort parse upstream `period` strings into (startDate, endDate).

    Reversible for MCP-managed values produced by `format_period_bounds`.
    """
    if not isinstance(period, str):
        return None, None
    value = period.strip()
    if not value:
        return None, None

    if " to " not in value:
        start = _normalize_date_string(value)
        return start, None
    start_raw, end_raw = value.split(" to ", 1)
    if start_raw.strip() == _PERIOD_OPEN_MARKER:
        start_raw = None
    if end_raw.strip() == _PERIOD_OPEN_MARKER:
        end_raw = None
    start = _normalize_date_string(start_raw) if start_raw is not None else None
    end = _normalize_date_string(end_raw) if end_raw is not None else None
    return start, end

    return None, None


def format_period_bounds(start_date: Optional[str], end_date: Optional[str]) -> str:
    """
    Encode (startDate, endDate) into upstream `period` string.

    This is the *reversible* MCP-managed representation:
      - start+end   -> "<start> to <end>"
      - start only  -> "<start> to [open]"
      - end only    -> "[open] to <end>"
      - neither     -> ""
    """
    start_norm = _normalize_date_string(start_date)
    end_norm = _normalize_date_string(end_date)
    if start_norm is None and end_norm is None:
        return ""
    if start_norm is None:
        return f"{_PERIOD_OPEN_MARKER} to {end_norm}"
    if end_norm is None:
        return f"{start_norm} to {_PERIOD_OPEN_MARKER}"
    return f"{start_norm} to {end_norm}"


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
