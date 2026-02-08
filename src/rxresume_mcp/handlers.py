"""MCP-facing handlers that apply contracts before calling the API."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from rxresume_mcp.contracts import RESUME_UPDATE_CONTRACT, TransformContext
from rxresume_mcp.rxresume_client import RxResumeClient


class ResumeHandler:
    """Apply MCP <-> upstream contracts around resume operations."""

    def __init__(self, client: RxResumeClient):
        self._client = client

    async def list_resumes(
        self, tags: Optional[List[str]] = None, sort: Optional[str] = None
    ) -> Any:
        return await self._client.list_resumes(tags=tags, sort=sort)

    async def get_resume(self, resume_id: str) -> Dict[str, Any]:
        api_payload = await self._client.get_resume(resume_id=resume_id)
        ctx = TransformContext(operation="resume.get.response", root=api_payload)
        return RESUME_UPDATE_CONTRACT.api_to_mcp(api_payload, ctx)

    async def get_resume_by_username(self, username: str, slug: str) -> Dict[str, Any]:
        api_payload = await self._client.get_resume_by_username(
            username=username, slug=slug
        )
        ctx = TransformContext(
            operation="resume.get_by_username.response", root=api_payload
        )
        return RESUME_UPDATE_CONTRACT.api_to_mcp(api_payload, ctx)

    async def create_resume(
        self,
        name: str,
        *,
        tags: Optional[List[str]] = None,
        with_sample_data: bool = False,
    ) -> Any:
        return await self._client.create_resume(
            name=name,
            tags=tags,
            with_sample_data=with_sample_data,
        )

    async def update_resume(
        self,
        resume_id: str,
        *,
        name: Optional[str] = None,
        slug: Optional[str] = None,
        tags: Optional[List[str]] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        api_data: Optional[Dict[str, Any]] = None
        if data is not None:
            ctx = TransformContext(operation="resume.update.request", root=data)
            api_data = RESUME_UPDATE_CONTRACT.mcp_to_api(data, ctx)

        api_payload = await self._client.update_resume(
            resume_id=resume_id,
            name=name,
            slug=slug,
            tags=tags,
            data=api_data,
        )
        response_ctx = TransformContext(
            operation="resume.update.response", root=api_payload
        )
        return RESUME_UPDATE_CONTRACT.api_to_mcp(api_payload, response_ctx)

    async def delete_resume(self, resume_id: str) -> Any:
        return await self._client.delete_resume(resume_id=resume_id)

    async def export_resume_pdf(self, resume_id: str) -> Any:
        return await self._client.export_resume_pdf(resume_id=resume_id)

    async def export_resume_screenshot(self, resume_id: str) -> Any:
        return await self._client.export_resume_screenshot(resume_id=resume_id)
