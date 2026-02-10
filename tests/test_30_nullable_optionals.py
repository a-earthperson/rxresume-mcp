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
                "url": None,
                "description": None,
            },
        ),
        (
            "resume.section.experience.item.create",
            {
                "id": None,
                "name": "Null Period Co",
                "position": "Tester",
                "location": None,
                "period": None,
                "url": None,
                "description": None,
            },
        ),
        (
            "resume.section.project.item.create",
            {
                "id": None,
                "name": "Project With Nulls",
                "period": None,
                "url": None,
                "description": None,
            },
        ),
        (
            "resume.section.publication.item.create",
            {
                "id": None,
                "name": "Pub With Null period",
                "publisher": "P",
                "period": None,
                "url": None,
                "description": None,
            },
        ),
        (
            "resume.section.volunteer.item.create",
            {
                "id": None,
                "name": "VolOrg",
                "location": None,
                "period": None,
                "url": None,
                "description": None,
            },
        ),
        (
            "resume.section.reference.item.create",
            {
                "id": None,
                "name": "Ref Person",
                "position": None,
                "url": None,
                "contact": None,
                "description": None,
            },
        ),
        (
            "resume.section.award.item.create",
            {
                "id": None,
                "name": "Award Without period",
                "awarder": "Org",
                "period": None,
                "description": None,
                "url": None,
            },
        ),
        (
            "resume.section.certification.item.create",
            {
                "id": None,
                "name": "Cert Without period",
                "issuer": "Org",
                "period": None,
                "description": None,
                "url": None,
            },
        ),
    ],
)
async def test_create_accepts_null_for_optional_fields(
    mcp_session: ClientSession,
    sample_resume_id: str,
    tool_name: str,
    item_payload: dict,
):
    """
    Desired behavior:
    - Optional string fields should accept `null` and be treated as "missing"
      (not raise INVALID_PATCH).
    """
    payload = await call_tool_json(
        mcp_session,
        tool_name,
        {"resume_id": sample_resume_id, "items": item_payload},
    )
    assert payload.get("status") == "success", payload


@pytest.mark.asyncio
async def test_skill_create_allows_null_level_and_preserves_null(
    mcp_session: ClientSession, sample_resume_id: str
):
    payload = await call_tool_json(
        mcp_session,
        "resume.section.skill.item.create",
        {
            "resume_id": sample_resume_id,
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
    mcp_session: ClientSession, sample_resume_id: str
):
    payload = await call_tool_json(
        mcp_session,
        "resume.section.language.item.create",
        {
            "resume_id": sample_resume_id,
            "items": {
                "id": None,
                "name": "Klingon",
                "proficiency": "Fluent",
                "level": None,
            },
        },
    )
    assert payload.get("status") == "success"
    items = payload["response"]
    created = next((i for i in items if i.get("name") == "Klingon"), None)
    assert created is not None
    assert (
        created.get("level") is None
    ), f"Expected level to remain null, got: {created.get('level')!r}"
