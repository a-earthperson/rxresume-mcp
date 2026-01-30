"""
Async client for interacting with Reactive Resume API.
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import httpx
from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, ValidationError

from . import DEFAULT_USER_AGENT

logger = logging.getLogger(__name__)


def _deep_merge(base: Any, patch: Any) -> Any:
    if isinstance(base, dict) and isinstance(patch, dict):
        merged = dict(base)
        for key, value in patch.items():
            if key in merged:
                merged[key] = _deep_merge(merged[key], value)
            else:
                merged[key] = value
        return merged
    return patch


def _find_resume_schema_path() -> Path | None:
    package_candidate = (
        Path(__file__).resolve().parent / "resources" / "resume-schema.json"
    )
    if package_candidate.is_file():
        return package_candidate

    return None


@lru_cache(maxsize=1)
def _load_resume_schema() -> Dict[str, Any]:
    schema_path = _find_resume_schema_path()
    if not schema_path:
        raise FileNotFoundError(
            "Resume schema file not found (expected packaged resources)."
        )
    return json.loads(schema_path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _resume_schema_validator() -> Draft202012Validator:
    schema = _load_resume_schema()
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def _format_validation_errors(
    errors: List[ValidationError], max_errors: int = 5
) -> str:
    lines: List[str] = []
    for err in errors[:max_errors]:
        path = ".".join(str(part) for part in err.path) or "<root>"
        lines.append(f"{path}: {err.message}")
    if len(errors) > max_errors:
        lines.append(f"... ({len(errors) - max_errors} more)")
    return "; ".join(lines)


def _validate_resume_data(data: Dict[str, Any]) -> None:
    try:
        validator = _resume_schema_validator()
    except (FileNotFoundError, json.JSONDecodeError, SchemaError) as exc:
        raise ValueError(f"Resume schema unavailable or invalid: {exc}") from exc

    errors = sorted(validator.iter_errors(data), key=lambda err: list(err.path))
    if errors:
        details = _format_validation_errors(errors)
        raise ValueError(f"Resume data failed schema validation: {details}")


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
        json_body: Optional[Dict[str, Any]] = None,
        accept: str = "application/json",
    ) -> Any:
        logger.debug("Requesting %s %s", method, path)
        response = await self.client.request(
            method,
            path,
            params=params,
            json=json_body,
            headers={"Accept": accept},
        )
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
                return response.json()
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
        return await self._request("GET", f"/resume/{resume_id}")

    async def get_resume_by_username(self, username: str, slug: str) -> Any:
        return await self._request("GET", f"/resume/{username}/{slug}")

    async def create_resume(
        self,
        name: str,
        slug: str,
        tags: Optional[List[str]] = None,
        with_sample_data: bool = False,
    ) -> Any:
        payload = {
            "name": name,
            "slug": slug,
            "tags": tags or [],
            "withSampleData": with_sample_data,
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

    async def update_resume_with_patch(
        self,
        resume_id: str,
        *,
        name: Optional[str] = None,
        slug: Optional[str] = None,
        tags: Optional[List[str]] = None,
        data_patch: Optional[Dict[str, Any]] = None,
    ) -> Any:
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
        return await self._request("DELETE", f"/resume/{resume_id}", json_body={})

    async def export_resume_pdf(self, resume_id: str) -> Any:
        return await self._request(
            "GET",
            f"/printer/resume/{resume_id}/pdf",
            accept="application/pdf",
        )

    async def export_resume_screenshot(self, resume_id: str) -> Any:
        return await self._request(
            "GET",
            f"/printer/resume/{resume_id}/screenshot",
            accept="image/png",
        )
