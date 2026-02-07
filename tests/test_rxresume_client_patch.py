import asyncio
import json

import httpx

from rxresume_mcp.rxresume_client import RxResumeClient


def test_patch_resume_sets_content_type_and_payload():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["content_type"] = request.headers.get("content-type")
        captured["path"] = request.url.path
        captured["body"] = request.content
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)
    client = RxResumeClient(base_url="http://test", api_key="test-key")
    client.client = httpx.AsyncClient(
        transport=transport,
        base_url=client.base_url,
        headers={"x-api-key": "test-key", "User-Agent": "rxresume-mcp-test"},
    )

    resume_id = "00000000-0000-0000-0000-000000000000"
    patch_ops = [{"op": "replace", "path": "/name", "value": "Updated"}]

    try:
        asyncio.run(client.patch_resume(resume_id, patch_ops=patch_ops))
    finally:
        asyncio.run(client.close())

    assert captured["method"] == "PATCH"
    assert captured["content_type"].startswith("application/json")
    assert captured["path"] == f"/resume/{resume_id}"
    assert json.loads(captured["body"]) == {"id": resume_id, "patch": patch_ops}
