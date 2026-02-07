from rxresume_mcp import resources as rx_resources
from rxresume_mcp import tools


def test_schema_dot_path_sections_experience():
    schema = rx_resources._load_resume_schema()
    node = tools._resolve_schema_path(schema, "sections.experience", resolve_refs=False)
    assert isinstance(node, dict)
    assert "properties" in node


def test_schema_dot_path_custom_sections_items():
    schema = rx_resources._load_resume_schema()
    node = tools._resolve_schema_path(schema, "customSections.items", resolve_refs=False)
    assert isinstance(node, dict)
