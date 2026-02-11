import pytest

from rxresume_mcp import patch_ops


def test_validate_patch_ops_accepts_from_alias():
    ops = [
        {"op": "add", "path": "/data/basics/name", "value": "Ada"},
        {"op": "move", "from": "/data/basics/name", "path": "/data/basics/headline"},
    ]
    validated = patch_ops.validate_patch_ops(ops)
    assert validated[1]["op"] == "move"
    assert validated[1]["from"] == "/data/basics/name"


def test_validate_patch_ops_normalizes_from_compat_alias():
    ops = [{"op": "copy", "from_": "/data/a", "path": "/data/b"}]
    validated = patch_ops.validate_patch_ops(ops)
    assert validated[0]["op"] == "copy"
    assert validated[0]["from"] == "/data/a"
    assert "from_" not in validated[0]


def test_validate_patch_ops_rejects_unexpected_keys():
    with pytest.raises(ValueError, match="unexpected keys"):
        patch_ops.validate_patch_ops(
            [{"op": "add", "path": "/data/basics/name", "value": "Ada", "extra": 1}]
        )


def test_path_builders_escape_segments():
    item_id = "id/with~slash"
    path = patch_ops.path_section_item("experience", item_id)
    assert path == "/data/sections/experience/items/id/id~1with~0slash"


def test_section_and_custom_section_paths():
    assert (
        patch_ops.path_section_items_append("skills") == "/data/sections/skills/items/-"
    )
    assert (
        patch_ops.path_custom_section_item("custom-1", "item-2")
        == "/data/customSections/id/custom-1/items/id/item-2"
    )
