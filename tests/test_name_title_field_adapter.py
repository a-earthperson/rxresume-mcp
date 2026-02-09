from rxresume_mcp.tools.resume.sections.field_adapters import NameTitleFieldAdapter


def test_name_title_field_adapter_apply_defaults_uses_title():
    adapter = NameTitleFieldAdapter()
    payload = {"name": "Best Paper"}
    adapter.apply_defaults(payload)
    assert payload["title"] == "Best Paper"


def test_name_title_field_adapter_apply_defaults_fallbacks_to_space():
    adapter = NameTitleFieldAdapter()
    payload = {"name": ""}
    adapter.apply_defaults(payload)
    assert payload["title"] == " "


def test_name_title_field_adapter_reshape_uses_response_key():
    adapter = NameTitleFieldAdapter(response_key="name")
    payload = {"title": "Publication A"}
    result = adapter.reshape(payload)
    assert result == {"name": "Publication A"}


def test_name_title_field_adapter_build_update_ops():
    adapter = NameTitleFieldAdapter()
    payload = {"name": "Award A"}
    ops = adapter.build_update_ops("awards", "item-1", payload)
    assert ops == [
        {
            "op": "replace",
            "path": "/data/sections/awards/items/id/item-1/title",
            "value": "Award A",
        }
    ]
