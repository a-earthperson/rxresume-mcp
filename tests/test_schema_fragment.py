from rxresume_mcp.rxresume_client import _load_resume_schema
from rxresume_mcp import tools


def test_schema_dot_path_sections_experience():
    schema = _load_resume_schema()
    node = tools._resolve_schema_path(schema, "sections.experience", resolve_refs=False)
    assert isinstance(node, dict)
    assert "properties" in node


def test_schema_dot_path_custom_sections_items():
    schema = _load_resume_schema()
    node = tools._resolve_schema_path(schema, "customSections.items", resolve_refs=False)
    assert isinstance(node, dict)
