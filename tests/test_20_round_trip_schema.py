import pytest
from mcp import ClientSession

from .conftest import call_tool_json


@pytest.mark.asyncio
async def test_basics_round_trip_uses_headline_and_website(
    mcp_session: ClientSession, empty_resume_id: str
):
    # Desired: response schema uses the same keys it accepts (headline/website), not label/url.
    payload = await call_tool_json(
        mcp_session,
        "resume.basics.create",
        {
            "resume_id": empty_resume_id,
            "payload": {
                "name": "Eva",
                "headline": "Headline Here",
                "email": "eva@example.com",
                "phone": None,
                "location": "Remote",
                "website": "https://eva.example.com",
                "summary": "Plain text summary",
            },
        },
    )
    assert payload.get("headline") == "Headline Here"
    assert payload.get("website") == "https://eva.example.com"
    assert "label" not in payload, "Should not return internal field 'label'"
    assert "url" not in payload, "Should not return internal field 'url'"


@pytest.mark.asyncio
async def test_profile_item_round_trip_uses_website_not_url(
    mcp_session: ClientSession, empty_resume_id: str
):
    payload = await call_tool_json(
        mcp_session,
        "resume.section.profile.item.create",
        {
            "resume_id": empty_resume_id,
            "items": {
                "id": None,
                "network": "X",
                "username": "eva",
                "website": "https://x.com/eva",
            },
        },
    )
    assert payload.get("status") == "success"
    items = payload["response"]
    # Current implementation returns a list; desired canonical shape would return website keys.
    created = next(
        i for i in items if i.get("network") == "X" and i.get("username") == "eva"
    )
    assert created.get("website") == "https://x.com/eva"
    assert "url" not in created


@pytest.mark.asyncio
async def test_experience_item_round_trip_uses_company_not_name(
    mcp_session: ClientSession, empty_resume_id: str
):
    payload = await call_tool_json(
        mcp_session,
        "resume.section.experience.item.create",
        {
            "resume_id": empty_resume_id,
            "items": {
                "id": None,
                "company": "Tooling Inc",
                "position": "API Tester",
                "location": "Remote",
                "period": "2026",
                "website": "https://tooling.example",
                "summary": "Did testing",
                "highlights": ["A", "B"],
            },
        },
    )
    assert payload.get("status") == "success"
    items = payload["response"]
    created = next(i for i in items if i.get("position") == "API Tester")
    assert created.get("company") == "Tooling Inc"
    assert "name" not in created


@pytest.mark.asyncio
async def test_language_item_round_trip_uses_language_and_fluency(
    mcp_session: ClientSession, empty_resume_id: str
):
    payload = await call_tool_json(
        mcp_session,
        "resume.section.language.item.create",
        {
            "resume_id": empty_resume_id,
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

    # Be robust to current (broken) schema which returns {"name": "...", "proficiency": "..."}.
    created = next(
        (
            i
            for i in items
            if i.get("language") == "Spanish" or i.get("name") == "Spanish"
        ),
        None,
    )
    assert created is not None, f"Expected to find created language item in: {items!r}"

    # Desired: canonical keys match inputs.
    assert created.get("language") == "Spanish"
    assert created.get("fluency") == "Basic"
    assert "name" not in created
    assert "proficiency" not in created
    payload = await call_tool_json(
        mcp_session,
        "resume.section.language.item.create",
        {
            "resume_id": empty_resume_id,
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
    created = next(i for i in items if i.get("language") == "Spanish")
    assert created.get("fluency") == "Basic"
    assert "name" not in created
    assert "proficiency" not in created


@pytest.mark.asyncio
async def test_doc_get_returns_canonical_schema(
    mcp_session: ClientSession, empty_resume_id: str
):
    # Setup: write basics
    await call_tool_json(
        mcp_session,
        "resume.basics.create",
        {
            "resume_id": empty_resume_id,
            "payload": {
                "name": "Canon Name",
                "headline": "Canon Headline",
                "email": "canon@example.com",
                "phone": None,
                "location": "Remote",
                "website": "https://canon.example.com",
                "summary": "Canon summary",
            },
        },
    )

    payload = await call_tool_json(
        mcp_session, "resume.doc.get", {"resume_id": empty_resume_id}
    )
    assert payload.get("status") == "success"
    resume = payload.get("response")

    # Desired: response uses canonical external keys, not internal ones.
    basics = resume["sections"]["basics"]
    assert basics.get("headline") == "Canon Headline"
    assert basics.get("website") == "https://canon.example.com"
    assert "label" not in basics
    assert "url" not in basics
