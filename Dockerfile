# 记忆港湾 · 单容器双进程（官网 Flask + 小智 MCP）
# Zeabur：ZBPACK_DOCKERFILE_PATH=Dockerfile
# 用官方 node 镜像拷贝二进制，避免 nodesource apt 在 CI 上失败
FROM node:20-bookworm-slim AS node_base

FROM python:3.12-slim-bookworm

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=8080 \
    FLASK_DEBUG=0 \
    NODE_ENV=production \
    WEBSITE_BASE=http://127.0.0.1:8080 \
    NPM_CONFIG_FETCH_RETRIES=5 \
    NPM_CONFIG_FETCH_RETRY_MINTIMEOUT=20000 \
    NPM_CONFIG_FETCH_RETRY_MAXTIMEOUT=120000

# TLS 证书（小智 WSS 必需）+ 从官方 Node 镜像拷贝 node/npm
RUN apt-get update \
  && apt-get install -y --no-install-recommends ca-certificates \
  && rm -rf /var/lib/apt/lists/*

COPY --from=node_base /usr/local/bin/node /usr/local/bin/node
COPY --from=node_base /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -sf /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
  && ln -sf /usr/local/lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx \
  && node -v \
  && npm -v

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY xiaozhi-mcp/package.json xiaozhi-mcp/package-lock.json /app/xiaozhi-mcp/
WORKDIR /app/xiaozhi-mcp
RUN npm ci --omit=dev

WORKDIR /app
COPY . .
RUN mkdir -p /app/instance /app/xiaozhi-mcp/data \
  && sed -i 's/\r$//' /app/scripts/docker-entrypoint.sh \
  && chmod +x /app/scripts/docker-entrypoint.sh \
  && test -x /app/scripts/docker-entrypoint.sh \
  && test -f /app/xiaozhi-mcp/start-with-env.js \
  && test -d /app/xiaozhi-mcp/node_modules/mcp_exe

EXPOSE 8080

CMD ["/app/scripts/docker-entrypoint.sh"]
