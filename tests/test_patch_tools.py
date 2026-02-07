import uuid

from rxresume_mcp import tools


def test_build_summary_minimal_and_full():
    ops = [{"op": "add", "path": "/data/basics/name", "value": "Ada"}]
    summary = tools._build_summary(
        "resume-1",
        ops,
        ["new-id"],
        include_result=False,
        result={"id": "resume-1"},
    )
    assert summary["resume_id"] == "resume-1"
    assert summary["applied_ops"] == ops
    assert summary["changed_paths"] == ["/data/basics/name"]
    assert "resume" not in summary

    summary_full = tools._build_summary(
        "resume-1",
        ops,
        [],
        include_result=True,
        result={"id": "resume-1"},
    )
    assert summary_full["resume"] == {"id": "resume-1"}


def test_ensure_item_id_generates_id(monkeypatch):
    created = []
    item = {"company": "Acme"}
    fixed = uuid.UUID("00000000-0000-0000-0000-000000000001")
    monkeypatch.setattr(tools.uuid, "uuid4", lambda: fixed)
    result = tools._ensure_item_id(item, created)
    assert result["id"] == str(fixed)
    assert created == [str(fixed)]


def test_custom_section_exists():
    data = {"customSections": [{"id": "cs-1"}, {"id": "cs-2"}]}
    assert tools._custom_section_exists(data, "cs-2") is True
    assert tools._custom_section_exists(data, "cs-3") is False
