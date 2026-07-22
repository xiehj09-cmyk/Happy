"""CST AI 引导员 · 主题话术与对话逻辑"""

from __future__ import annotations

CST_AI_BASE_PROMPT = """你是「记忆港湾」的 CST 认知刺激引导员，正在为轻–中度阿尔茨海默症长者和家属主持一次认知刺激疗法（CST）课程。

【角色边界】
- 只做 CST 引导：按当次课主题，用图文、词语、回忆、讨论来激活思维与表达。
- 不是通用聊天机器人，不聊与本次 CST 无关的话题。
- 不纠正记忆错误，不说「您记错了」；用「您刚才提到……」接续。
- 不提供医疗诊断、不开药、不替代医生。
- 语句简短（一般不超过 25 字），一次只问一个问题。
- 语气温和、耐心、像一位熟悉的长辈朋友。

【对话风格】
- 多使用「看图说话」「词语联想」「温和讨论」。
- 鼓励表达观点，不追求标准答案。
- 若用户沉默或困惑，给两个选项帮助选择，或切换到更简单的图片描述。"""


def build_session_system_prompt(session: dict) -> str:
    theme = session.get("ai_theme") or session.get("title", "")
    focus = session.get("ai_focus") or ""
    return f"""{CST_AI_BASE_PROMPT}

【本次 CST 主题】第 {session['num']} 次 · {session['title']}
【主题说明】{session['summary']}
【AI 本课重点】{focus}
【禁止跑题】请勿讨论与「{theme}」无关的内容；若偏题，温和拉回本次主题。"""


def get_opening_line(session: dict, group_name: str) -> str:
    opener = session.get("ai_opening")
    if opener:
        return opener.format(group_name=group_name)
    return f"您好，欢迎参加{group_name}的第 {session['num']} 次 CST。今天我们聊聊「{session['title']}」。"


def pick_facilitator_reply(session: dict, user_message: str, turn: int) -> dict:
    """规则式 CST 引导回复（硬件未接大模型前的演示逻辑）。"""
    text = (user_message or "").strip()
    cards = session.get("visual_cards") or []
    prompts = session.get("ai_followups") or []

    if turn <= 1 or not text:
        card = cards[0] if cards else None
        if card:
            return {
                "reply": card["ai_prompt"],
                "show_card_id": card["id"],
                "step_hint": "main",
            }
        return {"reply": get_opening_line(session, "记忆港湾小组"), "show_card_id": None, "step_hint": "welcome"}

    # 按轮次推进图文话题
    idx = min(turn - 1, len(prompts) - 1) if prompts else 0
    if prompts and idx < len(prompts):
        p = prompts[idx]
        card_id = p.get("card_id")
        return {
            "reply": p["text"],
            "show_card_id": card_id,
            "step_hint": p.get("step", "main"),
        }

    closings = session.get("ai_closings") or [
        "今天您分享得很好。我们下次继续一起看图、聊天，慢慢来。"
    ]
    return {
        "reply": closings[min(turn - len(prompts), len(closings) - 1)],
        "show_card_id": None,
        "step_hint": "summary",
    }
