import pytest
from mcp import ClientSession

from .conftest import call_tool_json


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "section, item_payload, expected_null_keys",
    [
        (
            "education",
            {
                "id": None,
                "institution": "Test University",
                "studyType": "MSc",
                "area": "HCI",
                "score": None,
                "location": None,
                "startDate": None,
                "endDate": None,
                "url": None,
                "description": None,
            },
            ("score", "location", "startDate", "endDate", "url", "description"),
        ),
        (
            "work",
            {
                "id": None,
                "name": "Null Period Co",
                "position": "Tester",
                "location": None,
                "startDate": None,
                "endDate": None,
                "url": None,
                "summary": None,
                "highlights": None,
            },
            ("location", "startDate", "endDate", "url", "summary", "highlights"),
        ),
        (
            "projects",
            {
                "id": None,
                "name": "Project With Nulls",
                "startDate": None,
                "endDate": None,
                "url": None,
                "description": None,
            },
            ("startDate", "endDate", "url", "description"),
        ),
        (
            "publications",
            {
                "id": None,
                "name": "Pub With Null period",
                "publisher": "P",
                "releaseDate": None,
                "url": None,
                "summary": None,
            },
            ("releaseDate", "url", "summary"),
        ),
        (
            "volunteer",
            {
                "id": None,
                "organization": "VolOrg",
                "location": None,
                "startDate": None,
                "endDate": None,
                "url": None,
                "summary": None,
            },
            ("location", "startDate", "endDate", "url", "summary"),
        ),
        (
            "references",
            {
                "id": None,
                "name": "Ref Person",
                "position": None,
                "url": None,
                "contact": None,
                "reference": None,
            },
            ("position", "url", "contact", "reference"),
        ),
        (
            "awards",
            {
                "id": None,
                "title": "Award Without period",
                "awarder": "Org",
                "date": None,
                "summary": None,
                "url": None,
            },
            ("date", "summary", "url"),
        ),
        (
            "certificates",
            {
                "id": None,
                "name": "Cert Without period",
                "issuer": "Org",
                "date": None,
                "description": None,
                "url": None,
            },
            ("date", "description", "url"),
        ),
    ],
)
async def test_create_accepts_null_for_optional_fields(
    mcp_session: ClientSession,
    sample_resume_id: str,
    section: str,
    item_payload: dict,
    expected_null_keys: tuple[str, ...],
):
    """
    Contract behavior (esp. for smaller/self-hosted models):
    - Optional string fields should accept `null` and be treated as "missing"
      (not raise INVALID_PATCH).
    - The generic section tool should accept list-shaped `items` and return
      a canonical item payload for the created items.
    """
    payload = await call_tool_json(
        mcp_session,
        "resume.section.create",
        {
            "resume_id": sample_resume_id,
            "section": section,
            "items": [item_payload],
            "return_mode": "delta",
        },
    )
    assert payload.get("status") == "success", payload
    resp = payload.get("response")
    assert isinstance(resp, dict), f"Expected delta response dict, got: {resp!r}"
    created_items = resp.get("created") or []
    assert isinstance(created_items, list) and created_items
    created = created_items[0]
    assert isinstance(created, dict)
    assert isinstance(created.get("id"), str) and created["id"]
    for key in expected_null_keys:
        assert (
            created.get(key) is None
        ), f"Expected {key} to be null-ish, got: {created.get(key)!r} in {created!r}"


@pytest.mark.asyncio
async def test_skill_create_allows_null_level_and_preserves_null(
    mcp_session: ClientSession, sample_resume_id: str
):
    payload = await call_tool_json(
        mcp_session,
        "resume.section.create",
        {
            "resume_id": sample_resume_id,
            "section": "skills",
            "items": [
                {
                    "id": None,
                    "name": "Null Level Skill",
                    "level": "Beginner",
                    "rating": None,
                    "keywords": ["x"],
                }
            ],
            "return_mode": "delta",
        },
    )
    assert payload.get("status") == "success"
    resp = payload.get("response")
    assert isinstance(resp, dict)
    created_items = resp.get("created") or []
    assert isinstance(created_items, list) and created_items
    created = created_items[0]
    assert created.get("name") == "Null Level Skill"
    assert (
        created.get("rating") is None
    ), f"Expected rating to remain null, got: {created.get('rating')!r}"


@pytest.mark.asyncio
async def test_language_create_allows_null_level_and_preserves_null(
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
                    "language": "Klingon",
                    "fluency": "Fluent",
                    "level": None,
                }
            ],
            "return_mode": "delta",
        },
    )
    assert payload.get("status") == "success"
    resp = payload.get("response")
    assert isinstance(resp, dict)
    created_items = resp.get("created") or []
    assert isinstance(created_items, list) and created_items
    created = created_items[0]
    assert created.get("language") == "Klingon"
    assert (
        created.get("level") is None
    ), f"Expected level to remain null, got: {created.get('level')!r}"
