"""
Configuration module for RxResume MCP server.
"""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from typing import Literal

DEFAULT_DOMAIN = "http://localhost:3000"
DEFAULT_TIMEOUT = 30
DEFAULT_USER_AGENT = "rxresume-mcp/0.1.0"


def _normalize_path(path: str) -> str:
    if not path.startswith("/"):
        return f"/{path}"
    return path


def _normalize_base_url(value: str) -> str:
    if not value:
        return value
    return value.rstrip("/")


def _build_base_url(domain: str) -> str:
    domain = domain.strip().rstrip("/")
    if not domain:
        return ""
    if domain.endswith("/api/openapi"):
        return domain
    return f"{domain}/api/openapi"


def _get_int_env(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class RxResumeSettings:
    """Settings for connecting to the Reactive Resume API server."""

    base_url: str
    api_key: str
    timeout: int = DEFAULT_TIMEOUT
    user_agent: str = DEFAULT_USER_AGENT

    @property
    def is_configured(self) -> bool:
        return bool(self.base_url)


@dataclass(frozen=True)
class MCPSettings:
    """Settings for MCP transport and HTTP server."""

    name: str = "RxResume MCP Server"
    website_url: str | None = None
    host: str = "127.0.0.1"
    port: int = 8001
    mount_path: str = "/"
    sse_path: str = "/sse"
    message_path: str = "/messages/"
    streamable_http_path: str = "/mcp"
    json_response: bool = True
    stateless_http: bool = True
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "DEBUG"
    debug: bool = True

    @property
    def http_url(self) -> str:
        return f"http://{self.host}:{self.port}{self.mount_path}"


def _resolve_rxresume_settings() -> RxResumeSettings:
    base_url_env = _normalize_base_url(os.getenv("RXRESUME_BASE_URL", "").strip())
    domain_env = os.getenv("RXRESUME_DOMAIN", "").strip()

    if base_url_env:
        base_url = base_url_env
    else:
        domain = domain_env or DEFAULT_DOMAIN
        base_url = _build_base_url(domain)

    api_key = os.getenv("RXRESUME_API_KEY", "").strip()
    timeout = _get_int_env("RXRESUME_TIMEOUT", DEFAULT_TIMEOUT)
    user_agent = os.getenv("RXRESUME_USER_AGENT", DEFAULT_USER_AGENT).strip()

    return RxResumeSettings(
        base_url=base_url,
        api_key=api_key,
        timeout=timeout,
        user_agent=user_agent or DEFAULT_USER_AGENT,
    )


def parse_args():
    """Parse command line arguments for MCP server."""
    parser = argparse.ArgumentParser(description="RxResume MCP Server")
    parser.add_argument(
        "--mcp-transport",
        choices=["stdio", "sse", "streamable-http"],
        default="streamable-http",
        help="MCP transport (default: streamable-http)",
    )
    parser.add_argument(
        "--mcp-http-host",
        default=MCPSettings.host,
        help=f"MCP HTTP host (default: {MCPSettings.host})",
    )
    parser.add_argument(
        "--mcp-http-port",
        type=int,
        default=MCPSettings.port,
        help=f"MCP HTTP port (default: {MCPSettings.port})",
    )
    parser.add_argument(
        "--mcp-http-path",
        type=str,
        default="/",
        help=(f"MCP HTTP base/mount path (default: {MCPSettings.mount_path})"),
    )
    parser.add_argument(
        "--mcp-http-stateless",
        action="store_true",
        help="Enable stateless HTTP mode (new session per request)",
    )
    parser.add_argument(
        "--mcp-http-json-response",
        action="store_true",
        help="Return JSON responses instead of SSE for HTTP",
    )
    return parser.parse_args()


args = parse_args()

RXRESUME = _resolve_rxresume_settings()

TRANSPORT = args.mcp_transport

MCP = MCPSettings(
    host=args.mcp_http_host,
    port=args.mcp_http_port,
    mount_path=_normalize_path(args.mcp_http_path),
    stateless_http=args.mcp_http_stateless,
    json_response=args.mcp_http_json_response,
)
