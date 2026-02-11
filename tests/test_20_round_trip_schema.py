import pytest
from mcp import ClientSession

from .conftest import call_tool_json


@pytest.mark.asyncio
async def test_basics_round_trip_uses_label_and_url(
    mcp_session: ClientSession, sample_resume_id: str
):
    # Desired: response schema uses the same keys it accepts label/url.
    payload = await call_tool_json(
        mcp_session,
        "resume.basics.patch",
        {
            "resume_id": sample_resume_id,
            "payload": {
                "name": "Eva",
                "label": "label Here",
                "email": "eva@example.com",
                "phone": None,
                "location": "Remote",
                "url": "https://eva.example.com",
                "summary": "Plain text summary",
            },
        },
    )
    assert payload.get("status") == "success"
    basics = payload.get("response", {})
    assert basics.get("label") == "label Here"
    assert basics.get("url") == "https://eva.example.com"
    assert "headline" not in basics, "Should not return internal field 'headline'"
    assert "website" not in basics, "Should not return internal field 'website'"


@pytest.mark.asyncio
async def test_profile_item_round_trip_uses_url_not_website(
    mcp_session: ClientSession, sample_resume_id: str
):
    payload = await call_tool_json(
        mcp_session,
        "resume.section.profile.item.create",
        {
            "resume_id": sample_resume_id,
            "items": {
                "id": None,
                "network": "X",
                "username": "eva",
                "url": "https://x.com/eva",
            },
        },
    )
    assert payload.get("status") == "success"
    items = payload["response"]
    # Current implementation returns a list; desired canonical shape would return url keys.
    created = next(
        i for i in items if i.get("network") == "X" and i.get("username") == "eva"
    )
    assert created.get("url") == "https://x.com/eva"
    assert "website" not in created


@pytest.mark.asyncio
async def test_experience_item_round_trip_uses_name_not_company(
    mcp_session: ClientSession, sample_resume_id: str
):
    payload = await call_tool_json(
        mcp_session,
        "resume.section.work.item.create",
        {
            "resume_id": sample_resume_id,
            "items": {
                "id": None,
                "name": "Tooling Inc",
                "position": "API Tester",
                "location": "Remote",
                "startDate": "2026",
                "url": "https://tooling.example",
                "description": "Did testing",
            },
        },
    )
    assert payload.get("status") == "success"
    items = payload["response"]
    created = next(i for i in items if i.get("position") == "API Tester")
    assert created.get("name") == "Tooling Inc"
    assert "company" not in created


@pytest.mark.asyncio
async def test_language_item_round_trip_uses_name_and_proficiency(
    mcp_session: ClientSession, sample_resume_id: str
):
    payload = await call_tool_json(
        mcp_session,
        "resume.section.language.item.create",
        {
            "resume_id": sample_resume_id,
            "items": {
                "id": None,
                "language": "Spanish",
                "fluency": "Basic",
                "level": 2,
            },
        },
    )
    assert payload.get("status") == "success"
    items = payload["response"]
    created = next((i for i in items if i.get("language") == "Spanish"), None)
    assert created is not None, f"Expected to find created language item in: {items!r}"
    assert created.get("fluency") == "Basic"


@pytest.mark.asyncio
async def test_doc_get_returns_canonical_schema(
    mcp_session: ClientSession, sample_resume_id: str
):
    # Setup: write basics
    await call_tool_json(
        mcp_session,
        "resume.basics.patch",
        {
            "resume_id": sample_resume_id,
            "payload": {
                "name": "Canon Name",
                "label": "Canon label",
                "email": "canon@example.com",
                "phone": None,
                "location": "Remote",
                "url": "https://canon.example.com",
                "summary": "Canon summary",
            },
        },
    )

    payload = await call_tool_json(
        mcp_session, "resume.doc.get", {"resume_id": sample_resume_id}
    )
    assert payload.get("status") == "success"
    resume = payload.get("response")

    # Desired: response uses canonical external keys, not internal ones.
    basics = resume["sections"]["basics"]
    assert basics.get("label") == "Canon label"
    assert basics.get("url") == "https://canon.example.com"
    assert "headline" not in basics
    assert "website" not in basics
