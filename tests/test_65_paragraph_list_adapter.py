import pytest
from mcp import ClientSession

from .conftest import call_tool_json


def _first_delta_item(resp: dict, key: str) -> dict:
    assert resp.get("mode") == "delta"
    items = (resp.get("delta") or {}).get(key) or []
    assert (
        isinstance(items, list) and items
    ), f"Expected non-empty {key} list, got: {resp!r}"
    item = items[0]
    assert isinstance(item, dict), f"Expected dict item, got: {item!r}"
    return item


@pytest.mark.asyncio
async def test_work_summary_highlights_round_trip_and_partial_updates_preserve_other_side(
    mcp_session: ClientSession, sample_resume_id: str
):
    created_payload = await call_tool_json(
        mcp_session,
        "resume.section.create",
        {
            "resume_id": sample_resume_id,
            "section": "work",
            "items": [
                {
                    "id": None,
                    "name": "PL Work",
                    "summary": "S1",
                    "highlights": ["A", "B"],
                }
            ],
            "return_mode": "delta",
        },
    )
    assert created_payload.get("status") == "success", created_payload
    created_resp = created_payload["response"]
    assert isinstance(created_resp, dict)
    created = _first_delta_item(created_resp, "created")
    item_id = created.get("id")
    assert isinstance(item_id, str) and item_id
    assert created.get("summary") == "S1"
    assert created.get("highlights") == ["A", "B"]
    assert "description" not in created, "Backing server text field must not be exposed"

    # Update only highlights; summary must be preserved.
    upd1_payload = await call_tool_json(
        mcp_session,
        "resume.section.update",
        {
            "resume_id": sample_resume_id,
            "section": "work",
            "items": [{"id": item_id, "highlights": ["C"]}],
            "return_mode": "delta",
        },
    )
    assert upd1_payload.get("status") == "success", upd1_payload
    upd1_resp = upd1_payload["response"]
    assert isinstance(upd1_resp, dict)
    updated1 = _first_delta_item(upd1_resp, "updated")
    assert updated1.get("id") == item_id
    assert updated1.get("summary") == "S1"
    assert updated1.get("highlights") == ["C"]
    assert "description" not in updated1

    # Update only summary; highlights must be preserved.
    upd2_payload = await call_tool_json(
        mcp_session,
        "resume.section.update",
        {
            "resume_id": sample_resume_id,
            "section": "work",
            "items": [{"id": item_id, "summary": "S2"}],
            "return_mode": "delta",
        },
    )
    assert upd2_payload.get("status") == "success", upd2_payload
    upd2_resp = upd2_payload["response"]
    assert isinstance(upd2_resp, dict)
    updated2 = _first_delta_item(upd2_resp, "updated")
    assert updated2.get("id") == item_id
    assert updated2.get("summary") == "S2"
    assert updated2.get("highlights") == ["C"]
    assert "description" not in updated2


@pytest.mark.asyncio
async def test_projects_description_highlights_round_trip_and_partial_updates_preserve_other_side(
    mcp_session: ClientSession, sample_resume_id: str
):
    created_payload = await call_tool_json(
        mcp_session,
        "resume.section.create",
        {
            "resume_id": sample_resume_id,
            "section": "projects",
            "items": [
                {
                    "id": None,
                    "name": "PL Project",
                    "description": "D1",
                    "highlights": ["X", "Y"],
                }
            ],
            "return_mode": "delta",
        },
    )
    assert created_payload.get("status") == "success", created_payload
    created_resp = created_payload["response"]
    assert isinstance(created_resp, dict)
    created = _first_delta_item(created_resp, "created")
    item_id = created.get("id")
    assert isinstance(item_id, str) and item_id
    assert created.get("description") == "D1"
    assert "<" not in (
        created.get("description") or ""
    ), "Description should be plain text"
    assert created.get("highlights") == ["X", "Y"]

    # Update only highlights; description must be preserved.
    upd1_payload = await call_tool_json(
        mcp_session,
        "resume.section.update",
        {
            "resume_id": sample_resume_id,
            "section": "projects",
            "items": [{"id": item_id, "highlights": ["Z"]}],
            "return_mode": "delta",
        },
    )
    assert upd1_payload.get("status") == "success", upd1_payload
    upd1_resp = upd1_payload["response"]
    assert isinstance(upd1_resp, dict)
    updated1 = _first_delta_item(upd1_resp, "updated")
    assert updated1.get("id") == item_id
    assert updated1.get("description") == "D1"
    assert updated1.get("highlights") == ["Z"]

    # Update only description; highlights must be preserved.
    upd2_payload = await call_tool_json(
        mcp_session,
        "resume.section.update",
        {
            "resume_id": sample_resume_id,
            "section": "projects",
            "items": [{"id": item_id, "description": "D2"}],
            "return_mode": "delta",
        },
    )
    assert upd2_payload.get("status") == "success", upd2_payload
    upd2_resp = upd2_payload["response"]
    assert isinstance(upd2_resp, dict)
    updated2 = _first_delta_item(upd2_resp, "updated")
    assert updated2.get("id") == item_id
    assert updated2.get("description") == "D2"
    assert updated2.get("highlights") == ["Z"]


@pytest.mark.asyncio
async def test_volunteer_summary_highlights_round_trip_and_partial_updates_preserve_other_side(
    mcp_session: ClientSession, sample_resume_id: str
):
    created_payload = await call_tool_json(
        mcp_session,
        "resume.section.create",
        {
            "resume_id": sample_resume_id,
            "section": "volunteer",
            "items": [
                {
                    "id": None,
                    "organization": "PL Org",
                    "summary": "V1",
                    "highlights": ["H1", "H2"],
                }
            ],
            "return_mode": "delta",
        },
    )
    assert created_payload.get("status") == "success", created_payload
    created_resp = created_payload["response"]
    assert isinstance(created_resp, dict)
    created = _first_delta_item(created_resp, "created")
    item_id = created.get("id")
    assert isinstance(item_id, str) and item_id
    assert created.get("summary") == "V1"
    assert created.get("highlights") == ["H1", "H2"]
    assert "description" not in created

    # Update only highlights; summary must be preserved.
    upd1_payload = await call_tool_json(
        mcp_session,
        "resume.section.update",
        {
            "resume_id": sample_resume_id,
            "section": "volunteer",
            "items": [{"id": item_id, "highlights": ["H3"]}],
            "return_mode": "delta",
        },
    )
    assert upd1_payload.get("status") == "success", upd1_payload
    upd1_resp = upd1_payload["response"]
    assert isinstance(upd1_resp, dict)
    updated1 = _first_delta_item(upd1_resp, "updated")
    assert updated1.get("id") == item_id
    assert updated1.get("summary") == "V1"
    assert updated1.get("highlights") == ["H3"]
    assert "description" not in updated1

    # Update only summary; highlights must be preserved.
    upd2_payload = await call_tool_json(
        mcp_session,
        "resume.section.update",
        {
            "resume_id": sample_resume_id,
            "section": "volunteer",
            "items": [{"id": item_id, "summary": "V2"}],
            "return_mode": "delta",
        },
    )
    assert upd2_payload.get("status") == "success", upd2_payload
    upd2_resp = upd2_payload["response"]
    assert isinstance(upd2_resp, dict)
    updated2 = _first_delta_item(upd2_resp, "updated")
    assert updated2.get("id") == item_id
    assert updated2.get("summary") == "V2"
    assert updated2.get("highlights") == ["H3"]
    assert "description" not in updated2
