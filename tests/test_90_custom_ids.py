import pytest
from mcp import ClientSession

from .conftest import call_tool_json


@pytest.mark.asyncio
async def test_create_ignores_or_rejects_client_supplied_item_id(
    mcp_session: ClientSession, sample_resume_id: str
):
    """
    Desired behavior:
    - Client-supplied IDs should be rejected (server generates canonical IDs).
    """
    payload = await call_tool_json(
        mcp_session,
        "resume.section.create",
        {
            "resume_id": sample_resume_id,
            "section": "interests",
            "items": [
                {
                    "id": "custom-id-123",
                    "name": "Music",
                    "keywords": ["jazz"],
                }
            ],
        },
    )
    assert payload.get("status") == "error", payload
    err = payload.get("error")
    assert isinstance(err, dict), err
    assert err.get("code") == "VALIDATION_ERROR"
