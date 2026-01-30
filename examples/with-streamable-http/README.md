# Streamable HTTP (Docker)

Run `rxresume-mcp` as a streamable HTTP server for MCP clients that connect over
HTTP. This is the default transport and the easiest to expose behind a reverse
proxy.

## Scenario

You want a network-accessible MCP server that multiple clients can connect to
via a single HTTP endpoint.

## Constraints

- If you expose this on a network, add auth + TLS (reverse proxy, VPN, or
  private network).
- Default endpoint is `http://<host>:8000/mcp`. If you change
  `MCP_HTTP_PATH` or the port, update client configs accordingly.
- For stateless, per-request behavior (no MCP sessions), set
  `MCP_HTTP_STATELESS=true`. For JSON responses instead of SSE streaming, set
  `MCP_HTTP_JSON_RESPONSE=true`.

## Files

- `docker-compose.yml`: run the container locally.
- `mcp.json`: example MCP client config for streamable HTTP.

## Quickstart

1) Update `docker-compose.yml` with your `APP_URL` and `REST_API_KEY`.

2) Start the server:

```bash
docker compose up -d
```

3) Point your MCP client at the server (example):

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
