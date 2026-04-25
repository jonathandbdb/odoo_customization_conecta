# syntax=docker/dockerfile:1.7
FROM python:3.12-slim-bookworm AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    NODE_MAJOR=22

# --- Sistema base + Node 22 (requerido por @github/copilot) + ssh client ----
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl gnupg openssh-client postgresql-client \
        git tini \
    && mkdir -p /etc/apt/keyrings \
    && curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key \
        | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg \
    && echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_${NODE_MAJOR}.x nodistro main" \
        > /etc/apt/sources.list.d/nodesource.list \
    && apt-get update && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# --- GitHub Copilot CLI (agente) ---
# El paquete es @github/copilot, instala el binario `copilot`.
RUN npm install -g @github/copilot && copilot --version || true

# --- Usuario no-root ---
RUN useradd -m -u 1000 -s /bin/bash gateway \
    && mkdir -p /home/gateway/.ssh /home/gateway/.copilot \
    && chown -R gateway:gateway /home/gateway

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY app /app/app
COPY AGENTS.md /app/AGENTS.md
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh && chown -R gateway:gateway /app

USER gateway
EXPOSE 8080

ENTRYPOINT ["/usr/bin/tini", "--", "/app/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "2"]
