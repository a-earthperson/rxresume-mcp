import pytest
from mcp import ClientSession

from .conftest import call_tool_json


@pytest.mark.asyncio
async def test_doc_create_is_compact_by_default(
    mcp_session: ClientSession, unique_slug: str
):
    """
    Desired behavior:
    - Creating a resume should return a compact payload (e.g., just the ID),
      not an entire resume document with all sections.
    """
    payload = await call_tool_json(
        mcp_session,
        "resume.doc.create",
        {
            "name": "Compact Create",
            "slug": unique_slug,
            "tags": ["pytest", "compact"],
            "with_sample_data": True,
        },
    )
    assert payload.get("status") == "success"
    resp = payload.get("response")
    assert isinstance(resp, dict)
    assert "resume_id" in resp or "id" in resp
    assert "resume" not in resp, "Should not return full resume document by default"

    # cleanup
    rid = resp.get("resume_id") or resp.get("id")
    await call_tool_json(mcp_session, "resume.doc.delete", {"resume_id": rid})


@pytest.mark.asyncio
async def test_section_item_create_returns_delta_not_full_list(
    mcp_session: ClientSession, empty_resume_id: str
):
    """
    Desired behavior:
    - item.create should return {created:[...]} or similar delta, not the entire section list.
    """
    payload = await call_tool_json(
        mcp_session,
        "resume.section.profile.item.create",
        {
            "resume_id": empty_resume_id,
            "items": {
                "id": None,
                "network": "GitHub",
                "username": "abc",
                "website": "https://github.com/abc",
            },
        },
    )
    assert payload.get("status") == "success"
    resp = payload.get("response")
    assert isinstance(resp, dict), "Expected delta response object, not a list"
    assert "created" in resp
    assert len(resp["created"]) == 1


@pytest.mark.asyncio
async def test_doc_update_returns_delta_not_full_resume(
    mcp_session: ClientSession, empty_resume_id: str
):
    payload = await call_tool_json(
        mcp_session,
        "resume.doc.update",
        {"resume_id": empty_resume_id, "payload": {"tags": ["pytest", "delta"]}},
    )
    assert payload.get("status") == "success"
    resp = payload.get("response")
    assert isinstance(resp, dict), "Expected structured delta response"
    assert (
        "sections" not in resp
    ), "Should not echo back entire resume document in update response"
    assert resp.get("updated") is True


@pytest.mark.asyncio
async def test_batch_create_returns_delta_not_full_list(
    mcp_session: ClientSession, empty_resume_id: str
):
    payload = await call_tool_json(
        mcp_session,
        "resume.section.interest.item.create",
        {
            "resume_id": empty_resume_id,
            "items": [
                {"id": None, "name": "Batch1", "keywords": ["a"]},
                {"id": None, "name": "Batch2", "keywords": ["b"]},
            ],
        },
    )
    assert payload.get("status") == "success"
    resp = payload.get("response")
    assert isinstance(resp, dict), "Expected delta response object, not a list"
    assert "created" in resp
    assert len(resp["created"]) == 2
