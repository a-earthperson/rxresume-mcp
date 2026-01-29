"""
Async client for interacting with Reactive Resume API.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, List, Optional, Tuple

import httpx

logger = logging.getLogger(__name__)


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
        user_agent: str = "rxresume-mcp/0.1.0",
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
