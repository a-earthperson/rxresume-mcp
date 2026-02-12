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
    for key in ("httpStatus", "code", "message", "details", "issues", "retryable"):
        assert key in err, f"Expected error to include {key}, got: {err!r}"
    assert isinstance(err.get("httpStatus"), int), f"Bad httpStatus: {err!r}"
    assert isinstance(err.get("code"), str), f"Bad code: {err!r}"
    assert isinstance(err.get("message"), str), f"Bad message: {err!r}"
    assert isinstance(err.get("details"), list), f"Bad details: {err!r}"
    assert isinstance(err.get("issues"), list), f"Bad issues: {err!r}"
    assert isinstance(err.get("retryable"), bool), f"Bad retryable: {err!r}"
    assert err.get("code") == "VALIDATION_ERROR"
