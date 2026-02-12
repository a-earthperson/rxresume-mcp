import pytest
from mcp import ClientSession

from .conftest import call_tool_json


async def _get_full_resume(mcp_session: ClientSession, resume_id: str) -> dict:
    payload = await call_tool_json(
        mcp_session,
        "resume.doc.get",
        {"resume_id": resume_id, "summary": False},
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


def _find_item(items: list[dict], item_id: str) -> dict | None:
    for item in items:
        if item.get("id") == item_id:
            return item
    return None


def _assert_structured_error(
    payload: dict, expected_code: str = "VALIDATION_ERROR"
) -> dict:
    assert payload.get("status") == "error", payload
    err = payload.get("error")
    assert isinstance(err, dict), f"Expected error object, got: {err!r}"
    assert err.get("code") == expected_code
    return err


def _extract_period_values(ops: list[dict]) -> list[str]:
    values: list[str] = []
    for op in ops:
        if not isinstance(op, dict):
            continue
        value = op.get("value")
        if isinstance(value, dict) and "period" in value:
            values.append(value["period"])
            continue
        path = op.get("path")
        if isinstance(path, str) and path.endswith("/period"):
            values.append(value)
    return values


@pytest.mark.asyncio
async def test_doc_update_allows_name_and_tags(
    mcp_session: ClientSession, sample_resume_id: str
):
    """
    `resume.doc.update` supports metadata updates; name/tags remain valid inputs.
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
    assert "applied_ops" not in resp

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
async def test_doc_update_allows_batch_patch_basics_and_sections(
    mcp_session: ClientSession, sample_resume_id: str
):
    payload = await call_tool_json(
        mcp_session,
        "resume.doc.update",
        {
            "resume_id": sample_resume_id,
            "payload": {
                "name": "Batch Meta",
                "tags": ["pytest", "batch"],
                "basics": {"name": "Batch Basics"},
                "sections": [
                    {
                        "op": "create",
                        "section": "interests",
                        "items": [{"id": None, "name": "Batch Interest"}],
                    }
                ],
            },
        },
    )
    assert payload.get("status") == "success", payload
    resp = payload.get("response") or {}
    assert resp.get("resume_id") == sample_resume_id
    assert isinstance(resp.get("applied_ops"), list)
    assert resp.get("name") == "Batch Meta"
    assert resp.get("tags") == ["pytest", "batch"]
    created_ids = resp.get("created_ids") or []
    assert isinstance(created_ids, list)
    assert len(created_ids) == 1

    # Verify persisted basics + section item.
    resume = await _get_full_resume(mcp_session, sample_resume_id)
    assert resume.get("sections", {}).get("basics", {}).get("name") == "Batch Basics"
    interests = _get_section_items(resume, "interests")
    created_item = _find_item(interests, created_ids[0])
    assert created_item is not None, f"Expected created id in interests: {interests!r}"
    assert created_item.get("name") == "Batch Interest"


@pytest.mark.asyncio
async def test_doc_update_allows_basics_clear_fields_only(
    mcp_session: ClientSession, sample_resume_id: str
):
    seeded = await call_tool_json(
        mcp_session,
        "resume.doc.update",
        {"resume_id": sample_resume_id, "payload": {"basics": {"name": "ToClear"}}},
    )
    assert seeded.get("status") == "success", seeded

    cleared = await call_tool_json(
        mcp_session,
        "resume.doc.update",
        {"resume_id": sample_resume_id, "payload": {"basics_clear_fields": ["name"]}},
    )
    assert cleared.get("status") == "success", cleared
    resp = cleared.get("response") or {}
    assert resp.get("resume_id") == sample_resume_id
    assert isinstance(resp.get("applied_ops"), list)

    resume = await _get_full_resume(mcp_session, sample_resume_id)
    basics = resume.get("sections", {}).get("basics", {}) or {}
    assert basics.get("name") is None


@pytest.mark.asyncio
async def test_doc_update_sections_update_preserves_period_bounds(
    mcp_session: ClientSession, sample_resume_id: str
):
    created = await call_tool_json(
        mcp_session,
        "resume.doc.update",
        {
            "resume_id": sample_resume_id,
            "payload": {
                "sections": [
                    {
                        "op": "create",
                        "section": "work",
                        "items": [
                            {
                                "id": None,
                                "name": "Period Work",
                                "startDate": "2020-01",
                                "endDate": "2021-01",
                            }
                        ],
                    }
                ]
            },
        },
    )
    assert created.get("status") == "success", created
    created_id = (created.get("response") or {}).get("created_ids", [None])[0]
    assert isinstance(created_id, str) and created_id

    updated = await call_tool_json(
        mcp_session,
        "resume.doc.update",
        {
            "resume_id": sample_resume_id,
            "payload": {
                "sections": [
                    {
                        "op": "update",
                        "section": "work",
                        "items": [{"id": created_id, "startDate": "2019-06"}],
                    }
                ]
            },
        },
    )
    assert updated.get("status") == "success", updated

    resume = await _get_full_resume(mcp_session, sample_resume_id)
    work_items = _get_section_items(resume, "work")
    item = _find_item(work_items, created_id)
    assert item is not None, f"Expected work item {created_id} in {work_items!r}"
    assert item.get("startDate") == "2019-06"
    assert item.get("endDate") == "2021-01"


@pytest.mark.asyncio
async def test_doc_update_sections_create_encodes_start_only_period(
    mcp_session: ClientSession, sample_resume_id: str
):
    payload = await call_tool_json(
        mcp_session,
        "resume.doc.update",
        {
            "resume_id": sample_resume_id,
            "payload": {
                "sections": [
                    {
                        "op": "create",
                        "section": "work",
                        "items": [
                            {
                                "id": None,
                                "name": "Open Period Work",
                                "startDate": "Jan 2024",
                                "endDate": None,
                            }
                        ],
                    }
                ]
            },
        },
    )
    assert payload.get("status") == "success", payload
    resp = payload.get("response") or {}
    ops = resp.get("applied_ops") or []
    period_values = _extract_period_values(ops)
    assert "Jan 2024 to Present" in period_values


@pytest.mark.asyncio
async def test_doc_update_sections_create_encodes_end_only_period(
    mcp_session: ClientSession, sample_resume_id: str
):
    payload = await call_tool_json(
        mcp_session,
        "resume.doc.update",
        {
            "resume_id": sample_resume_id,
            "payload": {
                "sections": [
                    {
                        "op": "create",
                        "section": "work",
                        "items": [
                            {
                                "id": None,
                                "name": "Closed Period Work",
                                "startDate": None,
                                "endDate": "Feb 2024",
                            }
                        ],
                    }
                ]
            },
        },
    )
    assert payload.get("status") == "success", payload
    resp = payload.get("response") or {}
    ops = resp.get("applied_ops") or []
    period_values = _extract_period_values(ops)
    assert "Present to Feb 2024" in period_values


@pytest.mark.asyncio
async def test_doc_update_sections_update_preserves_highlights_and_allows_clear_only(
    mcp_session: ClientSession, sample_resume_id: str
):
    created = await call_tool_json(
        mcp_session,
        "resume.doc.update",
        {
            "resume_id": sample_resume_id,
            "payload": {
                "sections": [
                    {
                        "op": "create",
                        "section": "work",
                        "items": [
                            {
                                "id": None,
                                "name": "Summary Work",
                                "summary": "Seed summary",
                                "highlights": ["H1", "H2"],
                            }
                        ],
                    }
                ]
            },
        },
    )
    assert created.get("status") == "success", created
    created_id = (created.get("response") or {}).get("created_ids", [None])[0]
    assert isinstance(created_id, str) and created_id

    updated = await call_tool_json(
        mcp_session,
        "resume.doc.update",
        {
            "resume_id": sample_resume_id,
            "payload": {
                "sections": [
                    {
                        "op": "update",
                        "section": "work",
                        "items": [{"id": created_id, "summary": "Updated summary"}],
                    }
                ]
            },
        },
    )
    assert updated.get("status") == "success", updated

    resume = await _get_full_resume(mcp_session, sample_resume_id)
    work_items = _get_section_items(resume, "work")
    item = _find_item(work_items, created_id)
    assert item is not None, f"Expected work item {created_id} in {work_items!r}"
    assert item.get("summary") == "Updated summary"
    assert item.get("highlights") == ["H1", "H2"]

    cleared = await call_tool_json(
        mcp_session,
        "resume.doc.update",
        {
            "resume_id": sample_resume_id,
            "payload": {
                "sections": [
                    {
                        "op": "update",
                        "section": "work",
                        "items": None,
                        "clear": {created_id: ["summary"]},
                    }
                ]
            },
        },
    )
    assert cleared.get("status") == "success", cleared

    resume_after_clear = await _get_full_resume(mcp_session, sample_resume_id)
    work_items_after = _get_section_items(resume_after_clear, "work")
    cleared_item = _find_item(work_items_after, created_id)
    assert (
        cleared_item is not None
    ), f"Expected work item {created_id} in {work_items_after!r}"
    assert cleared_item.get("summary") in (None, "")
    assert cleared_item.get("highlights") == ["H1", "H2"]


@pytest.mark.asyncio
async def test_doc_update_sections_delete_removes_items(
    mcp_session: ClientSession, sample_resume_id: str
):
    created = await call_tool_json(
        mcp_session,
        "resume.doc.update",
        {
            "resume_id": sample_resume_id,
            "payload": {
                "sections": [
                    {
                        "op": "create",
                        "section": "interests",
                        "items": [{"id": None, "name": "Delete Me"}],
                    }
                ]
            },
        },
    )
    assert created.get("status") == "success", created
    created_id = (created.get("response") or {}).get("created_ids", [None])[0]
    assert isinstance(created_id, str) and created_id

    deleted = await call_tool_json(
        mcp_session,
        "resume.doc.update",
        {
            "resume_id": sample_resume_id,
            "payload": {
                "sections": [
                    {
                        "op": "delete",
                        "section": "interests",
                        "item_ids": [created_id],
                    }
                ]
            },
        },
    )
    assert deleted.get("status") == "success", deleted

    resume = await _get_full_resume(mcp_session, sample_resume_id)
    interests = _get_section_items(resume, "interests")
    assert _find_item(interests, created_id) is None


@pytest.mark.asyncio
async def test_doc_update_rejects_empty_payload(
    mcp_session: ClientSession, sample_resume_id: str
):
    payload = await call_tool_json(
        mcp_session,
        "resume.doc.update",
        {"resume_id": sample_resume_id, "payload": {}},
    )
    _assert_structured_error(payload)


@pytest.mark.asyncio
async def test_doc_update_sections_update_requires_items_or_clear(
    mcp_session: ClientSession, sample_resume_id: str
):
    payload = await call_tool_json(
        mcp_session,
        "resume.doc.update",
        {
            "resume_id": sample_resume_id,
            "payload": {"sections": [{"op": "update", "section": "work", "items": []}]},
        },
    )
    _assert_structured_error(payload)


@pytest.mark.asyncio
async def test_doc_update_sections_delete_requires_item_ids(
    mcp_session: ClientSession, sample_resume_id: str
):
    payload = await call_tool_json(
        mcp_session,
        "resume.doc.update",
        {
            "resume_id": sample_resume_id,
            "payload": {"sections": [{"op": "delete", "section": "interests"}]},
        },
    )
    _assert_structured_error(payload)


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
