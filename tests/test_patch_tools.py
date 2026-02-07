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


def test_auto_id_patch_ops_injects_for_items_and_custom_fields(monkeypatch):
    first = uuid.UUID("00000000-0000-0000-0000-000000000002")
    second = uuid.UUID("00000000-0000-0000-0000-000000000003")
    generated = [first, second]
    monkeypatch.setattr(tools.uuid, "uuid4", lambda: generated.pop(0))
    ops = [
        {
            "op": "add",
            "path": "/data/sections/skills/items/-",
            "value": {"name": "TypeScript"},
        },
        {
            "op": "add",
            "path": "/data/basics/customFields/-",
            "value": {"label": "GitHub", "value": "https://github.com/octocat"},
        },
    ]
    normalized, created_ids = tools._auto_id_patch_ops(ops)
    assert created_ids == [str(first), str(second)]
    assert normalized[0]["value"]["id"] == str(first)
    assert normalized[1]["value"]["id"] == str(second)
