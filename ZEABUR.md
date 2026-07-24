# 在 Zeabur 上部署记忆港湾（官网 + 小智 MCP）

仓库：https://github.com/xiehj09-cmyk/Happy  
分支：`main`

---

## 推荐：单服务同容器（官网 + MCP）

之前用两个服务时，MCP 经常因环境变量/内网地址没配对而连不上小智。  
现在仓库根目录 `Dockerfile` 会在**同一个容器**里同时跑 Flask 与 MCP 桥接。

1. Zeabur → Add Service → Git → `xiehj09-cmyk/Happy`
2. 只需 **一个** 服务（名称随意，例如 `harbor`）
3. Variables 粘贴（完整模板见 `zeabur.all.env.example`），至少包含：

```text
ZBPACK_DOCKERFILE_PATH=Dockerfile
HOST=0.0.0.0
PORT=${WEB_PORT}
TRUST_PROXY=1
SECRET_KEY=随机长字符串
MCP_API_TOKEN=请换成随机长字符串
WEBSITE_MCP_TOKEN=与上面 MCP_API_TOKEN 相同
WEBSITE_BASE=http://127.0.0.1:8080
MCP_ELDER_USERNAME=15
XIAOZHI_MCP_ENDPOINT=wss://api.xiaozhi.me/mcp/?token=你的最新接入点
```

4. Networking → Generate Domain  
5. Volumes → 挂载 **`/data`**（持久化 SQLite 账号与业务数据；与图中硬盘挂载一致）  
6. Deploy / Redeploy  
7. 打开域名确认账号可用；小智绑定请粘贴 MCP 接入点 Token

日志里应出现：`稳定桥接启动` → `成功连接到WebSocket服务器` → `MCP服务器启动成功`。

说明：
- `DATA_DIR=/data`：账号库写入挂载盘 `/data/users.db`（也可用环境变量覆盖）
- `MCP_ELDER_USERNAME=15`：所有经全局 `MCP_API_TOKEN` 进来的小智请求都写入账号 15
- `WEBSITE_BASE` 由入口脚本自动设为 `http://127.0.0.1:$PORT`，Variables 里可不写
- 构建使用「从官方 `node` 镜像拷贝」方式安装 Node，避免 NodeSource apt 在 Zeabur 构建失败
- MCP 使用 `start-stable-bridge.js`（每次连接新建 Protocol，并禁用配置文件热重载），避免 `Already connected to a transport`
- 同一接入点只能有一条桥：关掉本机 `npm run xiaozhi`，Zeabur 也只保留**一个**带 MCP 的服务
- 接入点 Token 过期时，到小智控制台重新复制并更新 `XIAOZHI_MCP_ENDPOINT` 后 Redeploy
- 不要把 Token 提交到 Git

若构建仍失败：请把日志里带 `ERROR` / `failed` 的完整段落贴出（你上次贴到的只是 pip 成功，真正报错通常在后面的 `npm install` 或启动阶段）。

---

## 备选：双服务（Dockerfile.web + Dockerfile.mcp）

仅在需要把 MCP 与官网拆开扩缩容时使用。服务名必须为 `web` / `mcp`。

| 服务名 | Dockerfile | 作用 |
|--------|------------|------|
| `web` | `Dockerfile.web` | 官网 |
| `mcp` | `Dockerfile.mcp` | 小智桥接 |

**mcp** 必填：

```text
WEBSITE_BASE=http://web.zeabur.internal:8080
WEBSITE_MCP_TOKEN=与 web 的 MCP_API_TOKEN 相同
XIAOZHI_MCP_ENDPOINT=wss://api.xiaozhi.me/mcp/?token=...
```

---

## 部署后检查

1. 公网域名能打开落地页 / 登录  
2. 服务日志有小智 WebSocket 连接成功  
3. 小智控制台能看到记忆港湾工具  
4. 工作台已手动绑定小智 UserId  

本地 Docker Compose 双容器仍可用：`docker compose up -d --build`（见 `DOCKER.md`）。本机也可直接：

```bash
cd xiaozhi-mcp
# 先在 .env 写入 XIAOZHI_MCP_ENDPOINT
npm run xiaozhi
```
