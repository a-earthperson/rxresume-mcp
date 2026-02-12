import pytest
from mcp import ClientSession

from .conftest import call_tool_json


@pytest.mark.asyncio
async def test_description_is_not_wrapped_in_html(
    mcp_session: ClientSession, sample_resume_id: str
):
    """
    Desired behavior:
    - Server/tool should not inject HTML like <p>...</p> into description fields by
      default. It should preserve plain text verbatim.
    """
    description = "Hello description"
    payload = await call_tool_json(
        mcp_session,
        "resume.section.create",
        {
            "resume_id": sample_resume_id,
            "section": "projects",
            "items": [
                {
                    "id": None,
                    "name": "HTML Test",
                    "startDate": "2026",
                    "url": None,
                    "description": description,
                }
            ],
            "return_mode": "delta",
        },
    )
    assert payload.get("status") == "success"
    resp = payload["response"]
    assert isinstance(resp, dict)
    assert resp.get("mode") == "delta"
    created = resp["delta"]["created"][0]
    assert created.get("name") == "HTML Test"
    assert (
        created.get("description") == description
    ), f"Expected plain text description, got: {created.get('description')!r}"
