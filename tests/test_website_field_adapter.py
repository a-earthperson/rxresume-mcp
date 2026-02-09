from rxresume_mcp.tools.resume.sections.field_adapters import WebsiteFieldAdapter


def test_website_field_adapter_apply_defaults():
    adapter = WebsiteFieldAdapter()
    payload = {"website": {"url": "example.com", "label": "Example"}}
    adapter.apply_defaults(payload)
    assert payload["website"] == {"url": "example.com", "label": "Example"}


def test_website_field_adapter_reshape_uses_response_key():
    adapter = WebsiteFieldAdapter(input_key="url", response_key="url")
    payload = {"website": {"url": "https://example.com", "label": ""}}
    result = adapter.reshape(payload)
    assert result["url"]["url"] == "https://example.com"


def test_website_field_adapter_build_update_ops_normalizes_url():
    adapter = WebsiteFieldAdapter()
    payload = {"website": {"url": "example.com", "label": "Example"}}
    ops = adapter.build_update_ops("projects", "item-1", payload)
    assert {
        "op": "replace",
        "path": "/data/sections/projects/items/id/item-1/website/url",
        "value": "https://example.com",
    } in ops
    assert {
        "op": "replace",
        "path": "/data/sections/projects/items/id/item-1/website/label",
        "value": "Example",
    } in ops


def test_website_field_adapter_build_update_ops_respects_input_key():
    adapter = WebsiteFieldAdapter(input_key="url", response_key="url")
    payload = {"url": "example.com"}
    ops = adapter.build_update_ops("experience", "item-1", payload)
    assert {
        "op": "replace",
        "path": "/data/sections/experience/items/id/item-1/website/url",
        "value": "https://example.com",
    } in ops


def test_website_field_adapter_normalize_input():
    adapter = WebsiteFieldAdapter()
    normalized = adapter.normalize_input("example.com")
    assert normalized == {"url": "https://example.com", "label": ""}
