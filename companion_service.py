"""AI 陪伴闲聊 · 与 CST 引导员分离，不做用药/任务工具调用"""

from __future__ import annotations

from typing import Any

from assistant_service import call_deepseek_chat
from med_ai_service import deepseek_configured

COMPANION_SYSTEM = """你是「记忆港湾」的温和陪伴助手，陪老年人和家属轻松聊天。
规则：
1. 用简短、温暖的中文，一次只问一件小事。
2. 可以聊聊天气、回忆、兴趣爱好、今天过得怎么样；不跑题到复杂医疗建议。
3. 不纠正对方的记忆细节；多说「您说得很好」「慢慢来就好」。
4. 不做诊断、不开药、不替代医生；若涉及身体不适，温和建议联系家属或医生。
5. 回复尽量 2～4 句，字号感亲切，像坐在旁边聊天。
"""

DISCLAIMER = "这是陪伴聊天，不能代替医生面诊与处方。"


def run_companion_chat(
    *,
    message: str,
    username: str = "",
    history: list[dict] | None = None,
) -> dict[str, Any]:
    text = (message or "").strip()
    if not text:
        return {
            "ok": False,
            "reply": "您想聊点什么？可以说今天心情，或随便说一件小事。",
            "disclaimer": DISCLAIMER,
        }
    if not deepseek_configured():
        return {
            "ok": False,
            "reply": "AI 陪伴尚未配置 DeepSeek，请联系管理员设置 DEEPSEEK_API_KEY。",
            "disclaimer": DISCLAIMER,
        }

    messages: list[dict] = [{"role": "system", "content": COMPANION_SYSTEM}]
    for item in (history or [])[-10]:
        role_name = item.get("role")
        content = (item.get("content") or "").strip()
        if role_name in {"user", "assistant"} and content:
            messages.append({"role": role_name, "content": content[:800]})
    who = username or "朋友"
    messages.append(
        {
            "role": "user",
            "content": f"对方称呼：{who}\n对方说：{text}",
        }
    )

    try:
        msg = call_deepseek_chat(messages, tools=None, json_mode=False, temperature=0.65, max_tokens=600)
        reply = (msg.get("content") or "").strip() or "我在听，您慢慢说就好。"
        return {"ok": True, "reply": reply, "disclaimer": DISCLAIMER}
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "reply": f"暂时连不上陪伴助手：{exc}",
            "disclaimer": DISCLAIMER,
        }
