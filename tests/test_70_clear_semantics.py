import pytest
from mcp import ClientSession

from .conftest import call_tool_json


@pytest.mark.asyncio
async def test_basics_update_none_clears_field(
    mcp_session: ClientSession, sample_resume_id: str
):
    # set summary (stored as data.summary.content in RxResume)
    create_payload = await call_tool_json(
        mcp_session,
        "resume.basics.patch",
        {
            "resume_id": sample_resume_id,
            "payload": {
                "name": "A",
                "label": "H",
                "email": "a@example.com",
                "phone": None,
                "location": "Remote",
                "url": None,
                "summary": "Will be cleared",
            },
        },
    )
    assert create_payload.get("status") == "success"
    assert create_payload.get("response", {}).get("summary") is not None

    # Desired: description=None means clear field (not "no-op").
    update_payload = await call_tool_json(
        mcp_session,
        "resume.basics.patch",
        {
            "resume_id": sample_resume_id,
            "payload": {
                "name": None,
                "label": None,
                "email": None,
                "phone": None,
                "location": None,
                "url": None,
                "summary": None,
            },
        },
    )
    assert update_payload.get("status") == "success"
    assert update_payload.get("response", {}).get("summary") in (
        None,
        "",
        {},
    ), f"Expected cleared summary, got: {update_payload.get('response', {}).get('summary')!r}"
