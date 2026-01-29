# Developing rxresume-mcp

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)

## Setup

```bash
uv sync --extra dev
```

## Configuration (env + CLI)

Configuration can be provided via environment variables or CLI flags. CLI flags
always override environment variables. Booleans support explicit negation via
`--no-*` flags.

### Environment variables

| Variable | Default | Description |
| --- | --- | --- |
| `APP_URL` | `https://rxresu.me` | Base URL of Reactive Resume (e.g. `http://localhost:3000`). |
| `REST_API_KEY` | empty | API key for the REST API (`x-api-key`). |
| `REST_API_TIMEOUT` | `30` | Request timeout in seconds. |
| `REST_API_USER_AGENT` | `rxresume-mcp/0.1.0` | User-Agent header for API requests. |
| `MCP_TRANSPORT` | `streamable-http` | MCP transport: `stdio`, `sse`, or `streamable-http`. |
| `MCP_HTTP_HOST` | `localhost` | Host interface for HTTP transports. |
| `MCP_HTTP_PORT` | `8000` | Port for HTTP transports. |
| `MCP_HTTP_PATH` | `/` | Base path for MCP HTTP routes. |
| `MCP_STREAMABLE_HTTP_PATH` | empty | Fallback for `MCP_HTTP_PATH` when set. |
| `MCP_HTTP_STATELESS` | `false` | Enable stateless HTTP mode. |
| `MCP_STATELESS_HTTP` | empty | Fallback for `MCP_HTTP_STATELESS` when set. |
| `MCP_HTTP_JSON_RESPONSE` | `false` | Return JSON responses instead of SSE. |
| `MCP_JSON_RESPONSE` | empty | Fallback for `MCP_HTTP_JSON_RESPONSE` when set. |
| `MCP_LOG_LEVEL` | `DEBUG` | Log level: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`. |
| `MCP_DEBUG` | `true` | Enable debug mode in the MCP server. |

Notes:
- Fallback variables are supported to preserve compatibility with older configs.
- For booleans, accepted truthy values are `1`, `true`, `yes`, `y`, `on`; falsy are
  `0`, `false`, `no`, `n`, `off`.

### CLI arguments

| Argument | Default | Description |
| --- | --- | --- |
| `--app-url` | `https://rxresu.me` | Reactive Resume API base URL. |
| `--app-api-key` | empty | API key for the REST API (`x-api-key`). |
| `--app-api-user-agent` | `rxresume-mcp/0.1.0` | User-Agent header for API requests. |
| `--app-api-timeout` | `30` | Request timeout in seconds. |
| `--mcp-transport` | `streamable-http` | MCP transport: `stdio`, `sse`, or `streamable-http`. |
| `--mcp-http-host` | `localhost` | Host interface for HTTP transports. |
| `--mcp-http-port` | `8000` | Port for HTTP transports. |
| `--mcp-http-path` | `/` | Base path for MCP HTTP routes. |
| `--mcp-http-stateless` / `--no-mcp-http-stateless` | `false` | Toggle stateless HTTP mode. |
| `--mcp-http-json-response` / `--no-mcp-http-json-response` | `false` | Toggle JSON responses vs SSE. |
| `--mcp-log-level` | `DEBUG` | Log level: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`. |
| `--mcp-debug` / `--no-mcp-debug` | `true` | Toggle MCP debug mode. |

## Run the MCP server

Stdio transport:

```bash
APP_URL="http://localhost:3000" \
REST_API_KEY="rxresume-key" \
uv run rxresume-mcp --mcp-transport stdio
```

Streamable HTTP transport:

```bash
APP_URL="http://localhost:3000" \
REST_API_KEY="rxresume-key" \
uv run rxresume-mcp --mcp-transport streamable-http --mcp-http-host 127.0.0.1 --mcp-http-port 8000
```

## Lint and format

```bash
uv run ruff check src
uv run ruff format src
```

## Tests

```bash
uv run pytest
```

Coverage report:

```bash
uv run pytest --cov=rxresume_mcp --cov-report=term-missing --cov-report=xml
```

## Docker

Build the image:

```bash
docker build -f docker/Dockerfile -t rxresume-mcp:local .
```

Run the container:

```bash
docker run --rm -p 8000:8000 --env-file docker/example.env rxresume-mcp:local
```

Compose (Reactive Resume + dependencies + MCP server):

```bash
docker compose up --build
```

## Lockfile updates

After changing dependencies in `pyproject.toml`, regenerate the lockfile:

```bash
uv lock
```
