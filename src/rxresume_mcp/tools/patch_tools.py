"""Register generic JSON Patch tools."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

from rxresume_mcp import patch_ops
from rxresume_mcp.rxresume_client import RxResumeClient

from .core import execute_rxresume_operation
from .patching import _auto_id_patch_ops, _build_summary
from .sections import _extract_section_data, _require_resume_object


def register_patch_tools(mcp: FastMCP) -> None:
    """Register patch-level tools for resume updates."""

    @mcp.tool(
        name="patch_resume",
        description="Apply RxResume JSON Patch (RFC 6902 + id-path extensions).",
    )
    async def patch_resume(
        ctx: Context,
        resume_id: str = Field(description="Resume ID"),
        patch: List[patch_ops.JsonPatchOp] = Field(
            description="JSON Patch operations list (RFC 6902 + RxResume id paths).",
        ),
        include_result: bool = Field(
            default=False,
            description="If true, include the full resume in the response.",
        ),
        result_section_path: Optional[str] = Field(
            default=None,
            description=(
                "If set, include only this subtree from the patch result "
                "(basics | summary | picture | metadata | sections.<type> | "
                "customSections | customSections.<id>)."
            ),
        ),
    ) -> Dict[str, Any]:
        async def _operation(client: RxResumeClient) -> Any:
            _require_resume_object(await client.get_resume(resume_id))
            validated_ops = patch_ops.validate_patch_ops(patch)
            normalized_ops, created_ids = _auto_id_patch_ops(validated_ops)
            result = await client.patch_resume(resume_id, patch_ops=normalized_ops)
            extra: Dict[str, Any] = {}
            if result_section_path:
                extra["result_section"] = _extract_section_data(result, result_section_path)
            return _build_summary(
                resume_id,
                normalized_ops,
                created_ids,
                include_result=include_result,
                result=result,
                extra=extra if extra else None,
            )

        return await execute_rxresume_operation(
            operation_name=f"patch resume: {resume_id}",
            operation_func=_operation,
            ctx=ctx,
        )
