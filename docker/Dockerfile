############################
# Builder: resolve/install deps into a venv
############################
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    UV_PROJECT_ENVIRONMENT=/opt/venv

# uv is used by the repo; installing it once in the builder keeps the runtime image small.
RUN python -m venv "${VIRTUAL_ENV}" \
 && pip install --no-cache-dir -U pip \
 && pip install --no-cache-dir uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project

COPY src ./src
COPY README.md LICENSE ./
RUN uv sync --frozen

############################
# Runtime: copy venv only
############################
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH=/app/src

RUN addgroup --system app && adduser --system --ingroup app app

COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /app/src /app/src
COPY docker/entrypoint.sh /usr/local/bin/entrypoint

RUN chmod +x /usr/local/bin/entrypoint

USER app
WORKDIR /app

# Runtime-configurable REST_API_HOST + MCP parameters (override via env or docker run -e)
ENV MCP_TRANSPORT=streamable-http \
    MCP_HTTP_HOST=0.0.0.0 \
    MCP_HTTP_PORT=8001 \
    MCP_HTTP_PATH=/ \
    MCP_HTTP_STATELESS=true \
    MCP_HTTP_JSON_RESPONSE=true \
    MCP_LOG_LEVEL=DEBUG \
    MCP_DEBUG=true

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import os, socket, sys; transport=os.getenv('MCP_TRANSPORT','streamable-http'); transport == 'stdio' and sys.exit(0); port=int(os.getenv('MCP_HTTP_PORT','8000')); s=socket.socket(); s.settimeout(2); s.connect(('127.0.0.1', port)); s.close()"

ENTRYPOINT ["/usr/local/bin/entrypoint"]
CMD []