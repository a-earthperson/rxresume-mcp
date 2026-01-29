# Developing rxresume-mcp

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)

## Setup

```bash
uv sync --extra dev
```

## Environment variables

- `APP_URL`: Base URL of Reactive Resume (e.g. `http://localhost:3000`)
- `REST_API_KEY`: API key for the REST API
- `REST_API_TIMEOUT`: Request timeout in seconds (default `30`)
- `REST_API_USER_AGENT`: User-Agent header (default `rxresume-mcp/0.1.0`)

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
