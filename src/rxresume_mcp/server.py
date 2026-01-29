"""
Main module for RxResume MCP server.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from rxresume_mcp import config
from rxresume_mcp.prompts import register_prompts
from rxresume_mcp.resources import register_resources
from rxresume_mcp.tools import app_lifespan, register_tools

mcp = FastMCP(lifespan=app_lifespan, **config.MCP.__dict__)
register_resources(mcp)
register_prompts(mcp)
register_tools(mcp)
