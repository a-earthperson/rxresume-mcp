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
                "school": "Test University",
                "degree": "MSc",
                "area": "HCI",
                "grade": None,
                "location": None,
                "period": None,
                "url": None,
                "description": None,
            },
            ("grade", "location", "period", "url", "description"),
        ),
        (
            "experience",
            {
                "id": None,
                "name": "Null Period Co",
                "position": "Tester",
                "location": None,
                "period": None,
                "url": None,
                "description": None,
            },
            ("location", "period", "url", "description"),
        ),
        (
            "projects",
            {
                "id": None,
                "name": "Project With Nulls",
                "period": None,
                "url": None,
                "description": None,
            },
            ("period", "url", "description"),
        ),
        (
            "publications",
            {
                "id": None,
                "name": "Pub With Null period",
                "publisher": "P",
                "period": None,
                "url": None,
                "description": None,
            },
            ("period", "url", "description"),
        ),
        (
            "volunteer",
            {
                "id": None,
                "name": "VolOrg",
                "location": None,
                "period": None,
                "url": None,
                "description": None,
            },
            ("location", "period", "url", "description"),
        ),
        (
            "references",
            {
                "id": None,
                "name": "Ref Person",
                "position": None,
                "url": None,
                "contact": None,
                "description": None,
            },
            ("position", "url", "contact", "description"),
        ),
        (
            "awards",
            {
                "id": None,
                "name": "Award Without period",
                "awarder": "Org",
                "period": None,
                "description": None,
                "url": None,
            },
            ("period", "description", "url"),
        ),
        (
            "certifications",
            {
                "id": None,
                "name": "Cert Without period",
                "issuer": "Org",
                "period": None,
                "description": None,
                "url": None,
            },
            ("period", "description", "url"),
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
                    "proficiency": "Beginner",
                    "level": None,
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
        created.get("level") is None
    ), f"Expected level to remain null, got: {created.get('level')!r}"


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
                    "name": "Klingon",
                    "proficiency": "Fluent",
                    "level": None,
                }
            ],
        },
    )
    assert payload.get("status") == "success"
    items = payload["response"]
    assert isinstance(items, list)
    created = next((i for i in items if i.get("name") == "Klingon"), None)
    assert created is not None
    assert (
        created.get("level") is None
    ), f"Expected level to remain null, got: {created.get('level')!r}"
