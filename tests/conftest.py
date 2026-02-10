import json
import os
import pathlib
import sys
from pathlib import Path
import re
import uuid
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Optional, Tuple

import httpx
import pytest
import pytest_asyncio

from mcp import ClientSession, types
from mcp.client.streamable_http import streamable_http_client

pytest_plugins = ("pytest_asyncio",)


UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
_UPSTREAM_DIAGNOSTICS_PRINTED = False


@dataclass(frozen=True)
class ServerConfig:
    name: str
    url: str
    authorization: Optional[str]


def _load_servers_json() -> dict:
    path = os.environ.get("MCP_SERVERS_JSON")
    if path:
        p = pathlib.Path(path)
    else:
        repo_root = pathlib.Path(__file__).resolve().parents[1]
        candidates = (
            repo_root / "servers.json",
            repo_root / "tests" / "servers.json",
        )
        p = next(
            (candidate for candidate in candidates if candidate.exists()), candidates[0]
        )

    if not p.exists():
        raise RuntimeError(
            f"servers.json not found at {p}. "
            "Set MCP_SERVERS_JSON or place servers.json in the repo root."
        )
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


def _pick_server(mcp_servers: dict) -> Tuple[str, dict]:
    preferred = os.environ.get("MCP_SERVER_NAME")
    if preferred:
        if preferred not in mcp_servers:
            raise RuntimeError(
                f"MCP_SERVER_NAME={preferred!r} not found. Available: {list(mcp_servers.keys())}"
            )
        return preferred, mcp_servers[preferred]

    # common names
    for k in ("resume_tool", "resume-tool", "resumeTool"):
        if k in mcp_servers:
            return k, mcp_servers[k]

    if len(mcp_servers) == 1:
        k = next(iter(mcp_servers.keys()))
        return k, mcp_servers[k]

    raise RuntimeError(
        f"Unable to choose server from servers.json. Available: {list(mcp_servers.keys())}. "
        "Set MCP_SERVER_NAME."
    )


def load_server_config() -> ServerConfig:
    data = _load_servers_json()
    if "mcpServers" not in data or not isinstance(data["mcpServers"], dict):
        raise RuntimeError(
            "servers.json must contain top-level key 'mcpServers' as an object."
        )

    name, entry = _pick_server(data["mcpServers"])
    url = entry.get("url")
    if not url:
        raise RuntimeError(f"Server entry {name!r} missing 'url'")
    auth = entry.get("authorization") or entry.get("Authorization")  # tolerate variants
    return ServerConfig(name=name, url=url, authorization=auth)


def _extract_structured_payload(result: Any) -> Any:
    # Newer SDK: structured_content; older: structuredContent
    structured = getattr(result, "structured_content", None)
    if structured is None:
        structured = getattr(result, "structuredContent", None)
    if structured is not None:
        return structured

    # Fall back: attempt to parse JSON from text blocks
    content = getattr(result, "content", None) or []
    for block in content:
        if isinstance(block, types.TextContent):
            text = (block.text or "").strip()
            if not text:
                continue
            try:
                return json.loads(text)
            except Exception:
                # not JSON, keep going
                pass

    # Final fallback: return raw text
    for block in content:
        if isinstance(block, types.TextContent):
            return block.text
    return None


async def call_tool_json(
    session: ClientSession, tool_name: str, arguments: dict
) -> Any:
    "Call a tool and return the structured JSON payload if possible."
    result = await session.call_tool(tool_name, arguments=arguments)
    payload = _extract_structured_payload(result)
    if payload is None:
        raise RuntimeError(
            f"Tool {tool_name} returned no parseable payload: {result!r}"
        )
    # Some MCP servers wrap tool payloads as {"result": {...}}.
    if isinstance(payload, dict) and "result" in payload and len(payload) == 1:
        inner = payload.get("result")
        if inner is not None:
            payload = inner

    # Normalize string payloads into a structured error shape so tests
    # can assert on payload["status"] consistently.
    if isinstance(payload, str):
        text = payload.strip()
        if text:
            try:
                parsed = json.loads(text)
                if isinstance(parsed, dict):
                    if "result" in parsed and len(parsed) == 1 and isinstance(parsed["result"], dict):
                        return parsed["result"]
                    return parsed
            except Exception:
                pass
        return {"status": "error", "error": text or "<empty text response>"}

    return payload


def _sanitize_for_diagnostics(value: Any, *, depth: int = 0) -> Any:
    if depth > 5:
        return "<max-depth>"
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            lower_key = str(key).lower()
            if lower_key in {"authorization", "x-api-key", "api_key", "apikey"}:
                sanitized[str(key)] = "<redacted>"
                continue
            sanitized[str(key)] = _sanitize_for_diagnostics(item, depth=depth + 1)
        return sanitized
    if isinstance(value, list):
        if len(value) > 10:
            head = [_sanitize_for_diagnostics(item, depth=depth + 1) for item in value[:10]]
            head.append(f"<truncated {len(value) - 10} items>")
            return head
        return [_sanitize_for_diagnostics(item, depth=depth + 1) for item in value]
    if isinstance(value, str):
        if len(value) > 500:
            return value[:500] + "...<truncated>"
        return value
    return value


async def _print_upstream_diagnostics_once(
    session: ClientSession, create_payload: Any
) -> None:
    global _UPSTREAM_DIAGNOSTICS_PRINTED
    if _UPSTREAM_DIAGNOSTICS_PRINTED:
        return
    if os.getenv("MCP_TEST_PRINT_UPSTREAM_DIAGNOSTICS", "1").strip() in {"0", "false", "False"}:
        _UPSTREAM_DIAGNOSTICS_PRINTED = True
        return

    try:
        list_payload = await call_tool_json(
            session,
            "resume.doc.list",
            {"tags": [], "sort": None},
        )
    except Exception as exc:
        list_payload = {"diagnostic_error": str(exc)}

    create_sanitized = _sanitize_for_diagnostics(create_payload)
    list_sanitized = _sanitize_for_diagnostics(list_payload)
    print(
        "[pytest-upstream-diagnostics] create payload:",
        json.dumps(create_sanitized, ensure_ascii=True, sort_keys=True),
    )
    print(
        "[pytest-upstream-diagnostics] list payload:",
        json.dumps(list_sanitized, ensure_ascii=True, sort_keys=True),
    )
    _UPSTREAM_DIAGNOSTICS_PRINTED = True


def extract_resume_id(create_payload: Any) -> str:
    """
    Supports current server shape:
      {"status":"success","response":{"resume_id":"...","resume":{...}}}
    and future compact shapes such as:
      {"status":"success","response":{"id":"..."}}
    """
    if not isinstance(create_payload, dict):
        raise AssertionError(f"Expected dict payload, got: {type(create_payload)}")

    if create_payload.get("status") != "success":
        raise AssertionError(f"Expected success but got: {create_payload}")

    resp = create_payload.get("response")
    if isinstance(resp, dict):
        rid = resp.get("resume_id") or resp.get("id")
        if rid:
            return rid

    # Some implementations might return {"response": "<id>"}
    if isinstance(resp, str) and resp:
        return resp

    raise AssertionError(f"Unable to extract resume_id from payload: {create_payload}")


@pytest_asyncio.fixture
async def mcp_session() -> ClientSession:
    """
    Stateless streamable-http test client with fail-fast preflight.
    """
    cfg = load_server_config()
    connect_timeout_s = float(os.environ.get("MCP_CONNECT_TIMEOUT_S", "8"))
    headers = {"Authorization": cfg.authorization} if cfg.authorization else {}
    timeout = httpx.Timeout(connect_timeout_s, connect=connect_timeout_s)

    async def _preflight() -> None:
        async with httpx.AsyncClient(headers=headers, timeout=timeout) as probe_client:
            try:
                probe = await probe_client.post(
                    cfg.url,
                    json={
                        "jsonrpc": "2.0",
                        "id": "pytest-preflight",
                        "method": "initialize",
                        "params": {
                            "protocolVersion": "2024-11-05",
                            "capabilities": {},
                            "clientInfo": {
                                "name": "pytest-preflight",
                                "version": "0.1.0",
                            },
                        },
                    },
                    headers={"Accept": "application/json, text/event-stream"},
                )
            except httpx.TimeoutException as exc:
                raise RuntimeError(
                    f"Timeout reaching MCP endpoint within {connect_timeout_s:.1f}s: {cfg.url}"
                ) from exc
            except httpx.HTTPError as exc:
                raise RuntimeError(
                    f"HTTP transport error while reaching MCP endpoint: {cfg.url}"
                ) from exc

        if probe.status_code in (401, 403):
            detail = (probe.text or "").strip()
            detail = detail[:240] + ("..." if len(detail) > 240 else "")
            raise RuntimeError(
                f"MCP endpoint rejected authorization with HTTP {probe.status_code} for {cfg.url}. "
                f"Response: {detail or '<empty body>'}"
            )
        if probe.status_code >= 400:
            detail = (probe.text or "").strip()
            detail = detail[:240] + ("..." if len(detail) > 240 else "")
            raise RuntimeError(
                f"MCP endpoint preflight failed with HTTP {probe.status_code} for {cfg.url}. "
                f"Response: {detail or '<empty body>'}"
            )

    @dataclass
    class StatelessMCPSession:
        url: str
        headers: dict[str, str]
        timeout: httpx.Timeout

        async def _request(self, op: Callable[[ClientSession], Awaitable[Any]]) -> Any:
            async with httpx.AsyncClient(
                headers=self.headers, timeout=self.timeout
            ) as http_client:
                async with streamable_http_client(
                    self.url, http_client=http_client
                ) as (read, write, _):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        return await op(session)

        async def list_tools(self) -> Any:
            return await self._request(lambda session: session.list_tools())

        async def call_tool(self, tool_name: str, arguments: dict) -> Any:
            return await self._request(
                lambda session: session.call_tool(tool_name, arguments=arguments)
            )

    await _preflight()
    return StatelessMCPSession(url=cfg.url, headers=headers, timeout=timeout)


@pytest.fixture
def unique_slug() -> str:
    return f"pytest-{uuid.uuid4().hex}"


@pytest_asyncio.fixture
async def empty_resume_id(mcp_session: ClientSession, unique_slug: str) -> str:
    payload = await call_tool_json(
        mcp_session,
        "resume.doc.create",
        {
            "name": "Pytest Empty Resume",
            "slug": unique_slug,
            "tags": ["pytest", "contract"],
            "with_sample_data": False,
        },
    )
    await _print_upstream_diagnostics_once(mcp_session, payload)
    rid = extract_resume_id(payload)
    try:
        yield rid
    finally:
        # best-effort cleanup
        try:
            await call_tool_json(mcp_session, "resume.doc.delete", {"resume_id": rid})
        except Exception:
            pass


@pytest_asyncio.fixture
async def sample_resume_id(mcp_session: ClientSession, unique_slug: str) -> str:
    payload = await call_tool_json(
        mcp_session,
        "resume.doc.create",
        {
            "name": "Pytest Sample Resume",
            "slug": unique_slug,
            "tags": ["pytest", "contract", "sample"],
            "with_sample_data": True,
        },
    )
    await _print_upstream_diagnostics_once(mcp_session, payload)
    rid = extract_resume_id(payload)
    try:
        yield rid
    finally:
        try:
            await call_tool_json(mcp_session, "resume.doc.delete", {"resume_id": rid})
        except Exception:
            pass


def _ensure_local_src_on_path() -> None:
    tests_dir = Path(__file__).resolve().parent
    repo_root = tests_dir.parent
    src_dir = repo_root / "src"
    src_path = str(src_dir)
    if src_path not in sys.path:
        sys.path.insert(0, src_path)


_ensure_local_src_on_path()
