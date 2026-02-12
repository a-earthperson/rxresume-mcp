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
    - item.create should return a stable envelope with mode=delta and delta.created items,
      not the entire section list.
    """
    payload = await call_tool_json(
        mcp_session,
        "resume.section.create",
        {
            "resume_id": sample_resume_id,
            "section": "interests",
            "items": [
                {
                    "id": None,
                    "name": "Photography",
                    "keywords": ["film"],
                }
            ],
        },
    )
    assert payload.get("status") == "success"
    resp = payload.get("response")
    assert isinstance(resp, dict), "Expected response envelope object"
    assert resp.get("mode") == "delta"
    assert resp.get("items") == []
    created_items = resp.get("delta", {}).get("created") or []
    assert len(created_items) == 1
    created_item = created_items[0]
    created_id = created_item.get("id")
    assert isinstance(created_id, str) and created_id
    assert created_id in (resp.get("ids", {}).get("created") or [])


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
    assert isinstance(resp, dict), "Expected response envelope object"
    assert resp.get("mode") == "delta"
    created_items = resp.get("delta", {}).get("created") or []
    assert len(created_items) == 2
    created_ids = [item.get("id") for item in created_items]
    assert all(isinstance(item_id, str) and item_id for item_id in created_ids)
    returned_ids = resp.get("ids", {}).get("created") or []
    assert set(created_ids) <= set(returned_ids)


@pytest.mark.asyncio
async def test_section_item_update_can_return_ids_only(
    mcp_session: ClientSession, sample_resume_id: str
):
    """
    Issue 3 regression:
    - item.update must support a compact return mode to avoid echoing full section lists,
      while still returning a stable envelope.
    """
    created_payload = await call_tool_json(
        mcp_session,
        "resume.section.create",
        {
            "resume_id": sample_resume_id,
            "section": "work",
            "items": [{"id": None, "name": "CompactUpdate", "summary": "Seed"}],
            "return_mode": "delta",
        },
    )
    assert created_payload.get("status") == "success"
    created_resp = created_payload.get("response")
    assert isinstance(created_resp, dict)
    assert created_resp.get("mode") == "delta"
    created_item = created_resp["delta"]["created"][0]
    item_id = created_item.get("id")
    assert isinstance(item_id, str) and item_id

    update_payload = await call_tool_json(
        mcp_session,
        "resume.section.update",
        {
            "resume_id": sample_resume_id,
            "section": "work",
            "items": [{"id": item_id, "summary": "Updated"}],
            "return_mode": "none",
        },
    )
    assert update_payload.get("status") == "success"
    resp = update_payload.get("response")
    assert isinstance(resp, dict), "Expected response envelope object"
    assert resp.get("mode") == "none"
    assert item_id in (resp.get("ids", {}).get("updated") or [])


@pytest.mark.asyncio
async def test_section_item_update_delta_returns_ids(
    mcp_session: ClientSession, sample_resume_id: str
):
    created_payload = await call_tool_json(
        mcp_session,
        "resume.section.create",
        {
            "resume_id": sample_resume_id,
            "section": "work",
            "items": [{"id": None, "name": "DeltaUpdate", "summary": "Seed"}],
            "return_mode": "delta",
        },
    )
    assert created_payload.get("status") == "success"
    created_resp = created_payload.get("response")
    assert isinstance(created_resp, dict)
    assert created_resp.get("mode") == "delta"
    created_item = created_resp["delta"]["created"][0]
    item_id = created_item.get("id")
    assert isinstance(item_id, str) and item_id

    update_payload = await call_tool_json(
        mcp_session,
        "resume.section.update",
        {
            "resume_id": sample_resume_id,
            "section": "work",
            "items": [{"id": item_id, "summary": "Seed"}],
            "return_mode": "delta",
        },
    )
    assert update_payload.get("status") == "success"
    resp = update_payload.get("response")
    assert isinstance(resp, dict), "Expected response envelope object"
    assert resp.get("mode") == "delta"
    updated_items = resp.get("delta", {}).get("updated") or []
    assert any(
        isinstance(item, dict) and item.get("id") == item_id for item in updated_items
    ), f"Expected updated item id {item_id} in: {updated_items!r}"
    assert item_id in (resp.get("ids", {}).get("updated") or [])


@pytest.mark.asyncio
async def test_section_item_delete_can_return_ids_only(
    mcp_session: ClientSession, sample_resume_id: str
):
    """
    Issue 3 regression:
    - item.delete must support a compact return mode to avoid echoing full section lists,
      while still returning a stable envelope.
    """
    created_payload = await call_tool_json(
        mcp_session,
        "resume.section.create",
        {
            "resume_id": sample_resume_id,
            "section": "work",
            "items": [{"id": None, "name": "CompactDelete", "summary": "Seed"}],
            "return_mode": "delta",
        },
    )
    assert created_payload.get("status") == "success"
    created_resp = created_payload.get("response")
    assert isinstance(created_resp, dict)
    assert created_resp.get("mode") == "delta"
    created_item = created_resp["delta"]["created"][0]
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
    assert isinstance(resp, dict), "Expected response envelope object"
    assert resp.get("mode") == "none"
    assert item_id in (resp.get("ids", {}).get("deleted") or [])
