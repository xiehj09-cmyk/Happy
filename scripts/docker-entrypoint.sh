#!/bin/sh
# 单容器同时启动：官网 Flask + 小智 MCP 桥接
set -eu

PORT_VALUE="${PORT:-8080}"
export HOST="${HOST:-0.0.0.0}"
export PORT="$PORT_VALUE"
# 同容器内 MCP 永远走本机环回，避免 Zeabur 内网主机名配错
export WEBSITE_BASE="http://127.0.0.1:${PORT_VALUE}"

if [ -z "${WEBSITE_MCP_TOKEN:-}" ] && [ -n "${MCP_API_TOKEN:-}" ]; then
  export WEBSITE_MCP_TOKEN="$MCP_API_TOKEN"
fi

echo "[entrypoint] web HOST=$HOST PORT=$PORT_VALUE WEBSITE_BASE=$WEBSITE_BASE DATA_DIR=${DATA_DIR:-/data}"
mkdir -p "${DATA_DIR:-/data}" /app/xiaozhi-mcp/data

if [ -n "${XIAOZHI_MCP_ENDPOINT:-}" ]; then
  echo "[entrypoint] starting Xiaozhi MCP bridge…"
  (
    cd /app/xiaozhi-mcp
    exec node start-with-env.js
  ) &
  MCP_PID=$!
  echo "[entrypoint] mcp pid=$MCP_PID"
else
  echo "[entrypoint] WARN: XIAOZHI_MCP_ENDPOINT 未设置，跳过 MCP（官网仍可访问）"
  MCP_PID=""
fi

cleanup() {
  echo "[entrypoint] shutting down…"
  if [ -n "$MCP_PID" ] && kill -0 "$MCP_PID" 2>/dev/null; then
    kill "$MCP_PID" 2>/dev/null || true
    wait "$MCP_PID" 2>/dev/null || true
  fi
}
trap cleanup INT TERM EXIT

python /app/app.py &
WEB_PID=$!
echo "[entrypoint] web pid=$WEB_PID"

# 任一进程退出则结束容器，便于 Zeabur 发现故障并重启
while true; do
  if ! kill -0 "$WEB_PID" 2>/dev/null; then
    echo "[entrypoint] web exited"
    exit 1
  fi
  if [ -n "$MCP_PID" ] && ! kill -0 "$MCP_PID" 2>/dev/null; then
    echo "[entrypoint] mcp exited — restarting container so Zeabur redeploys MCP"
    kill "$WEB_PID" 2>/dev/null || true
    exit 1
  fi
  sleep 3
done
