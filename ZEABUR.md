# 在 Zeabur 上部署记忆港湾（官网 + MCP）

Zeabur **不支持直接跑 docker-compose**，请按「两个 Git 服务」部署同一仓库。

仓库：https://github.com/xiehj09-cmyk/Happy  
分支：`main`

| 服务名 | Dockerfile（自动匹配） | 作用 |
|--------|------------------------|------|
| `web` | `Dockerfile.web` | 官网 Flask |
| `mcp` | `Dockerfile.mcp` | 小智 MCP 桥接 |

---

## 方式 A：控制台手动部署（推荐）

1. 打开 [Zeabur](https://zeabur.com) → 新建项目  
2. **Add Service → Git** → 选择 `xiehj09-cmyk/Happy`  
3. 创建第一个服务，**名称必须为 `web`**  
   - Root Directory：仓库根目录  
   - 会自动使用 `Dockerfile.web`  
   - Networking：Generate Domain（得到 `*.zeabur.app`）  
   - Volumes：挂载 `/app/instance`（持久化 SQLite）  
4. 再添加第二个 Git 服务，**名称必须为 `mcp`**  
   - 自动使用 `Dockerfile.mcp`  
   - Volumes：挂载 `/app/data`  
   - **不要**绑公网域名（MCP 只出站连小智）  
5. 为两个服务配置环境变量（见下表）  
6. 部署完成后：用浏览器打开 web 域名 → 登录账号 **15** →「小智账号绑定」

### 环境变量

在 Zeabur 服务 → **Variables** 里按 `KEY=value` 逐行粘贴（可参考仓库根目录 `zeabur.web.env.example` / `zeabur.mcp.env.example`）。

**web**（必填 + DeepSeek / 百度语音）

```text
HOST=0.0.0.0
PORT=${WEB_PORT}
FLASK_DEBUG=0
TRUST_PROXY=1
WAITRESS_THREADS=4
SECRET_KEY=请换成随机长字符串
MCP_API_TOKEN=请与 mcp 的 WEBSITE_MCP_TOKEN 一致
MCP_ELDER_USER_ID=0
DEEPSEEK_API_KEY=你的DeepSeek密钥
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash
DEEPSEEK_TIMEOUT=60
BAIDU_API_KEY=
BAIDU_SECRET_KEY=
BAIDU_ACCESS_TOKEN=你的百度AccessToken
BAIDU_TTS_SPD=4
BAIDU_TTS_PER=0
BAIDU_ASR_URL=https://vop.baidu.com/server_api
BAIDU_ASR_DEV_PID=1537
```

说明：
- `PORT` 必须用 `${WEB_PORT}`，不要写死端口
- 百度：填 `BAIDU_API_KEY` + `BAIDU_SECRET_KEY`，**或**只填 `BAIDU_ACCESS_TOKEN`（Token 会过期，优先 Key/Secret）
- DeepSeek / 百度密钥只配在 Zeabur，不要提交到 Git

**mcp**

| 变量 | 说明 |
|------|------|
| `XIAOZHI_MCP_ENDPOINT` | 小智 `wss://api.xiaozhi.me/mcp/?token=...` |
| `WEBSITE_MCP_TOKEN` | 与 web 的 `MCP_API_TOKEN` **相同** |
| `WEBSITE_BASE` | 内网地址，例如 `http://web.zeabur.internal:8080`（以 Networking → Private 为准） |

在 mcp 服务的 Networking 里查看 web 的 Private Hostname，拼成：

```text
http://<web私有主机名>:8080
```

---

## 方式 B：模板一键部署

```bash
npx zeabur@latest auth login
npx zeabur@latest template deploy -f zeabur.yaml
```

按提示填写域名、`MCP_API_TOKEN`、`XIAOZHI_MCP_ENDPOINT`、`SECRET_KEY`。

---

## 部署后检查

1. 打开 web 公网域名，能看到落地页 / 登录  
2. Zeabur 中 `mcp` 状态为 Running  
3. 小智控制台能看到记忆港湾工具  
4. 工作台已手动绑定小智 UserId  

本地 Docker Compose 仍可用：`docker compose up -d --build`（见 `DOCKER.md`）。
