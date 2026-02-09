import pytest

from rxresume_mcp import client


def _base_section(title: str) -> dict:
    return {"title": title, "columns": 1, "hidden": False, "items": []}


def _minimal_resume_data() -> dict:
    return {
        "picture": {
            "hidden": False,
            "url": "https://example.com/photo.png",
            "size": 128,
            "rotation": 0,
            "aspectRatio": 1.0,
            "borderRadius": 0,
            "borderColor": "rgba(0, 0, 0, 1)",
            "borderWidth": 0,
            "shadowColor": "rgba(0, 0, 0, 0)",
            "shadowWidth": 0,
        },
        "basics": {},
        "summary": {
            "title": "Summary",
            "columns": 1,
            "hidden": False,
            "content": "<p>Summary</p>",
        },
        "sections": {
            "profiles": _base_section("Profiles"),
            "experience": _base_section("Experience"),
            "education": _base_section("Education"),
            "projects": _base_section("Projects"),
            "skills": _base_section("Skills"),
            "languages": _base_section("Languages"),
            "interests": _base_section("Interests"),
            "awards": _base_section("Awards"),
            "certifications": _base_section("Certifications"),
            "publications": _base_section("Publications"),
            "volunteer": _base_section("Volunteer"),
            "references": _base_section("References"),
        },
        "customSections": [],
        "metadata": {
            "template": "onyx",
            "layout": {"sidebarWidth": 35, "pages": []},
            "css": {"enabled": False, "value": ""},
            "page": {
                "gapX": 0,
                "gapY": 0,
                "marginX": 0,
                "marginY": 0,
                "format": "a4",
                "locale": "en-US",
                "hideIcons": False,
            },
            "design": {
                "level": {"icon": "", "type": "hidden"},
                "colors": {
                    "primary": "rgba(0, 0, 0, 1)",
                    "text": "rgba(0, 0, 0, 1)",
                    "background": "rgba(255, 255, 255, 1)",
                },
            },
            "typography": {
                "body": {
                    "fontFamily": "Inter",
                    "fontWeights": ["400"],
                    "fontSize": 11,
                    "lineHeight": 1.5,
                },
                "heading": {
                    "fontFamily": "Inter",
                    "fontWeights": ["600"],
                    "fontSize": 14,
                    "lineHeight": 1.3,
                },
            },
            "notes": "",
        },
    }


def test_validate_resume_data_allows_missing_basics_fields():
    data = _minimal_resume_data()
    data["basics"] = {}
    client._validate_resume_data(data)


def test_validate_resume_data_still_requires_basics_object():
    data = _minimal_resume_data()
    data.pop("basics")
    with pytest.raises(ValueError, match="basics"):
        client._validate_resume_data(data)
