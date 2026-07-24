# Docker 运行（官网 + 小智 MCP）

## 方式 A：Compose 双容器（本机开发）

```bash
cp .env.example .env
# 编辑 xiaozhi-mcp/.env：XIAOZHI_MCP_ENDPOINT=wss://...
docker compose up -d --build
```

| 服务 | 容器名 | 说明 |
|------|--------|------|
| `web` | `memory-harbor-web` | 官网，`5000:8080` |
| `mcp` | `memory-harbor-mcp` | 小智桥接，内网访问 `http://web:8080` |

## 方式 B：单镜像双进程（与 Zeabur 推荐一致）

```bash
docker build -t memory-harbor .
docker run --rm -p 8080:8080 \
  --env-file .env \
  -e MCP_API_TOKEN=memory-harbor-mcp-dev-token \
  -e WEBSITE_MCP_TOKEN=memory-harbor-mcp-dev-token \
  -e XIAOZHI_MCP_ENDPOINT="wss://api.xiaozhi.me/mcp/?token=..." \
  memory-harbor
```

打开 http://127.0.0.1:8080 ，日志应出现「成功连接到WebSocket服务器」。

## 常用命令

```bash
docker compose ps
docker compose logs -f mcp
docker compose down
```

浏览器（Compose）：http://127.0.0.1:5000  
Zeabur 说明见 `ZEABUR.md`。
