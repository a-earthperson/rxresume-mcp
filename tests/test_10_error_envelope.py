import uuid

import pytest
from mcp import ClientSession

from .conftest import call_tool_json


def _assert_structured_error(
    payload: dict, *, expected_http: int | None = None, expected_code: str | None = None
):
    assert payload.get("status") == "error", f"Expected status=error, got: {payload}"
    err = payload.get("error")
    # Desired behavior: error is a dict (not a string blob).
    assert isinstance(
        err, dict
    ), f"Expected error to be a dict, got {type(err)}: {err!r}"
    if expected_http is not None:
        assert err.get("httpStatus") == expected_http
    if expected_code is not None:
        assert err.get("code") == expected_code
    assert isinstance(
        err.get("issues", []), list
    ), "Expected issues to be a list (possibly empty)."


@pytest.mark.asyncio
async def test_invalid_sort_returns_structured_error(mcp_session: ClientSession):
    payload = await call_tool_json(
        mcp_session,
        "resume.doc.list",
        {"tags": [], "sort": "invalidSortKey"},
    )
    _assert_structured_error(payload, expected_http=400)


@pytest.mark.asyncio
async def test_get_unknown_resume_returns_structured_not_found(
    mcp_session: ClientSession,
):
    unknown_id = str(uuid.uuid4())
    payload = await call_tool_json(
        mcp_session, "resume.doc.get", {"resume_id": unknown_id}
    )
    _assert_structured_error(payload, expected_http=404, expected_code="NOT_FOUND")


@pytest.mark.asyncio
async def test_patch_target_not_found_is_structured(
    mcp_session: ClientSession, sample_resume_id: str
):
    payload = await call_tool_json(
        mcp_session,
        "resume.section.update",
        {
            "resume_id": sample_resume_id,
            "section": "work",
            "items": [
                {
                    "id": "does-not-exist",
                    "name": "Nope",
                    "position": None,
                    "location": None,
                    "url": None,
                    "description": None,
                }
            ],
        },
    )
    _assert_structured_error(payload, expected_http=404)


@pytest.mark.asyncio
async def test_missing_required_argument_errors_are_structured(
    mcp_session: ClientSession, sample_resume_id: str
):
    payload = await call_tool_json(
        mcp_session,
        "resume.section.delete",
        {"resume_id": sample_resume_id, "section": "profiles", "item_ids": None},
    )
    _assert_structured_error(payload, expected_http=400)


@pytest.mark.asyncio
async def test_section_create_rejects_non_list_items_is_structured(
    mcp_session: ClientSession, sample_resume_id: str
):
    payload = await call_tool_json(
        mcp_session,
        "resume.section.create",
        {
            "resume_id": sample_resume_id,
            "section": "profiles",
            "items": {"not": "a list"},
        },
    )
    _assert_structured_error(
        payload, expected_http=400, expected_code="VALIDATION_ERROR"
    )


@pytest.mark.asyncio
async def test_export_pdf_unknown_resume_returns_structured_not_found(
    mcp_session: ClientSession,
):
    unknown_id = str(uuid.uuid4())
    payload = await call_tool_json(
        mcp_session, "resume.export.pdf", {"resume_id": unknown_id}
    )
    _assert_structured_error(payload, expected_http=404, expected_code="NOT_FOUND")
