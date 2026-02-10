import pytest
from mcp import ClientSession

from .conftest import call_tool_json


@pytest.mark.asyncio
async def test_basics_update_none_clears_field(
    mcp_session: ClientSession, sample_resume_id: str
):
    # set description (stored as data.summary.content in RxResume)
    create_payload = await call_tool_json(
        mcp_session,
        "resume.basics.create",
        {
            "resume_id": sample_resume_id,
            "payload": {
                "name": "A",
                "label": "H",
                "email": "a@example.com",
                "phone": None,
                "location": "Remote",
                "url": None,
                "description": "Will be cleared",
            },
        },
    )
    assert create_payload.get("status") == "success"
    assert create_payload.get("response", {}).get("description") == "Will be cleared"

    # Desired: description=None means clear field (not "no-op").
    update_payload = await call_tool_json(
        mcp_session,
        "resume.basics.update",
        {
            "resume_id": sample_resume_id,
            "payload": {
                "name": None,
                "label": None,
                "email": None,
                "phone": None,
                "location": None,
                "url": None,
                "description": None,
            },
        },
    )
    assert update_payload.get("status") == "success"
    assert update_payload.get("response", {}).get("description") in (
        None,
        "",
        {},
    ), f"Expected cleared description, got: {update_payload.get('response', {}).get('description')!r}"
