@echo off
cd /d "%~dp0"
echo [记忆港湾] 安装依赖...
python -m pip install -r requirements.txt -q
if not exist ".env" (
  copy /Y ".env.example" ".env" >nul
  echo [记忆港湾] 已生成 .env，请尽快修改 SECRET_KEY
)
echo [记忆港湾] 使用 Waitress 启动...
python app.py
pause
