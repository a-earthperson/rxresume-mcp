import pytest
from mcp import ClientSession

from .conftest import UUID_RE, call_tool_json


@pytest.mark.asyncio
async def test_create_ignores_or_rejects_client_supplied_item_id(
    mcp_session: ClientSession, empty_resume_id: str
):
    """
    Desired behavior:
    - Client-supplied IDs should be rejected or ignored (server generates canonical IDs).
    This test expects the server to IGNORE and generate a UUID.
    """
    payload = await call_tool_json(
        mcp_session,
        "resume.section.profile.item.create",
        {
            "resume_id": empty_resume_id,
            "items": {
                "id": "custom-id-123",
                "network": "Mastodon",
                "username": "eva",
                "website": "https://mastodon.social/@eva",
            },
        },
    )
    assert payload.get("status") == "success"
    items = payload["response"]
    created = next(
        i
        for i in items
        if i.get("network") == "Mastodon" and i.get("username") == "eva"
    )
    assert created.get("id") != "custom-id-123"
    assert UUID_RE.match(
        created.get("id", "")
    ), f"Expected UUID id, got: {created.get('id')!r}"
