# Docker 双服务运行（官网 + 小智 MCP）

## 一键启动

```bash
# 1. 准备密钥（若尚无）
cp .env.example .env
# 编辑 .env：至少设置 MCP_API_TOKEN；按需填 DeepSeek / 百度

# 2. 小智接入点（xiaozhi-mcp/.env）
# XIAOZHI_MCP_ENDPOINT=wss://api.xiaozhi.me/mcp/?token=...
# WEBSITE_MCP_TOKEN 与官网 MCP_API_TOKEN 一致

# 3. 构建并后台启动两个容器
docker compose up -d --build
```

## 服务说明

| 服务 | 容器名 | 说明 |
|------|--------|------|
| `web` | `memory-harbor-web` | 记忆港湾官网，映射 `5000:5000` |
| `mcp` | `memory-harbor-mcp` | 小智 MCP 桥接，通过 `http://web:5000` 调官网 API |

数据卷：

- `web_instance` → SQLite（`/app/instance`）
- `mcp_notes` → 语音事项 txt（`/app/data`）

## 常用命令

```bash
docker compose ps
docker compose logs -f web
docker compose logs -f mcp
docker compose restart
docker compose down
```

浏览器打开：http://127.0.0.1:5000
