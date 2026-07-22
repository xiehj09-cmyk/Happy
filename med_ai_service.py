"""DeepSeek 智能加药：联网检索说明书要点 + V4 Flash 整理入库"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from html import unescape
from typing import Any

from config import (
    DEEPSEEK_API_KEY,
    DEEPSEEK_BASE_URL,
    DEEPSEEK_MODEL,
    DEEPSEEK_TIMEOUT,
)
from medication_service import PLACE_OPTIONS, add_medication

DISCLAIMER = "仅供照护参考，不能替代医嘱。具体用药请咨询医生或药师。"

SYSTEM_PROMPT = """你是「记忆港湾」用药助手，帮助家属用自然语言为老人整理用药计划。
你只能根据用户消息与提供的「联网检索摘要」整理信息，不要编造说明书未出现的适应症或剂量。
若检索不足，请降低 confidence，并在 reply 中说明需人工核对。

必须输出 JSON（不要 Markdown），字段如下：
{
  "intent": "add_medication" | "chat" | "clarify",
  "drug_name": "规范药名",
  "alias": "适合老人记忆的简单叫法",
  "category": "药品类型，如解热镇痛/抗痴呆/降压等",
  "dose": "建议剂量写法，如 0.2g 或 1片",
  "schedule_time": "HH:MM 24小时制建议服药时间",
  "usage_summary": "用法摘要（≤80字）",
  "place_area": "放置区域建议，须从给定列表选一个或空字符串",
  "confidence": 0到1的小数,
  "reply": "给家属看的中文回复"
}

规则：
1. 用户明确要「加入/添加/帮老人加」某药时，intent=add_medication。
2. 信息不清时 intent=clarify，不要假装已添加。
3. 闲聊或询问说明时 intent=chat。
4. place_area 只能是：客厅药盒、卧室床头、厨房药柜、餐厅桌边、冰箱冷藏、随身小药盒、其他，或空。
5. reply 末尾不要重复长篇免责声明（界面已有）。
"""


def deepseek_configured() -> bool:
    return bool(DEEPSEEK_API_KEY)


def _http_get(url: str, timeout: int = 12) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "MemoryHarborMedBot/1.0 (+local-care-app)",
            "Accept": "text/html,application/json,*/*",
        },
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
        charset = "utf-8"
        ctype = resp.headers.get_content_charset()
        if ctype:
            charset = ctype
        return raw.decode(charset, errors="replace")


def _strip_html(text: str) -> str:
    text = re.sub(r"(?is)<script.*?>.*?</script>", " ", text)
    text = re.sub(r"(?is)<style.*?>.*?</style>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_drug_query(message: str) -> str | None:
    text = (message or "").strip()
    if not text:
        return None
    patterns = [
        r"(?:加入|添加|帮(?:老人)?加|给老人加|增加)\s*[「『\"']?([^「」『』\"'\s，。！？、]{1,20})",
        r"把\s*([^，。！？\s]{1,20})\s*加[入到进]",
        r"^([^，。！？\s]{2,20})\s*(?:说明书|用法|怎么吃)",
    ]
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            name = m.group(1).strip("的了吗呢啊呀")
            if name and name not in {"一下", "这个", "那个", "药物", "药品"}:
                return name
    # 短句直接当药名试探
    if 2 <= len(text) <= 12 and re.fullmatch(r"[\u4e00-\u9fffA-Za-z0-9·\-]+", text):
        return text
    return None


def search_drug_online(drug_name: str) -> dict[str, Any]:
    """联网检索药品相关摘要（说明书要点 / 类型），供模型整理。"""
    snippets: list[str] = []
    sources: list[str] = []
    query = f"{drug_name} 药品说明书 用法用量 适应症"

    # 1) DuckDuckGo Instant Answer
    try:
        ddg_url = "https://api.duckduckgo.com/?" + urllib.parse.urlencode(
            {"q": query, "format": "json", "no_redirect": 1, "no_html": 1}
        )
        data = json.loads(_http_get(ddg_url, timeout=10))
        if data.get("AbstractText"):
            snippets.append(str(data["AbstractText"]))
            if data.get("AbstractURL"):
                sources.append(str(data["AbstractURL"]))
        for topic in data.get("RelatedTopics") or []:
            if isinstance(topic, dict) and topic.get("Text"):
                snippets.append(str(topic["Text"]))
            elif isinstance(topic, dict):
                for sub in topic.get("Topics") or []:
                    if isinstance(sub, dict) and sub.get("Text"):
                        snippets.append(str(sub["Text"]))
        for item in data.get("Results") or []:
            if isinstance(item, dict) and item.get("Text"):
                snippets.append(str(item["Text"]))
    except Exception as exc:  # noqa: BLE001
        snippets.append(f"[DuckDuckGo 检索失败: {exc}]")

    # 2) 中文维基百科摘要
    try:
        wiki_api = "https://zh.wikipedia.org/w/api.php?" + urllib.parse.urlencode(
            {
                "action": "query",
                "format": "json",
                "prop": "extracts",
                "exintro": 1,
                "explaintext": 1,
                "redirects": 1,
                "titles": drug_name,
            }
        )
        wiki = json.loads(_http_get(wiki_api, timeout=10))
        pages = (wiki.get("query") or {}).get("pages") or {}
        for page in pages.values():
            extract = (page.get("extract") or "").strip()
            if extract and page.get("pageid", -1) != -1:
                snippets.append(extract[:800])
                title = page.get("title") or drug_name
                sources.append(f"https://zh.wikipedia.org/wiki/{urllib.parse.quote(title)}")
                break
    except Exception as exc:  # noqa: BLE001
        snippets.append(f"[维基百科检索失败: {exc}]")

    # 3) DuckDuckGo HTML 结果页摘录（补充）
    try:
        html_url = "https://html.duckduckgo.com/html/?" + urllib.parse.urlencode({"q": query})
        html = _http_get(html_url, timeout=12)
        texts = re.findall(r'class="result__snippet[^"]*"[^>]*>(.*?)</a>', html, flags=re.I | re.S)
        if not texts:
            texts = re.findall(r'class="result__snippet[^"]*"[^>]*>(.*?)</(?:a|td|div)>', html, flags=re.I | re.S)
        for raw in texts[:5]:
            cleaned = _strip_html(raw)
            if cleaned:
                snippets.append(cleaned)
    except Exception as exc:  # noqa: BLE001
        snippets.append(f"[网页检索失败: {exc}]")

    # 去重压缩
    uniq: list[str] = []
    seen: set[str] = set()
    for s in snippets:
        key = s[:80]
        if key in seen:
            continue
        seen.add(key)
        uniq.append(s[:500])
        if len(uniq) >= 8:
            break

    return {
        "query": query,
        "snippets": uniq,
        "sources": sources[:5],
        "text": "\n".join(f"- {s}" for s in uniq) if uniq else "未检索到有效说明书摘要。",
    }


def call_deepseek(messages: list[dict], *, json_mode: bool = True) -> str:
    if not DEEPSEEK_API_KEY:
        raise RuntimeError("未配置 DEEPSEEK_API_KEY")

    payload: dict[str, Any] = {
        "model": DEEPSEEK_MODEL or "deepseek-v4-flash",
        "messages": messages,
        "thinking": {"type": "disabled"},
        "temperature": 0.2,
        "max_tokens": 1200,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    url = f"{DEEPSEEK_BASE_URL}/chat/completions"
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=DEEPSEEK_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"DeepSeek API 错误 {exc.code}: {detail[:300]}") from exc

    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError("DeepSeek 无返回内容")
    message = choices[0].get("message") or {}
    content = (message.get("content") or "").strip()
    if not content:
        raise RuntimeError("DeepSeek 返回空内容")
    return content


def _parse_model_json(raw: str) -> dict:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{.*\}", text, flags=re.S)
    if m:
        return json.loads(m.group(0))
    raise ValueError("模型未返回合法 JSON")


def _normalize_time(value: str) -> str:
    value = (value or "").strip()
    m = re.fullmatch(r"(\d{1,2}):(\d{2})", value)
    if not m:
        return "08:00"
    hh, mm = int(m.group(1)), int(m.group(2))
    if hh > 23 or mm > 59:
        return "08:00"
    return f"{hh:02d}:{mm:02d}"


def _normalize_place(value: str) -> str:
    value = (value or "").strip()
    return value if value in PLACE_OPTIONS else ""


def process_smart_add(
    db,
    *,
    elder_user_id: int,
    family_user_id: int,
    message: str,
    elder_username: str = "",
) -> dict[str, Any]:
    """处理家属自然语言加药：检索 → DeepSeek 整理 → 确认意图后写入药单。"""
    message = (message or "").strip()
    if not message:
        return {
            "ok": False,
            "reply": "请输入要添加的药物，例如「加入布洛芬」。",
            "added": False,
            "disclaimer": DISCLAIMER,
        }
    if not deepseek_configured():
        return {
            "ok": False,
            "reply": "智能加药未配置 DeepSeek API Key，请联系管理员在 .env 中设置 DEEPSEEK_API_KEY。",
            "added": False,
            "disclaimer": DISCLAIMER,
        }

    hint_name = extract_drug_query(message) or ""
    search_name = hint_name or message[:20]
    search = search_drug_online(search_name)

    user_payload = {
        "family_message": message,
        "elder_name": elder_username or "老人",
        "guessed_drug": hint_name,
        "place_options": PLACE_OPTIONS,
        "web_search": {
            "query": search["query"],
            "summary": search["text"],
            "sources": search["sources"],
        },
    }
    raw = call_deepseek(
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": "请根据以下 JSON 整理用药建议并输出规定 JSON：\n"
                + json.dumps(user_payload, ensure_ascii=False),
            },
        ],
        json_mode=True,
    )
    parsed = _parse_model_json(raw)

    intent = str(parsed.get("intent") or "clarify").strip()
    drug_name = str(parsed.get("drug_name") or hint_name or "").strip()
    alias = str(parsed.get("alias") or "").strip()
    category = str(parsed.get("category") or "").strip()
    dose = str(parsed.get("dose") or "按医嘱").strip() or "按医嘱"
    schedule_time = _normalize_time(str(parsed.get("schedule_time") or "08:00"))
    usage_summary = str(parsed.get("usage_summary") or "").strip()
    place_area = _normalize_place(str(parsed.get("place_area") or ""))
    try:
        confidence = float(parsed.get("confidence") or 0)
    except (TypeError, ValueError):
        confidence = 0.0
    reply = str(parsed.get("reply") or "").strip()

    result: dict[str, Any] = {
        "ok": True,
        "intent": intent,
        "added": False,
        "confidence": confidence,
        "search_query": search["query"],
        "search_sources": search["sources"],
        "proposal": {
            "drug_name": drug_name,
            "alias": alias,
            "category": category,
            "dose": dose,
            "schedule_time": schedule_time,
            "usage_summary": usage_summary,
            "place_area": place_area,
        },
        "disclaimer": DISCLAIMER,
        "reply": reply or "已处理您的消息。",
    }

    should_add = (
        intent == "add_medication"
        and bool(drug_name)
        and confidence >= 0.55
    )
    if should_add:
        note_parts = [p for p in [category and f"类型：{category}", usage_summary] if p]
        note = "；".join(note_parts) or "智能加药整理"
        med_id = add_medication(
            db,
            elder_user_id,
            name=drug_name,
            dose=dose,
            schedule_time=schedule_time,
            note=note,
            alias=alias,
            place_area=place_area,
            catalog_id=None,
            created_by=family_user_id,
        )
        result["added"] = True
        result["medication_id"] = med_id
        if "已添加" not in result["reply"] and "加入" not in result["reply"]:
            show = f"{alias}（{drug_name}）" if alias else drug_name
            result["reply"] = (
                f"已为老人加入「{show}」。建议时间 {schedule_time}，剂量 {dose}。"
                + (f"用法：{usage_summary}" if usage_summary else "")
            )
    elif intent == "add_medication" and not should_add:
        result["reply"] = (
            reply
            or "已识别到加药意图，但说明书信息不足或药名不明确，暂未自动写入。请补充药名或改用下方「添加药物」。"
        )
        result["ok"] = True

    return result
