import pytest
from mcp import ClientSession

from .conftest import load_server_config


@pytest.mark.asyncio
async def test_fail_fast_can_initialize_session(mcp_session: ClientSession):
    # If we got here, initialize succeeded.
    # Also sanity-check that the server advertises tools.
    tools = await mcp_session.list_tools()
    assert tools.tools, "Expected at least one tool exposed by the MCP server."


def test_servers_json_is_loadable():
    cfg = load_server_config()
    assert cfg.url.startswith("http"), "URL must be http(s)"
