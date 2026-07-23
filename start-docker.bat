@echo off
REM 双服务：官网(web) + 小智 MCP(mcp)
cd /d "%~dp0"

where docker >nul 2>&1
if errorlevel 1 (
  echo 未检测到 Docker。请先安装 Docker Desktop：
  echo https://www.docker.com/products/docker-desktop/
  pause
  exit /b 1
)

if not exist ".env" (
  echo 缺少根目录 .env，正在从 .env.example 复制...
  copy /Y ".env.example" ".env" >nul
)

if not exist "xiaozhi-mcp\.env" (
  echo 缺少 xiaozhi-mcp\.env，请先填写 XIAOZHI_MCP_ENDPOINT
  pause
  exit /b 1
)

echo 正在构建并启动 web + mcp ...
docker compose up -d --build
if errorlevel 1 (
  echo 启动失败，请查看上方日志
  pause
  exit /b 1
)

echo.
echo 官网: http://127.0.0.1:5000
echo 查看日志: docker compose logs -f
echo 停止:     docker compose down
pause
