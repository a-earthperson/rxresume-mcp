import pytest
from mcp import ClientSession

from .conftest import call_tool_json


@pytest.mark.asyncio
async def test_success_envelope_contains_status_and_response_object(
    mcp_session: ClientSession, sample_resume_id: str
):
    payload = await call_tool_json(
        mcp_session, "resume.basics.get", {"resume_id": sample_resume_id}
    )
    assert payload.get("status") == "success", payload
    assert "response" in payload, f"Missing response in payload: {payload!r}"
    assert "error" not in payload, f"Unexpected error in payload: {payload!r}"
    resp = payload.get("response")
    assert isinstance(resp, dict), f"Expected dict response, got: {type(resp)}"


@pytest.mark.asyncio
async def test_success_envelope_contains_status_and_response_list(
    mcp_session: ClientSession, sample_resume_id: str
):
    payload = await call_tool_json(
        mcp_session,
        "resume.section.list",
        {"resume_id": sample_resume_id, "section": "interests"},
    )
    assert payload.get("status") == "success", payload
    assert "response" in payload, f"Missing response in payload: {payload!r}"
    assert "error" not in payload, f"Unexpected error in payload: {payload!r}"
    resp = payload.get("response")
    assert isinstance(resp, list), f"Expected list response, got: {type(resp)}"
