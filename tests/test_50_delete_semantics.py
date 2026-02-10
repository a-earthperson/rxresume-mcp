import uuid

import pytest
from mcp import ClientSession

from .conftest import call_tool_json


@pytest.mark.asyncio
async def test_delete_unknown_resume_returns_not_found(mcp_session: ClientSession):
    unknown_id = str(uuid.uuid4())
    payload = await call_tool_json(
        mcp_session, "resume.doc.delete", {"resume_id": unknown_id}
    )
    assert payload.get("status") == "error"
    assert isinstance(payload.get("error"), dict)
    assert payload["error"].get("code") == "NOT_FOUND"


@pytest.mark.asyncio
async def test_delete_returns_structured_deleted_flag(
    mcp_session: ClientSession, sample_resume_id: str
):
    payload = await call_tool_json(
        mcp_session, "resume.doc.delete", {"resume_id": sample_resume_id}
    )
    assert payload.get("status") == "success"
    resp = payload.get("response")
    assert isinstance(resp, dict), "Expected structured response"
    assert resp.get("deleted") is True
