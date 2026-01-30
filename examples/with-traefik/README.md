# Streamable HTTP with Traefik + ForwardAuth

Expose `rxresume-mcp` over HTTPS behind Traefik, and gate access with an external
auth service using Traefik ForwardAuth.

## Scenario

You already run Traefik as an edge reverse proxy and want to publish the MCP
server over HTTPS with a Bearer token requirement.

## Constraints

- This example enables **stateless JSON** responses to make it easier to run
  behind auth middleware. Clients that require SSE streaming should disable
  `MCP_HTTP_JSON_RESPONSE` (and ensure SSE is allowed end-to-end).
- You must already have:
  - A Traefik instance on the `traefik-public` network.
  - An `https` entrypoint + certificate resolver (named `le` here).
  - An `https-redirect` middleware (or adjust/remove the label).
  - An external auth service that validates the `Authorization` header.
- Do not expose the MCP server publicly without auth; it has access to your
  Reactive Resume API key.

## Quickstart

1) Ensure the shared Traefik network exists:

```bash
docker network create traefik-public
```

2) Update `docker-compose.yml`:

- `APP_URL` to your Reactive Resume app root (no `/api` suffix).
- `REST_API_KEY` to your API key.
- `Host(...)` rule and `auth` URL to your domains.

3) Start the service:

```bash
docker compose up -d
```

4) Point your MCP client to the streamable HTTP endpoint:

```json
{
  "mcpServers": {
    "rxresume": {
      "type": "streamable_http",
      "url": "https://mcp.your-domain.com/mcp"
    }
  }
}
```

## Notes

- The ForwardAuth example assumes an auth endpoint that accepts a `GET` request
  with the `Authorization: Bearer <token>` header and returns a `2xx` response
  for valid tokens.
- If you want SSE instead of JSON, set `MCP_HTTP_JSON_RESPONSE=false` and ensure
  Traefik allows long-lived SSE connections.
