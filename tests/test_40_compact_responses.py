import pytest
from mcp import ClientSession

from .conftest import call_tool_json


async def _get_full_resume(mcp_session: ClientSession, resume_id: str) -> dict:
    payload = await call_tool_json(
        mcp_session, "resume.doc.get", {"resume_id": resume_id, "summary": False}
    )
    assert payload.get("status") == "success", payload
    resume = payload.get("response") or {}
    assert isinstance(resume, dict), f"Expected resume object, got: {resume!r}"
    return resume


def _get_section_items(resume: dict, section: str) -> list[dict]:
    sections = resume.get("sections") or {}
    assert isinstance(sections, dict), f"Expected sections object, got: {sections!r}"
    items = sections.get(section) or []
    assert isinstance(items, list), f"Expected {section} list, got: {items!r}"
    return [item for item in items if isinstance(item, dict)]


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
async def test_doc_create_accepts_sections_object_and_is_compact(
    mcp_session: ClientSession,
):
    payload = await call_tool_json(
        mcp_session,
        "resume.doc.create",
        {
            "name": "Create With Sections",
            "tags": ["pytest", "create", "sections"],
            "sections": {
                "interests": [{"id": None, "name": "Chess"}],
            },
        },
    )
    assert payload.get("status") == "success", payload
    resp = payload.get("response") or {}
    assert isinstance(resp, dict)
    rid = resp.get("resume_id") or resp.get("id")
    assert isinstance(rid, str) and rid
    assert "resume" not in resp
    assert "basics" not in resp

    try:
        resume = await _get_full_resume(mcp_session, rid)
        interests = _get_section_items(resume, "interests")
        assert any(
            isinstance(item, dict) and item.get("name") == "Chess" for item in interests
        )
    finally:
        await call_tool_json(mcp_session, "resume.doc.delete", {"resume_id": rid})


@pytest.mark.asyncio
async def test_doc_create_accepts_basics_and_sections(
    mcp_session: ClientSession,
):
    payload = await call_tool_json(
        mcp_session,
        "resume.doc.create",
        {
            "name": "Create With Basics And Sections",
            "tags": ["pytest", "create", "basics"],
            "basics": {"name": "Ada Lovelace"},
            "sections": {
                "work": [
                    {
                        "id": None,
                        "name": "Acme Corp",
                        "position": "Engineer",
                    }
                ]
            },
        },
    )
    assert payload.get("status") == "success", payload
    resp = payload.get("response") or {}
    assert isinstance(resp, dict)
    rid = resp.get("resume_id") or resp.get("id")
    assert isinstance(rid, str) and rid
    assert "resume" not in resp
    basics = resp.get("basics") or {}
    assert basics.get("name") == "Ada Lovelace"

    try:
        resume = await _get_full_resume(mcp_session, rid)
        basics_full = resume.get("sections", {}).get("basics") or {}
        assert basics_full.get("name") == "Ada Lovelace"
        work_items = _get_section_items(resume, "work")
        assert any(
            isinstance(item, dict) and item.get("name") == "Acme Corp"
            for item in work_items
        )
    finally:
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
async def test_section_item_create_all_populates_delta(
    mcp_session: ClientSession, sample_resume_id: str
):
    payload = await call_tool_json(
        mcp_session,
        "resume.section.create",
        {
            "resume_id": sample_resume_id,
            "section": "interests",
            "items": [
                {
                    "id": None,
                    "name": "AllMode",
                    "keywords": ["delta"],
                }
            ],
            "return_mode": "all",
        },
    )
    assert payload.get("status") == "success"
    resp = payload.get("response")
    assert isinstance(resp, dict), "Expected response envelope object"
    assert resp.get("mode") == "all"

    items = resp.get("items") or []
    assert any(
        isinstance(item, dict) and item.get("name") == "AllMode" for item in items
    )

    created_items = resp.get("delta", {}).get("created") or []
    assert len(created_items) == 1
    created_id = created_items[0].get("id")
    assert isinstance(created_id, str) and created_id
    assert created_id in (resp.get("ids", {}).get("created") or [])


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


@pytest.mark.asyncio
async def test_export_pdf_returns_url_only(
    mcp_session: ClientSession, sample_resume_id: str
):
    payload = await call_tool_json(
        mcp_session, "resume.export.pdf", {"resume_id": sample_resume_id}
    )
    assert payload.get("status") == "success"
    resp = payload.get("response")
    assert isinstance(resp, dict)
    url = resp.get("url")
    assert isinstance(url, str) and url
    assert "content_base64" not in resp
    assert "content_type" not in resp
    assert "size_bytes" not in resp


@pytest.mark.asyncio
async def test_export_screenshot_returns_url_only(
    mcp_session: ClientSession, sample_resume_id: str
):
    payload = await call_tool_json(
        mcp_session, "resume.export.screenshot", {"resume_id": sample_resume_id}
    )
    assert payload.get("status") == "success"
    resp = payload.get("response")
    assert isinstance(resp, dict)
    url = resp.get("url")
    assert isinstance(url, str) and url
    assert "content_base64" not in resp
    assert "content_type" not in resp
    assert "size_bytes" not in resp
