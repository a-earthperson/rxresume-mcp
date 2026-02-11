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
                "description": None,
            },
            ("location", "startDate", "endDate", "url", "description"),
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
      a list of canonical items (not internal keys).
    """
    payload = await call_tool_json(
        mcp_session,
        "resume.section.create",
        {"resume_id": sample_resume_id, "section": section, "items": [item_payload]},
    )
    assert payload.get("status") == "success", payload
    items = payload.get("response")
    assert isinstance(items, list), f"Expected list response, got: {type(items)}: {items!r}"
    assert len(items) >= 1
    created = items[-1]
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
        },
    )
    assert payload.get("status") == "success"
    items = payload["response"]
    assert isinstance(items, list)
    created = next((i for i in items if i.get("name") == "Null Level Skill"), None)
    assert created is not None
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
        },
    )
    assert payload.get("status") == "success"
    items = payload["response"]
    assert isinstance(items, list)
    created = next((i for i in items if i.get("language") == "Klingon"), None)
    assert created is not None
    assert (
        created.get("level") is None
    ), f"Expected level to remain null, got: {created.get('level')!r}"
