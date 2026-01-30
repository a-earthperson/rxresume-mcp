# Ollmcp (Ollama TUI) + RxResume MCP

This example wires `rxresume-mcp` into a local Ollama instance using the
`mcp-client-for-ollama` TUI (`ollmcp`) via a `--servers-json` config.

`ollmcp` supports STDIO, SSE, and streamable HTTP MCP transports. This example
uses STDIO so the TUI launches `rxresume-mcp` as a child process and communicates
over stdin/stdout. See the upstream README for details:
https://github.com/jonigl/mcp-client-for-ollama

## Scenario

Run an MCP client locally with a tool-capable Ollama model, and use `ollmcp` to
invoke the Reactive Resume tools over STDIO.

## Constraints

- STDIO is local-only: the MCP server runs as a child process and is not exposed
  over the network.
- `APP_URL` must be the app root (no `/api` suffix). `rxresume-mcp` appends
  `/api/openapi` internally.
- Treat `REST_API_KEY` as a secret; avoid committing it into source control.

## Prerequisites

- Python 3.11+ (required by `rxresume-mcp`)
- Ollama running locally (default: `http://localhost:11434`)
- A Reactive Resume API endpoint and API key

If you want a local Reactive Resume stack, you can use the repo's
`docker-compose.yml` and start only the UI + dependencies:

```bash
docker compose up rxresume -d
```

## Configure the server

Edit `examples/with-ollmcp/servers.json`:

- `APP_URL`: base URL for the Reactive Resume app (no `/api` suffix).
- `REST_API_KEY`: API key generated in the Reactive Resume UI.

## Quickstart

1) Install the MCP server and the Ollama client:

```bash
pip install rxresume-mcp
pip install --upgrade ollmcp
```

2) Ensure Ollama is running and pull a tool-capable model:

```bash
ollama serve
ollama pull qwen2.5:7b
```

3) Start `ollmcp` with this example config:

```bash
ollmcp --servers-json examples/with-ollmcp/servers.json --model qwen2.5:7b
```

4) In the TUI, confirm tools are available and try a call like `list_resumes`.

## Notes

- If `rxresume-mcp` is not on your `PATH`, update `servers.json` to use a
  different `command` and `args`. For example, with `uv`:

```json
{
  "mcpServers": {
    "rxresume": {
      "command": "uv",
      "args": ["run", "rxresume-mcp", "--mcp-transport", "stdio"],
      "env": {
        "APP_URL": "http://localhost:3000",
        "REST_API_KEY": "your-rxresume-api-key"
      }
    }
  }
}
```

## Optional: Streamable HTTP instead of STDIO

If you prefer a shared HTTP MCP server, run:

```bash
rxresume-mcp --mcp-transport streamable-http --mcp-http-host 0.0.0.0 --mcp-http-port 8000
```

Then replace the server entry with a `streamable_http` URL in a separate config
file:

```json
{
  "mcpServers": {
    "rxresume": {
      "type": "streamable_http",
      "url": "http://localhost:8000/mcp"
    }
  }
}
```
