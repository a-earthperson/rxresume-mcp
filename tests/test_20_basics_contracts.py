import uuid

import pytest
from mcp import ClientSession

from .conftest import call_tool_json

_BASICS_KEYS = ("name", "label", "email", "phone", "location", "url", "summary")


def _assert_success(payload: dict, *, resume_id: str | None = None) -> dict:
    assert payload.get("status") == "success", payload
    if resume_id is not None:
        assert payload.get("resume_id") == resume_id
    resp = payload.get("response")
    assert isinstance(
        resp, dict
    ), f"Expected response object, got: {type(resp)}: {resp!r}"
    return resp


def _assert_structured_error(
    payload: dict, *, expected_http: int | None = None, expected_code: str | None = None
) -> dict:
    assert payload.get("status") == "error", payload
    err = payload.get("error")
    assert isinstance(err, dict), f"Expected error dict, got: {type(err)}: {err!r}"
    if expected_http is not None:
        assert err.get("httpStatus") == expected_http
    if expected_code is not None:
        assert err.get("code") == expected_code
    # Keep the assertion weak but real: constrained agents depend on list-ness.
    assert isinstance(err.get("issues", []), list)
    return err


def _assert_basics_shape(basics: dict) -> None:
    assert set(basics.keys()) == set(_BASICS_KEYS), f"Unexpected keys: {sorted(basics)}"
    assert "headline" not in basics
    assert "website" not in basics
    assert "customFields" not in basics
    assert "sections" not in basics
    assert "data" not in basics
    for k in _BASICS_KEYS:
        v = basics.get(k)
        assert v is None or isinstance(v, str), f"{k} must be string|null, got: {v!r}"


def _tool_names(tools_result: object) -> set[str]:
    tools = getattr(tools_result, "tools", None) or []
    names: set[str] = set()
    for tool in tools:
        name = getattr(tool, "name", None)
        if isinstance(name, str) and name:
            names.add(name)
    return names


@pytest.mark.asyncio
async def test_basics_api_surface_is_get_patch(
    mcp_session: ClientSession,
):
    tools = await mcp_session.list_tools()
    names = _tool_names(tools)

    # Current surface (documented regression notes) uses patch, not create/update.
    assert "resume.basics.get" in names
    assert "resume.basics.patch" in names
    assert "resume.basics.create" not in names
    assert "resume.basics.update" not in names


@pytest.mark.asyncio
async def test_basics_get_is_compact_and_canonical(
    mcp_session: ClientSession,
    empty_resume_id: str,
):
    payload = await call_tool_json(
        mcp_session, "resume.basics.get", {"resume_id": empty_resume_id}
    )
    basics = _assert_success(payload, resume_id=empty_resume_id)
    _assert_basics_shape(basics)
    # Empty resume should return all-null basics.
    assert all(basics.get(k) is None for k in _BASICS_KEYS)


@pytest.mark.asyncio
async def test_basics_patch_partial_update_preserves_omitted_fields(
    mcp_session: ClientSession,
    empty_resume_id: str,
):
    # "Stupid model" pattern: update just one field without replaying the whole object.
    first = await call_tool_json(
        mcp_session,
        "resume.basics.patch",
        {"resume_id": empty_resume_id, "payload": {"name": "A"}},
    )
    basics1 = _assert_success(first, resume_id=empty_resume_id)
    _assert_basics_shape(basics1)
    assert basics1["name"] == "A"

    second = await call_tool_json(
        mcp_session,
        "resume.basics.patch",
        {"resume_id": empty_resume_id, "payload": {"label": "Engineer"}},
    )
    basics2 = _assert_success(second, resume_id=empty_resume_id)
    _assert_basics_shape(basics2)
    assert basics2["label"] == "Engineer"
    assert basics2["name"] == "A", "Omitted fields must be unchanged (patch semantics)."


@pytest.mark.asyncio
async def test_basics_patch_null_and_empty_string_clear_fields(
    mcp_session: ClientSession,
    empty_resume_id: str,
):
    await call_tool_json(
        mcp_session,
        "resume.basics.patch",
        {
            "resume_id": empty_resume_id,
            "payload": {"email": "a@example.com", "phone": "555-555"},
        },
    )

    cleared_null = await call_tool_json(
        mcp_session,
        "resume.basics.patch",
        {"resume_id": empty_resume_id, "payload": {"email": None}},
    )
    basics = _assert_success(cleared_null, resume_id=empty_resume_id)
    assert basics["email"] is None

    cleared_empty = await call_tool_json(
        mcp_session,
        "resume.basics.patch",
        {"resume_id": empty_resume_id, "payload": {"phone": ""}},
    )
    basics2 = _assert_success(cleared_empty, resume_id=empty_resume_id)
    assert basics2["phone"] is None


@pytest.mark.asyncio
async def test_basics_patch_clear_fields_works_without_payload(
    mcp_session: ClientSession,
    empty_resume_id: str,
):
    seeded = await call_tool_json(
        mcp_session,
        "resume.basics.patch",
        {"resume_id": empty_resume_id, "payload": {"name": "Eva", "label": "Builder"}},
    )
    basics1 = _assert_success(seeded, resume_id=empty_resume_id)
    assert basics1["label"] == "Builder"

    cleared = await call_tool_json(
        mcp_session,
        "resume.basics.patch",
        {"resume_id": empty_resume_id, "payload": None, "clear_fields": ["label"]},
    )
    basics2 = _assert_success(cleared, resume_id=empty_resume_id)
    assert basics2["label"] is None
    assert basics2["name"] == "Eva"


@pytest.mark.asyncio
async def test_basics_patch_clear_fields_accepts_string_or_list(
    mcp_session: ClientSession,
    empty_resume_id: str,
):
    await call_tool_json(
        mcp_session,
        "resume.basics.patch",
        {"resume_id": empty_resume_id, "payload": {"summary": "Hello"}},
    )

    as_string = await call_tool_json(
        mcp_session,
        "resume.basics.patch",
        {"resume_id": empty_resume_id, "payload": None, "clear_fields": "summary"},
    )
    basics1 = _assert_success(as_string, resume_id=empty_resume_id)
    assert basics1["summary"] is None

    await call_tool_json(
        mcp_session,
        "resume.basics.patch",
        {"resume_id": empty_resume_id, "payload": {"summary": "Hello2"}},
    )
    as_list = await call_tool_json(
        mcp_session,
        "resume.basics.patch",
        {"resume_id": empty_resume_id, "payload": None, "clear_fields": ["summary"]},
    )
    basics2 = _assert_success(as_list, resume_id=empty_resume_id)
    assert basics2["summary"] is None


@pytest.mark.asyncio
async def test_basics_patch_url_is_normalized_with_scheme(
    mcp_session: ClientSession,
    empty_resume_id: str,
):
    # "Stupid model" pattern: provides a bare domain.
    payload = await call_tool_json(
        mcp_session,
        "resume.basics.patch",
        {"resume_id": empty_resume_id, "payload": {"url": "example.com"}},
    )
    basics = _assert_success(payload, resume_id=empty_resume_id)
    assert basics["url"] in ("https://example.com", "http://example.com")
    assert basics["url"].startswith(("http://", "https://"))


@pytest.mark.asyncio
async def test_basics_patch_whitespace_summary_is_preserved(
    mcp_session: ClientSession,
    empty_resume_id: str,
):
    payload = await call_tool_json(
        mcp_session,
        "resume.basics.patch",
        {"resume_id": empty_resume_id, "payload": {"summary": " "}},
    )
    basics = _assert_success(payload, resume_id=empty_resume_id)
    assert basics["summary"] == " "


@pytest.mark.asyncio
async def test_basics_patch_rejects_common_wrong_keys_with_actionable_errors(
    mcp_session: ClientSession,
    empty_resume_id: str,
):
    # Small models frequently guess "website" or "description" or internal keys.
    for wrong_payload in (
        {"website": "https://example.com"},
        {"headline": "oops"},
        {"description": "oops"},
        {"unknown": "oops"},
    ):
        payload = await call_tool_json(
            mcp_session,
            "resume.basics.patch",
            {"resume_id": empty_resume_id, "payload": wrong_payload},
        )
        err = _assert_structured_error(
            payload, expected_http=400, expected_code="VALIDATION_ERROR"
        )
        assert isinstance(err.get("message"), str) and err.get("message")

    # Also common: payload is the wrong type entirely.
    wrong_type = await call_tool_json(
        mcp_session,
        "resume.basics.patch",
        {"resume_id": empty_resume_id, "payload": "name=Eva"},
    )
    _assert_structured_error(
        wrong_type, expected_http=400, expected_code="VALIDATION_ERROR"
    )


@pytest.mark.asyncio
async def test_basics_patch_requires_payload_or_clear_fields(
    mcp_session: ClientSession,
    empty_resume_id: str,
):
    payload = await call_tool_json(
        mcp_session,
        "resume.basics.patch",
        {"resume_id": empty_resume_id, "payload": None, "clear_fields": None},
    )
    _assert_structured_error(
        payload, expected_http=400, expected_code="VALIDATION_ERROR"
    )

    # Small-model mistake: clear_fields has the wrong type.
    bad_clear = await call_tool_json(
        mcp_session,
        "resume.basics.patch",
        {
            "resume_id": empty_resume_id,
            "payload": None,
            "clear_fields": {"field": "name"},
        },
    )
    _assert_structured_error(
        bad_clear, expected_http=400, expected_code="VALIDATION_ERROR"
    )


@pytest.mark.asyncio
async def test_basics_get_invalid_and_unknown_resume_ids_are_structured(
    mcp_session: ClientSession,
):
    invalid = await call_tool_json(
        mcp_session, "resume.basics.get", {"resume_id": "not-a-uuid"}
    )
    assert invalid.get("resume_id") == "not-a-uuid"
    _assert_structured_error(
        invalid, expected_http=400, expected_code="VALIDATION_ERROR"
    )

    unknown = await call_tool_json(
        mcp_session, "resume.basics.get", {"resume_id": str(uuid.uuid4())}
    )
    assert isinstance(unknown.get("resume_id"), str) and unknown["resume_id"]
    _assert_structured_error(unknown, expected_http=404, expected_code="NOT_FOUND")


@pytest.mark.asyncio
async def test_basics_delete_resets_if_tool_is_exposed(
    mcp_session: ClientSession,
    empty_resume_id: str,
):
    """
    Contract-style guard:
    - If the server advertises `resume.basics.delete`, it must actually work.
    - If it is not advertised (temporarily removed to avoid broken behavior), do nothing.
    """
    tools = await mcp_session.list_tools()
    names = _tool_names(tools)
    if "resume.basics.delete" not in names:
        return

    # Seed something non-null, then delete should reset to all-null.
    await call_tool_json(
        mcp_session,
        "resume.basics.patch",
        {
            "resume_id": empty_resume_id,
            "payload": {"name": "X", "label": "Y", "url": "https://example.com"},
        },
    )
    deleted = await call_tool_json(
        mcp_session, "resume.basics.delete", {"resume_id": empty_resume_id}
    )
    basics = _assert_success(deleted, resume_id=empty_resume_id)
    _assert_basics_shape(basics)
    assert all(basics.get(k) is None for k in _BASICS_KEYS)
