import uuid

import pytest
from mcp import ClientSession

from .conftest import call_tool_json


@pytest.mark.asyncio
async def test_delete_existing_resume_returns_success_null_payload(
    mcp_session: ClientSession, sample_resume_id: str
):
    payload = await call_tool_json(
        mcp_session, "resume.doc.delete", {"resume_id": sample_resume_id}
    )
    assert payload.get("status") == "success"
    resp = payload.get("response")
    assert isinstance(resp, dict)
    assert resp.get("resume_id") == sample_resume_id
    assert resp.get("applied_ops") == []
    assert resp.get("changed_paths") == []
    assert resp.get("created_ids") == []
    assert resp.get("deleted") is True
