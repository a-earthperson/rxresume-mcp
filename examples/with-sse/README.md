# SSE Transport (Docker)

Run `rxresume-mcp` using the Server-Sent Events (SSE) transport for MCP clients
that require SSE instead of streamable HTTP.

## Scenario

You have an MCP client that expects an SSE endpoint and a separate messages
endpoint (common in early MCP clients).

## Constraints

- SSE uses long-lived HTTP connections. Reverse proxies must allow streaming and
  idle timeouts should be increased.
- If you load balance, you may need sticky sessions.
- The server exposes `/sse` and `/messages/` by default (under `MCP_HTTP_PATH`).

## Files

- `docker-compose.yml`: run the container locally.
- `mcp.json`: example MCP client config for SSE.

## Quickstart

1) Update `docker-compose.yml` with your `APP_URL` and `REST_API_KEY`.

2) Start the server:

```bash
docker compose up -d
```

3) Point your MCP client at the SSE endpoint (example):

```json
{
  "mcpServers": {
    "rxresume": {
      "type": "sse",
      "url": "http://localhost:8000/sse"
    }
  }
}
```
