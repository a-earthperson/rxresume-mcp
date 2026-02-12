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
        "resume.basics.update",
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
async def test_basics_profiles_round_trip_uses_url_not_website(
    mcp_session: ClientSession, sample_resume_id: str
):
    payload = await call_tool_json(
        mcp_session,
        "resume.basics.update",
        {
            "resume_id": sample_resume_id,
            "payload": {
                "profiles": [
                    {
                        "network": "X",
                        "username": "eva",
                        "url": "https://x.com/eva",
                    }
                ]
            },
        },
    )
    assert payload.get("status") == "success"
    basics = payload["response"]
    profiles = basics.get("profiles")
    assert isinstance(profiles, list)
    created = profiles[0]
    assert created.get("url") == "https://x.com/eva"
    assert "website" not in created


@pytest.mark.asyncio
async def test_experience_item_round_trip_uses_name_not_company(
    mcp_session: ClientSession, sample_resume_id: str
):
    payload = await call_tool_json(
        mcp_session,
        "resume.section.create",
        {
            "resume_id": sample_resume_id,
            "section": "work",
            "items": [
                {
                    "id": None,
                    "name": "Tooling Inc",
                    "position": "API Tester",
                    "location": "Remote",
                    "period": "2026",
                    "url": "https://tooling.example",
                    "summary": "Did testing",
                    "highlights": ["H1"],
                }
            ],
            "return_mode": "delta",
        },
    )
    assert payload.get("status") == "success"
    resp = payload["response"]
    assert isinstance(resp, dict)
    assert resp.get("mode") == "delta"
    created = resp["delta"]["created"][0]
    assert created.get("name") == "Tooling Inc"
    assert "company" not in created
    assert "description" not in created, "Backing field should not be exposed"


@pytest.mark.asyncio
async def test_language_item_round_trip_uses_name_and_proficiency(
    mcp_session: ClientSession, sample_resume_id: str
):
    payload = await call_tool_json(
        mcp_session,
        "resume.section.create",
        {
            "resume_id": sample_resume_id,
            "section": "languages",
            "items": [
                {
                    "id": None,
                    "language": "Spanish",
                    "fluency": "Basic",
                    "level": 2,
                }
            ],
            "return_mode": "delta",
        },
    )
    assert payload.get("status") == "success"
    resp = payload["response"]
    assert isinstance(resp, dict)
    assert resp.get("mode") == "delta"
    created = resp["delta"]["created"][0]
    assert created.get("language") == "Spanish"
    assert created.get("fluency") == "Basic"


@pytest.mark.asyncio
async def test_doc_get_returns_canonical_schema(
    mcp_session: ClientSession, sample_resume_id: str
):
    # Setup: write basics
    await call_tool_json(
        mcp_session,
        "resume.basics.update",
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
        mcp_session,
        "resume.doc.get",
        {"resume_id": sample_resume_id, "summary": False},
    )
    assert payload.get("status") == "success"
    resume = payload.get("response")

    # Desired: response uses canonical external keys, not internal ones.
    basics = resume["sections"]["basics"]
    assert basics.get("label") == "Canon label"
    assert basics.get("url") == "https://canon.example.com"
    assert "headline" not in basics
    assert "website" not in basics
