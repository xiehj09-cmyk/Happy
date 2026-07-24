"""应用配置 · 优先读取环境变量"""

from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def _load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


_load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.environ.get("SECRET_KEY") or "alzheimers-care-dev-secret-change-in-production"
HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "5000"))
DEBUG = os.environ.get("FLASK_DEBUG", "0").lower() in {"1", "true", "yes", "on"}
THREADS = int(os.environ.get("WAITRESS_THREADS", "4"))

# DeepSeek · 智能加药
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "").strip()
DEEPSEEK_BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-flash").strip()
DEEPSEEK_TIMEOUT = int(os.environ.get("DEEPSEEK_TIMEOUT", "60"))

# 百度智能云 · 语音合成 / 短语音识别（勿把真实 Key 写进代码仓库）
BAIDU_API_KEY = os.environ.get("BAIDU_API_KEY", "").strip()
BAIDU_SECRET_KEY = os.environ.get("BAIDU_SECRET_KEY", "").strip()
# 可选：直接提供 Access Token（调试用）；优先建议用 API Key + Secret 自动刷新
BAIDU_ACCESS_TOKEN = os.environ.get("BAIDU_ACCESS_TOKEN", "").strip()
BAIDU_TTS_SPD = int(os.environ.get("BAIDU_TTS_SPD", "4"))  # 0-15，认知训练偏慢
BAIDU_TTS_PER = int(os.environ.get("BAIDU_TTS_PER", "0"))  # 0 温和女声
BAIDU_ASR_URL = os.environ.get("BAIDU_ASR_URL", "https://vop.baidu.com/server_api").strip()
# 1537=普通话(纯中文)；极速版应用可改用对应 dev_pid / pro_api
BAIDU_ASR_DEV_PID = int(os.environ.get("BAIDU_ASR_DEV_PID", "1537"))

# 小智 MCP → 本站 API（本机桥接；勿把真实 Token 提交仓库）
MCP_API_TOKEN = os.environ.get("MCP_API_TOKEN", "").strip()
# 所有小智请求默认归属的老人：优先用户名（如 15），其次数字 id
MCP_ELDER_USERNAME = os.environ.get("MCP_ELDER_USERNAME", "").strip()
MCP_ELDER_USER_ID = int(os.environ.get("MCP_ELDER_USER_ID", "0") or "0")
MCP_API_BASE = os.environ.get("MCP_API_BASE", "http://127.0.0.1:5000").rstrip("/")
