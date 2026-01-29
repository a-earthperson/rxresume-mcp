"""
Configuration module for RxResume MCP server.
"""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from typing import Literal

from . import DEFAULT_USER_AGENT


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


def _get_env_value(*names: str, default: str = "") -> str:
    for name in names:
        raw = os.getenv(name)
        if raw is not None:
            value = raw.strip()
            if value:
                return value
    return default


def _parse_int(value: str, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _parse_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    normalized = value.strip().lower()
    if not normalized:
        return default
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    return default


@dataclass(frozen=True)
class RxResumeSettings:
    """Settings for connecting to the Reactive Resume API server."""

    base_url: str = "https://rxresu.me"
    api_key: str = ""
    timeout: int = 30
    user_agent: str = DEFAULT_USER_AGENT

    @property
    def is_configured(self) -> bool:
        return bool(self.base_url)


@dataclass(frozen=True)
class MCPSettings:
    """Settings for MCP transport and HTTP server."""

    name: str = "RxResume MCP Server"
    website_url: str | None = None
    host: str = "localhost"
    port: int = 8000
    mount_path: str = "/"
    sse_path: str = "/sse"
    message_path: str = "/messages/"
    streamable_http_path: str = "/mcp"
    json_response: bool = False
    stateless_http: bool = False
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "DEBUG"
    debug: bool = True

    @property
    def http_url(self) -> str:
        return f"http://{self.host}:{self.port}{self.mount_path}"


@dataclass(frozen=True)
class MCPTransportSettings:
    """Defaults for MCP transport selection."""

    transport: Literal["stdio", "sse", "streamable-http"] = "streamable-http"


def _resolve_rxresume_settings(args: argparse.Namespace) -> RxResumeSettings:
    base_url = _build_base_url(args.app_url.strip())
    api_key = args.app_api_key.strip()
    timeout = args.app_api_timeout
    user_agent = args.app_api_user_agent.strip() or RxResumeSettings.user_agent
    return RxResumeSettings(
        base_url=base_url,
        api_key=api_key,
        timeout=timeout,
        user_agent=user_agent,
    )


def parse_args():
    """Parse command line arguments for MCP server."""
    app_url_default = _get_env_value("APP_URL", default=RxResumeSettings.base_url)
    app_api_key_default = _get_env_value(
        "REST_API_KEY", default=RxResumeSettings.api_key
    )
    app_api_user_agent_default = _get_env_value(
        "REST_API_USER_AGENT", default=RxResumeSettings.user_agent
    )
    app_api_timeout_default = _parse_int(
        _get_env_value("REST_API_TIMEOUT", default=str(RxResumeSettings.timeout)),
        RxResumeSettings.timeout,
    )

    mcp_transport_default = _get_env_value(
        "MCP_TRANSPORT", default=MCPTransportSettings.transport
    )
    if mcp_transport_default not in {"stdio", "sse", "streamable-http"}:
        mcp_transport_default = MCPTransportSettings.transport

    mcp_http_host_default = _get_env_value("MCP_HTTP_HOST", default=MCPSettings.host)
    mcp_http_port_default = _parse_int(
        _get_env_value("MCP_HTTP_PORT", default=str(MCPSettings.port)),
        MCPSettings.port,
    )
    mcp_http_path_default = _get_env_value(
        "MCP_HTTP_PATH", "MCP_STREAMABLE_HTTP_PATH", default=MCPSettings.mount_path
    )
    mcp_http_stateless_default = _parse_bool(
        _get_env_value("MCP_HTTP_STATELESS", "MCP_STATELESS_HTTP", default=""),
        MCPSettings.stateless_http,
    )
    mcp_http_json_response_default = _parse_bool(
        _get_env_value("MCP_HTTP_JSON_RESPONSE", "MCP_JSON_RESPONSE", default=""),
        MCPSettings.json_response,
    )
    mcp_log_level_default = _get_env_value(
        "MCP_LOG_LEVEL", default=MCPSettings.log_level
    ).upper()
    if mcp_log_level_default not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
        mcp_log_level_default = MCPSettings.log_level
    mcp_debug_default = _parse_bool(
        _get_env_value("MCP_DEBUG", default=""), MCPSettings.debug
    )

    parser = argparse.ArgumentParser(description="RxResume MCP Server")
    parser.add_argument(
        "--app-url",
        type=str,
        default=app_url_default,
        help="Reactive Resume API URL (default: APP_URL or https://rxresu.me)",
    )
    parser.add_argument(
        "--app-api-key",
        type=str,
        default=app_api_key_default,
        help="Reactive Resume API key (default: environment variable REST_API_KEY)",
    )
    parser.add_argument(
        "--app-api-user-agent",
        type=str,
        default=app_api_user_agent_default,
        help=(
            "Reactive Resume API user agent (default: environment variable "
            "REST_API_USER_AGENT)"
        ),
    )
    parser.add_argument(
        "--app-api-timeout",
        type=int,
        default=app_api_timeout_default,
        help=(
            "Reactive Resume API timeout in seconds (default: environment "
            "variable REST_API_TIMEOUT)"
        ),
    )
    parser.add_argument(
        "--mcp-transport",
        choices=["stdio", "sse", "streamable-http"],
        default=mcp_transport_default,
        help="MCP transport (default: MCP_TRANSPORT or streamable-http)",
    )
    parser.add_argument(
        "--mcp-http-host",
        default=mcp_http_host_default,
        help="MCP HTTP host (default: MCP_HTTP_HOST)",
    )
    parser.add_argument(
        "--mcp-http-port",
        type=int,
        default=mcp_http_port_default,
        help="MCP HTTP port (default: MCP_HTTP_PORT)",
    )
    parser.add_argument(
        "--mcp-http-path",
        type=str,
        default=mcp_http_path_default,
        help=(
            "MCP HTTP base/mount path (default: MCP_HTTP_PATH or "
            "MCP_STREAMABLE_HTTP_PATH)"
        ),
    )
    parser.add_argument(
        "--mcp-http-stateless",
        action=argparse.BooleanOptionalAction,
        default=mcp_http_stateless_default,
        help="Enable stateless HTTP mode (new session per request)",
    )
    parser.add_argument(
        "--mcp-http-json-response",
        action=argparse.BooleanOptionalAction,
        default=mcp_http_json_response_default,
        help="Return JSON responses instead of SSE for HTTP",
    )
    parser.add_argument(
        "--mcp-log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default=mcp_log_level_default,
        help="MCP log level (default: environment variable MCP_LOG_LEVEL)",
    )
    parser.add_argument(
        "--mcp-debug",
        action=argparse.BooleanOptionalAction,
        default=mcp_debug_default,
        help="Enable MCP debug mode (default: environment variable MCP_DEBUG)",
    )
    return parser.parse_args()


args = parse_args()

RXRESUME = _resolve_rxresume_settings(args)

TRANSPORT = args.mcp_transport

MCP = MCPSettings(
    host=args.mcp_http_host,
    port=args.mcp_http_port,
    mount_path=_normalize_path(args.mcp_http_path),
    stateless_http=args.mcp_http_stateless,
    json_response=args.mcp_http_json_response,
    log_level=args.mcp_log_level,
    debug=args.mcp_debug,
)
