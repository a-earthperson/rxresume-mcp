import pytest
from mcp import ClientSession

from .conftest import call_tool_json


@pytest.mark.asyncio
async def test_basics_update_none_clears_field(
    mcp_session: ClientSession, empty_resume_id: str
):
    # set summary
    create_payload = await call_tool_json(
        mcp_session,
        "resume.basics.create",
        {
            "resume_id": empty_resume_id,
            "payload": {
                "name": "A",
                "headline": "H",
                "email": "a@example.com",
                "phone": None,
                "location": "Remote",
                "website": None,
                "summary": "Will be cleared",
            },
        },
    )
    assert create_payload.get("summary") == "Will be cleared"

    # Desired: summary=None means clear field (not "no-op").
    update_payload = await call_tool_json(
        mcp_session,
        "resume.basics.update",
        {
            "resume_id": empty_resume_id,
            "payload": {
                "name": None,
                "headline": None,
                "email": None,
                "phone": None,
                "location": None,
                "website": None,
                "summary": None,
            },
        },
    )
    assert update_payload.get("summary") in (
        None,
        "",
        {},
    ), f"Expected cleared summary, got: {update_payload.get('summary')!r}"
