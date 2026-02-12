import pytest
from mcp import ClientSession

from .conftest import call_tool_json


def _assert_summary_section(section: dict, expected_ids: list[str]) -> None:
    assert isinstance(section, dict)
    assert "ids" in section and "count" in section, f"Bad section summary: {section!r}"
    ids = section.get("ids")
    count = section.get("count")
    assert isinstance(ids, list), f"ids must be a list, got: {ids!r}"
    assert isinstance(count, int), f"count must be an int, got: {count!r}"
    assert count == len(ids), f"count {count} != len(ids) {len(ids)}"
    assert set(ids) == set(expected_ids)


@pytest.mark.asyncio
async def test_doc_get_summary_shapes_and_counts(
    mcp_session: ClientSession, sample_resume_id: str
):
    basics_payload = await call_tool_json(
        mcp_session,
        "resume.basics.update",
        {
            "resume_id": sample_resume_id,
            "payload": {
                "name": "Summary Name",
                "profiles": [
                    {"network": "GitHub", "username": "example", "url": "https://x.y"}
                ],
            },
        },
    )
    assert basics_payload.get("status") == "success", basics_payload
    basics = basics_payload.get("response") or {}
    profile_ids = [p.get("id") for p in (basics.get("profiles") or []) if p.get("id")]
    assert profile_ids, "Expected profile ids to be assigned"

    work_payload = await call_tool_json(
        mcp_session,
        "resume.section.create",
        {
            "resume_id": sample_resume_id,
            "section": "work",
            "items": [{"id": None, "name": "Summary Work", "summary": "Seed"}],
            "return_mode": "delta",
        },
    )
    assert work_payload.get("status") == "success", work_payload
    work_ids = work_payload.get("response", {}).get("ids", {}).get("created") or []
    assert work_ids, "Expected work ids to be returned"

    skills_payload = await call_tool_json(
        mcp_session,
        "resume.section.create",
        {
            "resume_id": sample_resume_id,
            "section": "skills",
            "items": [{"id": None, "name": "Python", "keywords": ["typing"]}],
            "return_mode": "delta",
        },
    )
    assert skills_payload.get("status") == "success", skills_payload
    skill_ids = skills_payload.get("response", {}).get("ids", {}).get("created") or []
    assert skill_ids, "Expected skill ids to be returned"

    summary_payload = await call_tool_json(
        mcp_session,
        "resume.doc.get",
        {"resume_id": sample_resume_id, "summary": True},
    )
    assert summary_payload.get("status") == "success", summary_payload
    resume = summary_payload.get("response") or {}
    sections = resume.get("sections") or {}

    basics_summary = sections.get("basics") or {}
    assert basics_summary.get("name") == "Summary Name"
    assert "headline" not in basics_summary
    assert "website" not in basics_summary
    assert "label" in basics_summary
    assert "url" in basics_summary
    _assert_summary_section(basics_summary.get("profiles"), profile_ids)
    _assert_summary_section(sections.get("work"), work_ids)
    _assert_summary_section(sections.get("skills"), skill_ids)
