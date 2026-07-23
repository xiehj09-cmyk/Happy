@echo off
REM 将本机 MCP 工具挂载到小智 AI（WebSocket 接入点）
cd /d "%~dp0"
set "PATH=C:\Program Files\nodejs;%PATH%"

if not exist ".env" (
  echo 缺少 .env，请先填写 XIAOZHI_MCP_ENDPOINT
  pause
  exit /b 1
)

for /f "usebackq tokens=1,* delims==" %%a in (".env") do (
  if /i "%%a"=="XIAOZHI_MCP_ENDPOINT" set "XIAOZHI_MCP_ENDPOINT=%%b"
)

if "%XIAOZHI_MCP_ENDPOINT%"=="" (
  echo .env 中未找到 XIAOZHI_MCP_ENDPOINT
  pause
  exit /b 1
)

echo 正在连接小智 MCP 接入点...
echo 配置: mcp-config.json + custom-mcp.js
npx --yes mcp_exe --ws "%XIAOZHI_MCP_ENDPOINT%" --mcp-config "./mcp-config.json" --mcp-js "./custom-mcp.js" --server-name "memory-harbor-xiaozhi" --log-level INFO
pause
