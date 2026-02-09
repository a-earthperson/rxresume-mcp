import pytest
from mcp import ClientSession

from .conftest import call_tool_json


@pytest.mark.asyncio
async def test_summary_is_not_wrapped_in_html(
    mcp_session: ClientSession, empty_resume_id: str
):
    """
    Desired behavior:
    - Server/tool should not inject HTML like <p>...</p> into summaries by default.
      It should preserve plain text (or declare contentType explicitly).
    """
    summary = "Hello summary"
    payload = await call_tool_json(
        mcp_session,
        "resume.section.project.item.create",
        {
            "resume_id": empty_resume_id,
            "items": {
                "id": None,
                "name": "HTML Test",
                "period": "2026",
                "website": None,
                "summary": summary,
                "highlights": None,
            },
        },
    )
    assert payload.get("status") == "success"
    items = payload["response"]
    created = next(i for i in items if i.get("name") == "HTML Test")
    assert (
        created.get("summary") == summary
    ), f"Expected plain text summary, got: {created.get('summary')!r}"
