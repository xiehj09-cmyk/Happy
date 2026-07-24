# 记忆港湾 · 单容器双进程（官网 Flask + 小智 MCP）
# Zeabur 推荐：只建一个 Git 服务，并设置
#   ZBPACK_DOCKERFILE_PATH=Dockerfile
#   XIAOZHI_MCP_ENDPOINT=wss://api.xiaozhi.me/mcp/?token=...
FROM python:3.12-slim-bookworm

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=8080 \
    FLASK_DEBUG=0 \
    NODE_ENV=production \
    WEBSITE_BASE=http://127.0.0.1:8080

RUN apt-get update \
  && apt-get install -y --no-install-recommends curl ca-certificates \
  && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
  && apt-get install -y --no-install-recommends nodejs \
  && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY xiaozhi-mcp/package.json /app/xiaozhi-mcp/package.json
WORKDIR /app/xiaozhi-mcp
RUN npm install --omit=dev

WORKDIR /app
COPY . .
RUN mkdir -p /app/instance /app/xiaozhi-mcp/data \
  && sed -i 's/\r$//' /app/scripts/docker-entrypoint.sh \
  && chmod +x /app/scripts/docker-entrypoint.sh

EXPOSE 8080

CMD ["/app/scripts/docker-entrypoint.sh"]
