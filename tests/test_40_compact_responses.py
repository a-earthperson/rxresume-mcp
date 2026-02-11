import pytest
from mcp import ClientSession

from .conftest import call_tool_json


@pytest.mark.asyncio
async def test_doc_create_is_compact_by_default(
    mcp_session: ClientSession,
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
            "tags": ["pytest", "compact"],
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
    mcp_session: ClientSession, sample_resume_id: str
):
    """
    Desired behavior:
    - item.create should return {created:[...]} or similar delta, not the entire section list.
    """
    payload = await call_tool_json(
        mcp_session,
        "resume.section.create",
        {
            "resume_id": sample_resume_id,
            "section": "profiles",
            "items": [
                {
                    "id": None,
                    "network": "GitHub",
                    "username": "abc",
                    "url": "https://github.com/abc",
                }
            ],
        },
    )
    assert payload.get("status") == "success"
    resp = payload.get("response")
    assert isinstance(resp, dict), "Expected delta response object, not a list"
    assert "created" in resp
    assert len(resp["created"]) == 1


@pytest.mark.asyncio
async def test_batch_create_returns_delta_not_full_list(
    mcp_session: ClientSession, sample_resume_id: str
):
    payload = await call_tool_json(
        mcp_session,
        "resume.section.create",
        {
            "resume_id": sample_resume_id,
            "section": "interests",
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


@pytest.mark.asyncio
async def test_section_item_update_can_return_ids_only(
    mcp_session: ClientSession, sample_resume_id: str
):
    """
    Issue 3 regression:
    - item.update must support a compact return mode to avoid echoing full section lists.
    """
    created_payload = await call_tool_json(
        mcp_session,
        "resume.section.create",
        {
            "resume_id": sample_resume_id,
            "section": "work",
            "items": [{"id": None, "name": "CompactUpdate", "description": "Seed"}],
            "return_mode": "delta",
        },
    )
    assert created_payload.get("status") == "success"
    created_resp = created_payload.get("response")
    assert isinstance(created_resp, dict)
    created_item = created_resp["created"][0]
    item_id = created_item.get("id")
    assert isinstance(item_id, str) and item_id

    update_payload = await call_tool_json(
        mcp_session,
        "resume.section.update",
        {
            "resume_id": sample_resume_id,
            "section": "work",
            "items": [{"id": item_id, "description": "Updated"}],
            "return_mode": "none",
        },
    )
    assert update_payload.get("status") == "success"
    resp = update_payload.get("response")
    assert isinstance(resp, dict), "Expected ids-only response object"
    assert item_id in (resp.get("updated_ids") or [])


@pytest.mark.asyncio
async def test_section_item_delete_can_return_ids_only(
    mcp_session: ClientSession, sample_resume_id: str
):
    """
    Issue 3 regression:
    - item.delete must support a compact return mode to avoid echoing full section lists.
    """
    created_payload = await call_tool_json(
        mcp_session,
        "resume.section.create",
        {
            "resume_id": sample_resume_id,
            "section": "work",
            "items": [{"id": None, "name": "CompactDelete", "description": "Seed"}],
            "return_mode": "delta",
        },
    )
    assert created_payload.get("status") == "success"
    created_resp = created_payload.get("response")
    assert isinstance(created_resp, dict)
    created_item = created_resp["created"][0]
    item_id = created_item.get("id")
    assert isinstance(item_id, str) and item_id

    delete_payload = await call_tool_json(
        mcp_session,
        "resume.section.delete",
        {
            "resume_id": sample_resume_id,
            "section": "work",
            "item_ids": [item_id],
            "return_mode": "none",
        },
    )
    assert delete_payload.get("status") == "success"
    resp = delete_payload.get("response")
    assert isinstance(resp, dict), "Expected ids-only response object"
    assert item_id in (resp.get("deleted_ids") or [])
