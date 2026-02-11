"""
Async client for interacting with Reactive Resume API.
"""

from __future__ import annotations

import json
import logging
import uuid
from copy import deepcopy
from functools import lru_cache
from importlib import resources as importlib_resources
from typing import Any, Dict, Iterable, List, Optional, Tuple

from deepmerge import Merger
import httpx
from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, ValidationError
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from . import DEFAULT_USER_AGENT

logger = logging.getLogger(__name__)

_DEEP_MERGER: Merger = Merger(
    # Match prior behavior: merge dicts recursively, override everything else.
    [(dict, ["merge"])],
    ["override"],
    ["override"],
)

_RESUME_SCHEMA_CANDIDATES: tuple[str, ...] = (
    # Preferred: draft 2020-12 schema that matches Draft202012Validator.
    "upstream-schema.json",
    # Backward-compat fallback if a renamed schema ever ships.
    "resume-schema.json",
)

_IDEMPOTENT_METHODS: frozenset[str] = frozenset({"GET", "HEAD", "OPTIONS"})
_RETRYABLE_STATUS_CODES: frozenset[int] = frozenset({408, 429, 500, 502, 503, 504})


class _RetryableStatusError(RuntimeError):
    """Internal sentinel exception used for retrying HTTP responses."""

    def __init__(self, status_code: int):
        super().__init__(f"Retryable HTTP status: {status_code}")
        self.status_code = status_code


def _deep_merge(base: Any, patch: Any) -> Any:
    """
    Deep-merge dict patches into dict bases.

    Semantics are intentionally conservative:
    - dict + dict: recursive merge
    - anything else: patch wins (override)
    """
    if not isinstance(base, dict) or not isinstance(patch, dict):
        return patch
    merged = deepcopy(base)
    return _DEEP_MERGER.merge(merged, patch)


@lru_cache(maxsize=1)
def _load_resume_schema() -> Dict[str, Any]:
    resources_dir = importlib_resources.files("rxresume_mcp").joinpath("resources")
    last_error: Exception | None = None
    for filename in _RESUME_SCHEMA_CANDIDATES:
        try:
            raw = resources_dir.joinpath(filename).read_text(encoding="utf-8")
        except FileNotFoundError as exc:
            last_error = exc
            continue
        return json.loads(raw)
    searched = ", ".join(_RESUME_SCHEMA_CANDIDATES)
    raise FileNotFoundError(
        f"Resume schema file not found in packaged resources (searched: {searched})."
    ) from last_error


def _make_basics_fields_optional(schema: Dict[str, Any]) -> Dict[str, Any]:
    """Return a schema copy with basics.* fields marked optional."""
    if not isinstance(schema, dict):
        return schema
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        return dict(schema)
    basics = properties.get("basics")
    if not isinstance(basics, dict):
        return dict(schema)
    relaxed = dict(schema)
    relaxed_properties = dict(properties)
    relaxed_basics = dict(basics)
    relaxed_basics.pop("required", None)
    relaxed_properties["basics"] = relaxed_basics
    relaxed["properties"] = relaxed_properties
    return relaxed


@lru_cache(maxsize=2)
def _resume_schema_validator(
    relax_basics_required: bool = False,
) -> Draft202012Validator:
    schema = _load_resume_schema()
    if relax_basics_required:
        schema = _make_basics_fields_optional(schema)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


COMMON_DATA_FIELD_HINTS: Dict[str, str] = {
    "name": "data.basics.name (resume title is resume.update.name)",
    "job_title": "data.basics.headline",
    "headline": "data.basics.headline",
    "email": "data.basics.email",
    "phone": "data.basics.phone",
    "location": "data.basics.location",
    "website": "data.basics.website.url",
    "description": "data.summary.content (HTML string)",
    "notes": "data.metadata.notes (HTML string)",
    "social_media": "data.sections.profiles.items or data.basics.customFields",
    "profiles": "data.sections.profiles.items",
    "employment": "data.sections.experience.items",
    "experience": "data.sections.experience.items",
    "education": "data.sections.education.items",
    "projects": "data.sections.projects.items",
    "skills": "data.sections.skills.items",
    "languages": "data.sections.languages.items",
    "interests": "data.sections.interests.items",
    "awards": "data.sections.awards.items",
    "certifications": "data.sections.certifications.items",
    "publications": "data.sections.publications.items",
    "volunteer": "data.sections.volunteer.items",
    "references": "data.sections.references.items",
}


def _extract_root_additional_keys(
    errors: List[ValidationError],
) -> List[str]:
    extras: List[str] = []
    for err in errors:
        if err.validator != "additionalProperties":
            continue
        if err.path:
            continue
        additional = err.params.get("additionalProperties")
        if isinstance(additional, list):
            extras.extend(str(value) for value in additional)
        elif isinstance(additional, str):
            extras.append(additional)
    return sorted(set(extras))


def _format_additional_properties_hint(
    schema: Dict[str, Any] | None, extra_keys: List[str]
) -> str | None:
    if not schema or not extra_keys:
        return None
    allowed = sorted(schema.get("properties", {}).keys())
    hints: List[str] = []
    if allowed:
        hints.append("allowed top-level keys: " + ", ".join(allowed))
    mapped = [
        f"{key} -> {COMMON_DATA_FIELD_HINTS[key]}"
        for key in extra_keys
        if key in COMMON_DATA_FIELD_HINTS
    ]
    if mapped:
        hints.append("common mappings: " + "; ".join(mapped))
    if not hints:
        return None
    return "hint: " + " | ".join(hints)


def _format_validation_errors(
    errors: List[ValidationError],
    max_errors: int = 5,
    schema: Dict[str, Any] | None = None,
) -> str:
    lines: List[str] = []
    extra_keys = _extract_root_additional_keys(errors)
    for err in errors[:max_errors]:
        path = ".".join(str(part) for part in err.path) or "<root>"
        lines.append(f"{path}: {err.message}")
    if len(errors) > max_errors:
        lines.append(f"... ({len(errors) - max_errors} more)")
    hint = _format_additional_properties_hint(schema, extra_keys)
    if hint:
        lines.append(hint)
    return "; ".join(lines)


def _validate_resume_data(data: Dict[str, Any]) -> None:
    try:
        schema = _load_resume_schema()
        schema = _make_basics_fields_optional(schema)
        validator = _resume_schema_validator(relax_basics_required=True)
    except (FileNotFoundError, json.JSONDecodeError, SchemaError) as exc:
        raise ValueError(f"Resume schema unavailable or invalid: {exc}") from exc

    errors = sorted(validator.iter_errors(data), key=lambda err: list(err.path))
    if errors:
        details = _format_validation_errors(errors, schema=schema)
        raise ValueError(f"Resume data failed schema validation: {details}")


def _validate_resume_id(resume_id: str) -> None:
    if not isinstance(resume_id, str) or not resume_id:
        raise ValueError("resume_id must be a non-empty string")
    try:
        uuid.UUID(resume_id)
    except ValueError as exc:
        raise ValueError(
            f"Invalid resume_id '{resume_id}'. Expected UUID format."
        ) from exc


class RxResumeAPIError(RuntimeError):
    """Raised when the Reactive Resume API returns an error response."""

    def __init__(self, status_code: int, message: str, payload: Any | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload

    def __str__(self) -> str:
        if self.payload is None:
            return f"HTTP {self.status_code}: {super().__str__()}"
        return f"HTTP {self.status_code}: {self.payload!r}"


class RxResumeClient:
    """
    Client for interacting with Reactive Resume API.
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        timeout: int = 30,
        user_agent: str = DEFAULT_USER_AGENT,
    ):
        """
        Initialize Reactive Resume API client.

        Args:
            base_url (str): Base API URL (e.g. https://host/api/openapi).
            api_key (str): API key for x-api-key header.
        """
        self.base_url = base_url
        self.api_key = api_key
        self.client = httpx.AsyncClient(
            base_url=base_url,
            timeout=timeout,
            headers={
                "x-api-key": api_key,
                "User-Agent": user_agent,
            },
        )
        logger.info("Initialized Reactive Resume API client: %s", base_url)

    async def close(self) -> None:
        await self.client.aclose()

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Iterable[Tuple[str, str]]] = None,
        json_body: Optional[Any] = None,
        accept: str = "application/json",
        content_type: Optional[str] = None,
    ) -> Any:
        method_upper = method.upper()
        logger.debug("Requesting %s %s", method_upper, path)
        headers = {"Accept": accept}
        if content_type:
            headers["Content-Type"] = content_type

        async def _send_once() -> httpx.Response:
            return await self.client.request(
                method_upper,
                path,
                params=params,
                json=json_body,
                headers=headers,
            )

        response: httpx.Response
        if method_upper in _IDEMPOTENT_METHODS:
            # Conservative retries: only idempotent methods, only transient codes.
            async for attempt in AsyncRetrying(
                retry=retry_if_exception_type(httpx.RequestError)
                | retry_if_exception_type(_RetryableStatusError),
                wait=wait_exponential(multiplier=0.2, min=0.2, max=2.0),
                stop=stop_after_attempt(3),
                reraise=True,
            ):
                with attempt:
                    response = await _send_once()
                    if response.status_code in _RETRYABLE_STATUS_CODES:
                        # Ensure the connection is released before retrying.
                        response.close()
                        raise _RetryableStatusError(response.status_code)
                    break
        else:
            response = await _send_once()
        content_type = response.headers.get("Content-Type", "")

        if response.status_code >= 400:
            error_payload: Any = None
            if response.content:
                if "application/json" in content_type:
                    try:
                        error_payload = response.json()
                    except ValueError:
                        error_payload = response.text
                else:
                    error_payload = response.text
            raise RxResumeAPIError(
                response.status_code, response.text, payload=error_payload
            )

        if not response.content:
            return None

        if "application/json" in content_type:
            try:
                payload = response.json()
                if (
                    isinstance(payload, dict)
                    and payload.get("unhandled") is True
                    and payload.get("message") == "HTTPError"
                ):
                    raise RxResumeAPIError(
                        response.status_code,
                        (
                            f"Upstream API returned unhandled HTTPError payload for "
                            f"{method} {path}"
                        ),
                        payload=payload,
                    )
                return payload
            except ValueError:
                return response.text

        if content_type.startswith("text/"):
            return response.text

        return content_type, response.content

    async def list_resumes(
        self,
        tags: Optional[List[str]] = None,
        sort: Optional[str] = None,
    ) -> Any:
        params: List[Tuple[str, str]] = []
        if tags:
            for tag in tags:
                params.append(("tags[]", tag))
        if sort:
            params.append(("sort", sort))
        return await self._request("GET", "/resume/list", params=params or None)

    async def get_resume(self, resume_id: str) -> Any:
        _validate_resume_id(resume_id)
        return await self._request("GET", f"/resume/{resume_id}")

    async def create_resume(
        self,
        name: str,
        slug: str,
        tags: Optional[List[str]] = None,
    ) -> Any:
        payload = {
            "name": name,
            "slug": slug,
            "tags": tags or [],
        }
        return await self._request("POST", "/resume/create", json_body=payload)

    async def update_resume(
        self,
        resume_id: str,
        *,
        name: Optional[str] = None,
        slug: Optional[str] = None,
        tags: Optional[List[str]] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> Any:
        _validate_resume_id(resume_id)
        if data is not None:
            _validate_resume_data(data)

        payload: Dict[str, Any] = {}
        if name is not None:
            payload["name"] = name
        if slug is not None:
            payload["slug"] = slug
        if tags is not None:
            payload["tags"] = tags
        if data is not None:
            payload["data"] = data

        return await self._request("PUT", f"/resume/{resume_id}", json_body=payload)

    async def patch_resume(
        self,
        resume_id: str,
        *,
        patch_ops: List[Dict[str, Any]],
    ) -> Any:
        _validate_resume_id(resume_id)
        if not isinstance(patch_ops, list):
            raise ValueError("patch_ops must be a JSON Patch list")
        payload = {"id": resume_id, "patch": patch_ops}
        return await self._request(
            "PATCH",
            f"/resume/{resume_id}",
            json_body=payload,
        )

    async def update_resume_with_patch(
        self,
        resume_id: str,
        *,
        name: Optional[str] = None,
        slug: Optional[str] = None,
        tags: Optional[List[str]] = None,
        data_patch: Optional[Dict[str, Any]] = None,
    ) -> Any:
        _validate_resume_id(resume_id)
        if data_patch is None:
            return await self.update_resume(
                resume_id=resume_id,
                name=name,
                slug=slug,
                tags=tags,
                data=None,
            )

        if not isinstance(data_patch, dict):
            raise ValueError("data_patch must be an object (dict) when provided")

        resume = await self.get_resume(resume_id)
        if not isinstance(resume, dict):
            raise ValueError("Resume payload is not a JSON object")

        base_data = resume.get("data")
        if base_data is None:
            base_data = {}
        if not isinstance(base_data, dict):
            raise ValueError("Resume data is not a JSON object")

        merged_data = _deep_merge(base_data, data_patch)
        return await self.update_resume(
            resume_id=resume_id,
            name=name,
            slug=slug,
            tags=tags,
            data=merged_data,
        )

    async def delete_resume(self, resume_id: str) -> Any:
        _validate_resume_id(resume_id)
        return await self._request("DELETE", f"/resume/{resume_id}", json_body={})

    async def export_resume_pdf(self, resume_id: str) -> Any:
        _validate_resume_id(resume_id)
        return await self._request(
            "GET",
            f"/printer/resume/{resume_id}/pdf",
            accept="application/pdf",
        )

    async def export_resume_screenshot(self, resume_id: str) -> Any:
        _validate_resume_id(resume_id)
        return await self._request(
            "GET",
            f"/printer/resume/{resume_id}/screenshot",
            accept="image/png",
        )
