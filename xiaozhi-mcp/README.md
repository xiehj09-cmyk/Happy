# 小智 AI MCP 桥接（本目录）
#
# 作用：把本机 MCP 工具通过 WebSocket 挂到小智 AI 官方接入点。
#
# 首次准备：
# 1. 安装 Node.js LTS
# 2. 在本目录执行：npm install
# 3. 复制接入点到 .env 的 XIAOZHI_MCP_ENDPOINT=
#
# 启动（任选其一）：
# - 双击 start-xiaozhi.bat
# - npm run xiaozhi
#
# 已内置工具（custom-mcp.js）：
# - memory_harbor_ping：连通性检查
# - care_tip：用药/陪伴/安全/训练温馨提示
# - voice_note_write：把语音事项写入 data/voice_notes.txt
# - voice_note_query：按关键词查询或查看最近事项
#
# 事项文件路径：xiaozhi-mcp/data/voice_notes.txt

# 在 https://xiaozhi.me 控制台查看 MCP 工具是否已同步。
# 注意：.env 含 token，不要提交到 Git；本机需保持此进程运行，小智才能调用工具。
