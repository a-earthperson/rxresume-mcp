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


@pytest.mark.asyncio
async def test_section_item_update_allows_clear_only_without_items(
    mcp_session: ClientSession, sample_resume_id: str
):
    """
    Issue 9 regression:
    - item.update should allow "clear-only" operations (no items payload) as long
      as `clear` is provided.
    """
    created_payload = await call_tool_json(
        mcp_session,
        "resume.section.create",
        {
            "resume_id": sample_resume_id,
            "section": "work",
            "items": [{"id": None, "name": "ClearOnly", "description": "Will clear"}],
            "return_mode": "delta",
        },
    )
    assert created_payload.get("status") == "success"
    created_resp = created_payload.get("response")
    assert isinstance(created_resp, dict)
    created_item = created_resp["created"][0]
    item_id = created_item.get("id")
    assert isinstance(item_id, str) and item_id

    cleared_payload = await call_tool_json(
        mcp_session,
        "resume.section.update",
        {
            "resume_id": sample_resume_id,
            "section": "work",
            "items": None,
            "clear": {item_id: ["description"]},
            "return_mode": "delta",
        },
    )
    assert cleared_payload.get("status") == "success"
    resp = cleared_payload.get("response")
    assert isinstance(resp, dict)
    updated = resp.get("updated") or []
    assert (
        isinstance(updated, list) and updated
    ), f"Expected updated list, got: {resp!r}"
    updated_item = next(
        (i for i in updated if isinstance(i, dict) and i.get("id") == item_id), None
    )
    assert (
        updated_item is not None
    ), f"Expected updated item id {item_id} in: {updated!r}"
    assert (
        updated_item.get("description") is None
    ), f"Expected description cleared to None, got: {updated_item.get('description')!r}"
