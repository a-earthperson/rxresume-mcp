# rxresume-mcp
A small MCP wrapper around the [Reactive Resume](https://github.com/amruthpillai/reactive-resume) REST API

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
        "APP_URL": "http://localhost:3000",
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
        "APP_URL": "http://localhost:3000",
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
