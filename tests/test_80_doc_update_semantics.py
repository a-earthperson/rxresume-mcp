import pytest
from mcp import ClientSession

from .conftest import call_tool_json


@pytest.mark.asyncio
async def test_doc_update_allows_isPublic(
    mcp_session: ClientSession, sample_resume_id: str
):
    """
    Desired behavior:
    - doc.update should allow updating isPublic/isLocked when those fields are surfaced in doc.list.
    """
    payload = await call_tool_json(
        mcp_session,
        "resume.doc.update",
        {"resume_id": sample_resume_id, "payload": {"isPublic": True}},
    )
    assert payload.get("status") == "success", payload


@pytest.mark.asyncio
async def test_doc_update_supports_partial_data_patch(
    mcp_session: ClientSession, sample_resume_id: str
):
    """
    Desired behavior:
    - doc.update should support *partial* patching of resume data without requiring a full replacement blob.
    """
    payload = await call_tool_json(
        mcp_session,
        "resume.doc.update",
        {
            "resume_id": sample_resume_id,
            "payload": {"data": {"sections": {"basics": {"name": "Patched Name"}}}},
        },
    )
    assert payload.get("status") == "success", payload
