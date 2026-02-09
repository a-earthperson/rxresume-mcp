import pytest
from mcp import ClientSession

from .conftest import call_tool_json


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "tool_name, item_payload",
    [
        (
            "resume.section.education.item.create",
            {
                "id": None,
                "school": "Test University",
                "degree": "MSc",
                "area": "HCI",
                "grade": None,
                "location": None,
                "period": None,
                "website": None,
                "summary": None,
                "highlights": None,
            },
        ),
        (
            "resume.section.experience.item.create",
            {
                "id": None,
                "company": "Null Period Co",
                "position": "Tester",
                "location": None,
                "period": None,
                "website": None,
                "summary": None,
                "highlights": None,
            },
        ),
        (
            "resume.section.project.item.create",
            {
                "id": None,
                "name": "Project With Nulls",
                "period": None,
                "website": None,
                "summary": None,
                "highlights": None,
            },
        ),
        (
            "resume.section.publication.item.create",
            {
                "id": None,
                "title": "Pub With Null Date",
                "publisher": "P",
                "date": None,
                "website": None,
                "summary": None,
                "highlights": None,
            },
        ),
        (
            "resume.section.volunteer.item.create",
            {
                "id": None,
                "organization": "VolOrg",
                "location": None,
                "period": None,
                "website": None,
                "summary": None,
                "highlights": None,
            },
        ),
        (
            "resume.section.reference.item.create",
            {
                "id": None,
                "name": "Ref Person",
                "position": None,
                "website": None,
                "phone": None,
                "description": None,
            },
        ),
        (
            "resume.section.award.item.create",
            {
                "id": None,
                "title": "Award Without Date",
                "awarder": "Org",
                "date": None,
                "description": None,
                "website": None,
            },
        ),
        (
            "resume.section.certification.item.create",
            {
                "id": None,
                "title": "Cert Without Date",
                "issuer": "Org",
                "date": None,
                "description": None,
                "website": None,
            },
        ),
    ],
)
async def test_create_accepts_null_for_optional_fields(
    mcp_session: ClientSession, empty_resume_id: str, tool_name: str, item_payload: dict
):
    """
    Desired behavior:
    - Optional string fields should accept `null` and be treated as "missing"
      (not raise INVALID_PATCH).
    """
    payload = await call_tool_json(
        mcp_session,
        tool_name,
        {"resume_id": empty_resume_id, "items": item_payload},
    )
    assert payload.get("status") == "success", payload


@pytest.mark.asyncio
async def test_skill_create_allows_null_level_and_preserves_null(
    mcp_session: ClientSession, empty_resume_id: str
):
    payload = await call_tool_json(
        mcp_session,
        "resume.section.skill.item.create",
        {
            "resume_id": empty_resume_id,
            "items": {
                "id": None,
                "name": "Null Level Skill",
                "proficiency": "Beginner",
                "level": None,
                "keywords": ["x"],
            },
        },
    )
    assert payload.get("status") == "success"
    items = payload["response"]
    created = next((i for i in items if i.get("name") == "Null Level Skill"), None)
    assert created is not None
    assert (
        created.get("level") is None
    ), f"Expected level to remain null, got: {created.get('level')!r}"


@pytest.mark.asyncio
async def test_language_create_allows_null_level_and_preserves_null(
    mcp_session: ClientSession, empty_resume_id: str
):
    payload = await call_tool_json(
        mcp_session,
        "resume.section.language.item.create",
        {
            "resume_id": empty_resume_id,
            "items": {
                "id": None,
                "language": "Klingon",
                "fluency": "Fluent",
                "level": None,
            },
        },
    )
    assert payload.get("status") == "success"
    items = payload["response"]
    created = next(
        (
            i
            for i in items
            if i.get("language") == "Klingon" or i.get("name") == "Klingon"
        ),
        None,
    )
    assert created is not None
    assert (
        created.get("level") is None
    ), f"Expected level to remain null, got: {created.get('level')!r}"
