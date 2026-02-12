import pytest
from mcp import ClientSession

from .conftest import call_tool_json


@pytest.mark.asyncio
async def test_doc_update_allows_name_and_tags(
    mcp_session: ClientSession, sample_resume_id: str
):
    """
    `resume.doc.update` intentionally supports only a small metadata surface area:
    - name
    - tags
    """
    payload = await call_tool_json(
        mcp_session,
        "resume.doc.update",
        {
            "resume_id": sample_resume_id,
            "payload": {"name": "Updated Name", "tags": ["pytest", "updated"]},
        },
    )
    assert payload.get("status") == "success", payload
    resp = payload.get("response") or {}
    assert resp.get("resume_id") == sample_resume_id
    assert resp.get("name") == "Updated Name"
    assert resp.get("tags") == ["pytest", "updated"]

    # Verify persisted and canonical get response doesn't leak internal fields.
    get_payload = await call_tool_json(
        mcp_session,
        "resume.doc.get",
        {"resume_id": sample_resume_id, "summary": False},
    )
    assert get_payload.get("status") == "success", get_payload
    resume = get_payload.get("response") or {}
    assert resume.get("name") == "Updated Name"
    assert resume.get("tags") == ["pytest", "updated"]
    assert "isPublic" not in resume
    assert "isLocked" not in resume


@pytest.mark.asyncio
async def test_doc_list_strips_isPublic_and_isLocked(
    mcp_session: ClientSession, sample_resume_id: str
):
    """
    `resume.doc.list` returns upstream summaries; we strip internal fields so callers
    never see `isPublic` / `isLocked` in any view.
    """
    payload = await call_tool_json(
        mcp_session, "resume.doc.list", {"tags": [], "sort": None}
    )
    assert payload.get("status") == "success", payload
    resumes = payload.get("response") or []
    assert isinstance(resumes, list)
    for entry in resumes:
        if not isinstance(entry, dict):
            continue
        assert "isPublic" not in entry
        assert "isLocked" not in entry
