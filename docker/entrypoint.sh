#!/usr/bin/env sh
set -e

MCP_TRANSPORT="${MCP_TRANSPORT:-streamable-http}"
MCP_HTTP_HOST="${MCP_HTTP_HOST:-${MCP_HOST:-0.0.0.0}}"
MCP_HTTP_PORT="${MCP_HTTP_PORT:-${MCP_PORT:-8000}}"
MCP_HTTP_PATH="${MCP_HTTP_PATH:-${MCP_STREAMABLE_HTTP_PATH:-/}}"
MCP_HTTP_STATELESS="${MCP_HTTP_STATELESS:-${MCP_STATELESS_HTTP:-false}}"
MCP_HTTP_JSON_RESPONSE="${MCP_HTTP_JSON_RESPONSE:-${MCP_JSON_RESPONSE:-false}}"

ARGS="--mcp-transport ${MCP_TRANSPORT} --mcp-http-host ${MCP_HTTP_HOST} --mcp-http-port ${MCP_HTTP_PORT} --mcp-http-path ${MCP_HTTP_PATH}"

case "$(printf '%s' "${MCP_HTTP_STATELESS}" | tr '[:upper:]' '[:lower:]')" in
  1|true|yes|y) ARGS="${ARGS} --mcp-http-stateless" ;;
esac

case "$(printf '%s' "${MCP_HTTP_JSON_RESPONSE}" | tr '[:upper:]' '[:lower:]')" in
  1|true|yes|y) ARGS="${ARGS} --mcp-http-json-response" ;;
esac

exec rxresume-mcp ${ARGS} "$@"
