# systemd Service (Linux)

Run `rxresume-mcp` as a long-lived systemd service on a Linux host. This is a
good fit for homelab or single-VM deployments.

## Scenario

You want a stable, always-on MCP server on a Linux host, managed by systemd, and
exposed to your network or reverse proxy.

## Constraints

- The service runs with access to your Reactive Resume API key; secure the host
  and environment file permissions.
- If you expose it publicly, put it behind auth + TLS.
- Update `ExecStart` to the correct `rxresume-mcp` path on your system.

## Files

- `rxresume-mcp.service`: systemd unit file.
- `rxresume-mcp.env.example`: example environment file (copy to `/etc`).

## Quickstart

1) Install `rxresume-mcp` on the host (Python 3.11+ required):

```bash
pip install rxresume-mcp
```

2) Create a service user (optional but recommended):

```bash
sudo useradd --system --create-home --shell /usr/sbin/nologin rxresume
```

3) Copy and edit the environment file:

```bash
sudo cp examples/with-systemd/rxresume-mcp.env.example /etc/rxresume-mcp.env
sudo chmod 600 /etc/rxresume-mcp.env
```

4) Copy the unit file and update `ExecStart` if needed:

```bash
sudo cp examples/with-systemd/rxresume-mcp.service /etc/systemd/system/
sudo systemctl daemon-reload
```

5) Enable and start:

```bash
sudo systemctl enable --now rxresume-mcp.service
```

6) Verify:

```bash
systemctl status rxresume-mcp.service
```
