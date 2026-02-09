from rxresume_mcp.tools.resume.sections.field_adapters import WebsiteFieldAdapter
from rxresume_mcp.tools.resume.sections.item_spec import SectionItemPatchTarget


def test_website_field_adapter_apply_defaults():
    adapter = WebsiteFieldAdapter()
    payload = {"website": {"url": "example.com", "label": "Example"}}
    adapter.apply_defaults(payload)
    assert payload["website"] == {"url": "example.com", "label": "Example"}


def test_website_field_adapter_reshape_uses_response_key():
    adapter = WebsiteFieldAdapter(input_key="url", response_key="url")
    payload = {"website": {"url": "https://example.com", "label": ""}}
    result = adapter.reshape(payload)
    assert result["url"] == "https://example.com"


def test_website_field_adapter_build_update_ops_normalizes_url():
    adapter = WebsiteFieldAdapter()
    payload = {"url": "example.com"}
    target = SectionItemPatchTarget(section="projects", item_id="item-1")
    ops = adapter.build_update_ops(payload, target)
    assert {
        "op": "replace",
        "path": "/data/sections/projects/items/id/item-1/website/url",
        "value": "https://example.com",
    } in ops


def test_website_field_adapter_build_update_ops_respects_input_key():
    adapter = WebsiteFieldAdapter(input_key="url", response_key="url")
    payload = {"url": "example.com"}
    target = SectionItemPatchTarget(section="experience", item_id="item-1")
    ops = adapter.build_update_ops(payload, target)
    assert {
        "op": "replace",
        "path": "/data/sections/experience/items/id/item-1/website/url",
        "value": "https://example.com",
    } in ops


def test_website_field_adapter_normalize_input():
    adapter = WebsiteFieldAdapter()
    normalized = adapter.normalize_input("example.com")
    assert normalized == "https://example.com"
