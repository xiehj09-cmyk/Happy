"""百度智能云 · 语音合成（TTS）与短语音识别（ASR）服务端代理"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from config import (
    BAIDU_ACCESS_TOKEN,
    BAIDU_API_KEY,
    BAIDU_ASR_DEV_PID,
    BAIDU_ASR_URL,
    BAIDU_SECRET_KEY,
    BAIDU_TTS_PER,
    BAIDU_TTS_SPD,
)

_token_cache: dict[str, Any] = {"token": "", "expires_at": 0.0}


def baidu_speech_configured() -> bool:
    return bool(BAIDU_ACCESS_TOKEN or (BAIDU_API_KEY and BAIDU_SECRET_KEY))


def get_access_token(*, force_refresh: bool = False) -> str:
    """获取百度 Access Token（优先环境变量静态 Token，否则用 API Key/Secret 拉取并缓存）。"""
    if BAIDU_ACCESS_TOKEN and not force_refresh:
        return BAIDU_ACCESS_TOKEN

    now = time.time()
    if (
        not force_refresh
        and _token_cache["token"]
        and now < float(_token_cache["expires_at"]) - 120
    ):
        return str(_token_cache["token"])

    if not (BAIDU_API_KEY and BAIDU_SECRET_KEY):
        if BAIDU_ACCESS_TOKEN:
            return BAIDU_ACCESS_TOKEN
        raise RuntimeError("未配置百度语音凭证：请在 .env 设置 BAIDU_API_KEY/BAIDU_SECRET_KEY 或 BAIDU_ACCESS_TOKEN")

    query = urllib.parse.urlencode(
        {
            "grant_type": "client_credentials",
            "client_id": BAIDU_API_KEY,
            "client_secret": BAIDU_SECRET_KEY,
        }
    )
    url = f"https://aip.baidubce.com/oauth/2.0/token?{query}"
    req = urllib.request.Request(url, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"获取百度 Token 失败 {exc.code}: {detail[:300]}") from exc

    token = (data.get("access_token") or "").strip()
    if not token:
        raise RuntimeError(f"百度 Token 响应异常: {str(data)[:200]}")
    expires_in = int(data.get("expires_in") or 2592000)
    _token_cache["token"] = token
    _token_cache["expires_at"] = now + expires_in
    return token


def synthesize_speech(
    text: str,
    *,
    spd: int | None = None,
    per: int | None = None,
    pit: int | None = None,
    vol: int | None = None,
    aue: int | None = None,
    cuid: str = "memory-harbor-web",
) -> bytes:
    """调用百度 TTS，返回音频二进制（默认 mp3）。

    AD 关怀推荐：spd=3, pit=6, vol=10, per=4, aue=3
    """
    text = (text or "").strip()
    if not text:
        raise ValueError("播报文本不能为空")
    if len(text) > 500:
        text = text[:500]

    spd_val = BAIDU_TTS_SPD if spd is None else int(spd)
    per_val = BAIDU_TTS_PER if per is None else int(per)
    pit_val = 6 if pit is None else int(pit)
    vol_val = 10 if vol is None else int(vol)
    aue_val = 3 if aue is None else int(aue)
    spd_val = max(0, min(15, spd_val))
    pit_val = max(0, min(15, pit_val))
    vol_val = max(0, min(15, vol_val))
    # 常用：0普通女声 1普通男声 3情感合成度逍遥 4情感合成度丫丫；认知训练默认情感女声 4
    per_val = int(per_val)
    # aue: 3=mp3（情感更饱满）, 6=wav/pcm
    if aue_val not in (3, 4, 5, 6):
        aue_val = 3

    token = get_access_token()
    params = {
        "tex": text,
        "tok": token,
        "cuid": cuid[:60] or "memory-harbor-web",
        "ctp": "1",
        "lan": "zh",
        "spd": str(spd_val),
        "pit": str(pit_val),
        "vol": str(vol_val),
        "per": str(per_val),
        "aue": str(aue_val),
    }
    body = urllib.parse.urlencode(params).encode("utf-8")
    req = urllib.request.Request(
        "https://tsn.baidu.com/text2audio",
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            content_type = (resp.headers.get("Content-Type") or "").lower()
            raw = resp.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"百度 TTS 失败 {exc.code}: {detail[:300]}") from exc

    if "application/json" in content_type or raw[:1] == b"{":
        try:
            err = json.loads(raw.decode("utf-8", errors="replace"))
        except json.JSONDecodeError:
            err = {"err_msg": raw[:200].decode("utf-8", errors="replace")}
        raise RuntimeError(f"百度 TTS 错误: {err.get('err_msg') or err}")
    return raw


def recognize_speech(
    audio_bytes: bytes,
    *,
    format_: str = "wav",
    rate: int = 16000,
    cuid: str = "memory-harbor-web",
) -> dict[str, Any]:
    """调用百度短语音识别，返回 {text, raw}。"""
    if not audio_bytes:
        raise ValueError("音频为空")
    if len(audio_bytes) > 10 * 1024 * 1024:
        raise ValueError("音频过大（请控制在 10MB 内）")

    token = get_access_token()
    # JSON 方式上传（base64）兼容性更好
    import base64

    payload = {
        "format": format_ or "wav",
        "rate": int(rate) or 16000,
        "channel": 1,
        "cuid": cuid[:60] or "memory-harbor-web",
        "token": token,
        "dev_pid": int(BAIDU_ASR_DEV_PID or 1537),
        "speech": base64.b64encode(audio_bytes).decode("ascii"),
        "len": len(audio_bytes),
    }
    body = json.dumps(payload).encode("utf-8")
    url = BAIDU_ASR_URL or "https://vop.baidu.com/server_api"
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=40) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"百度 ASR 失败 {exc.code}: {detail[:300]}") from exc

    err_no = int(data.get("err_no", -1))
    if err_no != 0:
        raise RuntimeError(f"百度 ASR 错误 {err_no}: {data.get('err_msg') or data}")

    results = data.get("result") or []
    text = ""
    if isinstance(results, list) and results:
        text = str(results[0] or "").strip()
    return {"text": text, "raw": data}


def evaluate_soft_answer(user_text: str, question: dict) -> dict[str, Any]:
    """认知训练柔和评判：匹配选项或关键词即视为参与成功，避免严苛对错。"""
    text = (user_text or "").strip()
    options = [str(o) for o in (question.get("options") or []) if str(o).strip()]
    prompt = str(question.get("prompt") or "")

    if not text:
        return {
            "ok": False,
            "matched": False,
            "level": "empty",
            "message": "没有听清，请再试一次，慢慢说就好。",
            "speak": "没有听清，请再试一次，慢慢说就好。",
        }

    # 完全包含任一选项
    for opt in options:
        if opt and (opt in text or text in opt):
            return {
                "ok": True,
                "matched": True,
                "level": "good",
                "message": f"很好，您说了「{text}」。",
                "speak": f"很好。您说了{text}。我们继续下一题。",
            }

    # 选项关键词（去掉语气词）
    soft_skip = {"可以说一说", "有点印象", "想再看看", "先跳过", "说不准", "记不清了"}
    meaningful = [o for o in options if o not in soft_skip and len(o) >= 2]
    for opt in meaningful:
        # 取 2 字以上片段粗匹配
        if len(opt) >= 2 and any(opt[i : i + 2] in text for i in range(len(opt) - 1)):
            return {
                "ok": True,
                "matched": True,
                "level": "close",
                "message": f"说得不错：「{text}」。谢谢您的分享。",
                "speak": "说得不错。谢谢您的分享。我们继续。",
            }

    # 无严格标准答案：只要开口就正向反馈
    return {
        "ok": True,
        "matched": False,
        "level": "try",
        "message": f"已记下您说的「{text}」。没有对错，能说出来就很好。",
        "speak": "很好，您已经回答了。没有对错，我们继续下一题。",
        "prompt_hint": prompt[:40],
    }


def public_speech_config() -> dict[str, Any]:
    return {
        "configured": baidu_speech_configured(),
        "default_spd": BAIDU_TTS_SPD,
        "default_per": BAIDU_TTS_PER,
        "voices": [
            {"id": 0, "label": "标准女声（温和）"},
            {"id": 1, "label": "标准男声"},
            {"id": 3, "label": "情感男声"},
            {"id": 4, "label": "情感女声"},
        ],
        "spd_hint": "认知训练建议语速 3–5",
    }
