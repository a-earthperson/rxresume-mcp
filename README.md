# rxresume-mcp
[![Coverage](https://github.com/a-earthperson/rxresume-mcp/actions/workflows/coverage.yml/badge.svg?branch=main)](https://github.com/a-earthperson/rxresume-mcp/actions/workflows/coverage.yml)
[![Docker](https://github.com/a-earthperson/rxresume-mcp/actions/workflows/docker.yml/badge.svg?branch=main)](https://github.com/a-earthperson/rxresume-mcp/actions/workflows/docker.yml)
[![Lint](https://github.com/a-earthperson/rxresume-mcp/actions/workflows/lint.yml/badge.svg?branch=main)](https://github.com/a-earthperson/rxresume-mcp/actions/workflows/lint.yml)
[![Tests](https://github.com/a-earthperson/rxresume-mcp/actions/workflows/tests.yml/badge.svg?branch=main)](https://github.com/a-earthperson/rxresume-mcp/actions/workflows/tests.yml)
[![PyPI](https://img.shields.io/pypi/v/rxresume-mcp.svg)](https://pypi.org/project/rxresume-mcp/)
[![GHCR](https://img.shields.io/badge/ghcr.io-rxresume--mcp-blue)](https://github.com/a-earthperson/rxresume-mcp/pkgs/container/rxresume-mcp)


A small MCP wrapper around the [Reactive Resume](https://github.com/amruthpillai/reactive-resume) REST API.
Use it to manipulate resumes using MCP tools.

## Quick start

### 1) Install

Requirements: Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/a-earthperson/rxresume-mcp.git
cd rxresume-mcp
uv sync
```

This installs dependencies and registers the `rxresume-mcp` console script via `uv run`.

### 2) Configure your MCP client (stdio)

Add this to your MCP client config (stdio transport). Some clients (like Cursor)
may require `uv` to be pointed at the project path, in which case include
`--project /absolute/path/to/rxresume-mcp` in the `args`.

## mcp.json
Use this as a starting point for your MCP client configuration (stdio transport).

```json
{
  "mcpServers": {
    "rxresume": {
      "command": "uv",
      "args": ["run", "rxresume-mcp", "--mcp-transport", "stdio"],
      "env": {
        "APP_URL": "https://rxresu.me",
        "REST_API_KEY": "your-rxresume-api-key",
        "REST_API_TIMEOUT": "30",
        "REST_API_USER_AGENT": "rxresume-mcp/0.1.0"
      }
    }
  }
}
```

Cursor example (note the `--project` path):

```json
{
  "mcpServers": {
    "rxresume": {
      "command": "uv",
      "args": [
        "run",
        "--project",
        "/absolute/path/to/rxresume-mcp",
        "rxresume-mcp",
        "--mcp-transport",
        "stdio"
      ],
      "env": {
        "APP_URL": "https://rxresu.me",
        "REST_API_KEY": "your-rxresume-api-key",
        "REST_API_TIMEOUT": "30",
        "REST_API_USER_AGENT": "rxresume-mcp/0.1.0"
      }
    }
  }
}
```

If you want to run it manually for debugging:

```bash
APP_URL="http://localhost:3000" REST_API_KEY="rxresume-key" uv run rxresume-mcp --mcp-transport stdio
```

## Quick start with Docker Compose

Spin up Reactive Resume (plus dependencies) and the MCP server together:

```bash
docker compose up --build
```

Once healthy, the MCP server is available on port `8000` and the app on `3000`.

## Development

For full development instructions, see `DEVELOPING.md`. Quick start:

```bash
uv sync --extra dev
uv run ruff check src
uv run pytest
```
