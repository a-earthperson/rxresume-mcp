# Examples

This directory contains opinionated client and deployment examples for
`rxresume-mcp`. Each example is self-contained and documents its assumptions,
trade-offs, and constraints.

## Choosing an example

- `with-ollmcp`: Local STDIO integration with the Ollama TUI.
- `with-streamable-http`: Simple HTTP server for clients that support
  streamable HTTP (default transport).
- `with-sse`: SSE transport for clients that require Server-Sent Events.
- `with-traefik`: HTTPS exposure behind Traefik + ForwardAuth.
- `with-systemd`: Always-on Linux service with systemd.

## Common constraints

- `APP_URL` must be the Reactive Resume app root (no `/api` suffix). The MCP
  server appends `/api/openapi` internally.
- `REST_API_KEY` is a secret; avoid committing it to git or logs.
- If the MCP server is exposed on a network, put it behind auth and TLS.
- Streamable HTTP is served at `/mcp`. SSE uses `/sse` plus a `/messages/`
  posting endpoint. Proxies must allow these paths and long-lived connections
  when using SSE.
