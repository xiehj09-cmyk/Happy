"""CST 个性化练习 · 家属资料上传 + DeepSeek 随机出题"""

from __future__ import annotations

import json
import random
import re
import sqlite3
import uuid
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

from config import (
    BASE_DIR,
    DEEPSEEK_API_KEY,
    DEEPSEEK_BASE_URL,
    DEEPSEEK_MODEL,
    DEEPSEEK_TIMEOUT,
)
from cst_data import get_session
from med_ai_service import deepseek_configured

UPLOAD_ROOT = BASE_DIR / "instance" / "uploads" / "cst_materials"
ALLOWED_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
ALLOWED_TEXT_EXT = {".txt"}
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
DEFAULT_QUESTION_COUNT = 10

THEME_VISUALS = {
    1: [
        {"label": "老茶壶", "emoji": "🫖", "tone": "#c4a574"},
        {"label": "老街灯笼", "emoji": "🏮", "tone": "#c45c48"},
        {"label": "合影相册", "emoji": "🖼️", "tone": "#6b8cae"},
        {"label": "时令水果", "emoji": "🍎", "tone": "#d97b5c"},
        {"label": "茶杯蒸汽", "emoji": "☕", "tone": "#8f6b4a"},
        {"label": "窗台花盆", "emoji": "🪴", "tone": "#5a8f6b"},
    ],
    2: [
        {"label": "清晨鸟鸣", "emoji": "🐦", "tone": "#6b9e78"},
        {"label": "老收音机", "emoji": "📻", "tone": "#7a6b5a"},
        {"label": "雨打屋檐", "emoji": "🌧️", "tone": "#5a7a8f"},
        {"label": "老歌旋律", "emoji": "🎵", "tone": "#8f5a7a"},
        {"label": "钟声", "emoji": "🔔", "tone": "#c4a040"},
        {"label": "灶间沸水", "emoji": "♨️", "tone": "#a06040"},
    ],
    3: [
        {"label": "风筝", "emoji": "🪁", "tone": "#5a8fc4"},
        {"label": "旧书包", "emoji": "🎒", "tone": "#8f6b4a"},
        {"label": "弹珠", "emoji": "🔵", "tone": "#4a6b8f"},
        {"label": "调色板", "emoji": "🎨", "tone": "#c45c8f"},
        {"label": "跳房子", "emoji": "🟨", "tone": "#c4a040"},
        {"label": "小人书", "emoji": "📖", "tone": "#6b5a8f"},
    ],
}

FALLBACK_VISUALS = [
    {"label": "回忆卡片", "emoji": "💬", "tone": "#0f766e"},
    {"label": "温馨一刻", "emoji": "☀️", "tone": "#c4a040"},
    {"label": "熟悉场景", "emoji": "🏠", "tone": "#6b8cae"},
    {"label": "生活点滴", "emoji": "🌸", "tone": "#c45c8f"},
    {"label": "今日练习", "emoji": "✨", "tone": "#5a8f6b"},
    {"label": "轻声细语", "emoji": "🕊️", "tone": "#7a9eb0"},
]


def ensure_practice_tables(db: sqlite3.Connection) -> None:
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS cst_materials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            elder_user_id INTEGER NOT NULL,
            uploaded_by INTEGER NOT NULL,
            kind TEXT NOT NULL DEFAULT 'photo',
            title TEXT NOT NULL DEFAULT '',
            caption TEXT NOT NULL DEFAULT '',
            file_name TEXT,
            file_path TEXT,
            mime_type TEXT,
            text_content TEXT NOT NULL DEFAULT '',
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (elder_user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS cst_practice_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            elder_user_id INTEGER NOT NULL,
            session_num INTEGER NOT NULL,
            seed TEXT NOT NULL,
            questions_json TEXT NOT NULL,
            material_ids_json TEXT NOT NULL DEFAULT '[]',
            created_by INTEGER,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (elder_user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS cst_practice_answers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            question_id TEXT NOT NULL,
            answer_text TEXT NOT NULL,
            answered_by INTEGER NOT NULL,
            answerer_role TEXT NOT NULL DEFAULT 'elder',
            created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            UNIQUE(run_id, question_id, answered_by),
            FOREIGN KEY (run_id) REFERENCES cst_practice_runs(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_cst_materials_elder
            ON cst_materials(elder_user_id, is_active);
        CREATE INDEX IF NOT EXISTS idx_cst_practice_runs_elder
            ON cst_practice_runs(elder_user_id, session_num, status);
        """
    )
    db.commit()
    UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _safe_ext(filename: str) -> str:
    return Path(filename or "").suffix.lower()


def list_materials(
    db: sqlite3.Connection, elder_user_id: int, *, active_only: bool = True
) -> list[dict]:
    sql = "SELECT * FROM cst_materials WHERE elder_user_id = ?"
    params: list[Any] = [elder_user_id]
    if active_only:
        sql += " AND is_active = 1"
    sql += " ORDER BY created_at DESC, id DESC"
    return [dict(r) for r in db.execute(sql, params).fetchall()]


def get_material(db: sqlite3.Connection, material_id: int, elder_user_id: int) -> dict | None:
    row = db.execute(
        "SELECT * FROM cst_materials WHERE id = ? AND elder_user_id = ? AND is_active = 1",
        (material_id, elder_user_id),
    ).fetchone()
    return dict(row) if row else None


def save_material(
    db: sqlite3.Connection,
    *,
    elder_user_id: int,
    uploaded_by: int,
    title: str,
    caption: str,
    kind: str,
    file_storage=None,
    text_content: str = "",
) -> int:
    title = (title or "").strip() or "未命名资料"
    caption = (caption or "").strip()
    text_content = (text_content or "").strip()
    kind = (kind or "note").strip()
    file_name = None
    file_path = None
    mime_type = None

    if file_storage and getattr(file_storage, "filename", None):
        ext = _safe_ext(file_storage.filename)
        if ext in ALLOWED_IMAGE_EXT:
            kind = "photo"
        elif ext in ALLOWED_TEXT_EXT:
            kind = "note"
        else:
            raise ValueError("仅支持图片（jpg/png/webp/gif）或 txt 文本")

        data = file_storage.read()
        if not data:
            raise ValueError("文件为空")
        if len(data) > MAX_UPLOAD_BYTES:
            raise ValueError("文件不能超过 5MB")

        elder_dir = UPLOAD_ROOT / f"elder_{elder_user_id}"
        elder_dir.mkdir(parents=True, exist_ok=True)
        stored = f"{uuid.uuid4().hex}{ext}"
        abs_path = elder_dir / stored
        abs_path.write_bytes(data)
        file_name = Path(file_storage.filename).name[:120]
        file_path = str(abs_path.relative_to(BASE_DIR)).replace("\\", "/")
        mime_type = getattr(file_storage, "mimetype", None) or ""

        if kind == "note" and not text_content and ext in ALLOWED_TEXT_EXT:
            text_content = data.decode("utf-8", errors="replace")[:4000]

    if kind == "note" and not text_content and not file_path:
        raise ValueError("请填写文字资料或上传文件")

    cur = db.execute(
        """
        INSERT INTO cst_materials
            (elder_user_id, uploaded_by, kind, title, caption, file_name, file_path, mime_type, text_content)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            elder_user_id,
            uploaded_by,
            kind,
            title,
            caption,
            file_name,
            file_path,
            mime_type,
            text_content,
        ),
    )
    db.commit()
    return int(cur.lastrowid)


def deactivate_material(db: sqlite3.Connection, material_id: int, elder_user_id: int) -> bool:
    cur = db.execute(
        """
        UPDATE cst_materials SET is_active = 0
        WHERE id = ? AND elder_user_id = ? AND is_active = 1
        """,
        (material_id, elder_user_id),
    )
    db.commit()
    return cur.rowcount > 0


def material_abs_path(material: dict) -> Path | None:
    rel = material.get("file_path") or ""
    if not rel:
        return None
    path = BASE_DIR / rel
    if not path.is_file():
        return None
    return path


def _call_deepseek_json(messages: list[dict], *, temperature: float = 0.85) -> dict:
    if not DEEPSEEK_API_KEY:
        raise RuntimeError("未配置 DEEPSEEK_API_KEY")
    payload = {
        "model": DEEPSEEK_MODEL or "deepseek-v4-flash",
        "messages": messages,
        "thinking": {"type": "disabled"},
        "temperature": temperature,
        "max_tokens": 3200,
        "response_format": {"type": "json_object"},
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        f"{DEEPSEEK_BASE_URL}/chat/completions",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=max(DEEPSEEK_TIMEOUT, 90)) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"DeepSeek API 错误 {exc.code}: {detail[:400]}") from exc

    content = ((data.get("choices") or [{}])[0].get("message") or {}).get("content") or "{}"
    content = content.strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*", "", content)
        content = re.sub(r"\s*```$", "", content)
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", content)
        if not match:
            raise RuntimeError("模型未返回有效 JSON")
        return json.loads(match.group(0))


def render_card_speak_text(
    *,
    session_title: str,
    card_label: str,
    card_caption: str = "",
    ai_prompt: str = "",
) -> dict[str, Any]:
    """用 DeepSeek 把练习题改写成简短、温柔、适合播报的引导语。"""
    fallback = (ai_prompt or "").strip() or f"请看看「{card_label}」，您想起了什么？"
    if len(fallback) > 48:
        fallback = fallback[:46] + "…"

    if not DEEPSEEK_API_KEY:
        return {"ok": True, "text": fallback, "source": "fallback"}

    system = """你是认知刺激疗法（CST）引导员，服务轻中度阿尔茨海默症长者。
必须输出 JSON：{"text":"一句话引导语"}
要求：
1. 语气温柔、鼓励，像家人轻声说话。
2. 只输出一句中文，尽量 12–28 字，最长不超过 36 字。
3. 不要列举选项，不要感叹号过多，不要医学术语。
4. 围绕题目内容提问或邀请分享，重参与、无对错。
"""
    user = (
        f"课次主题：{session_title}\n"
        f"题目标题：{card_label}\n"
        f"题目提示：{card_caption or '无'}\n"
        f"原始引导：{ai_prompt or '无'}\n"
        "请改写成适合语音播报的一句温柔短问。"
    )
    try:
        data = _call_deepseek_json(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.7,
        )
        text = str(data.get("text") or "").strip()
        text = re.sub(r"\s+", "", text)
        if not text:
            text = fallback
        if len(text) > 40:
            text = text[:38] + "…"
        return {"ok": True, "text": text, "source": "deepseek"}
    except Exception:
        return {"ok": True, "text": fallback, "source": "fallback"}


def expand_practice_reply(
    *,
    session_title: str,
    prompt: str,
    transcript: str,
    hint: str = "",
) -> dict[str, Any]:
    """根据长者录音识别文本，用 DeepSeek 温柔扩展话题并回复。"""
    said = (transcript or "").strip()
    topic = (prompt or "").strip() or "今天的话题"
    tip = (hint or "").strip()
    fallback = (
        f"谢谢您说「{said[:16]}」。{('关于' + tip[:12] + '，') if tip else ''}"
        f"您愿意再多说一点吗？"
    )
    if len(fallback) > 56:
        fallback = fallback[:54] + "…"

    if not said:
        return {"ok": True, "reply": "没关系，想好了再说一句就很好。", "source": "fallback"}

    if not DEEPSEEK_API_KEY:
        return {"ok": True, "reply": fallback, "source": "fallback"}

    system = """你是认知刺激疗法（CST）引导员，服务轻中度阿尔茨海默症长者。
必须输出 JSON：{"reply":"回复内容"}
要求：
1. 先温柔肯定长者刚说的内容，再轻轻扩展话题，邀请再分享一点。
2. 语气温柔、简短，像家人说话；共 1–2 句中文，尽量 20–48 字，最长不超过 60 字。
3. 不要纠正对错，不要考试感，不要医学术语，不要一次问很多问题。
4. 不要复述整段原话，点到关键细节即可。
"""
    user = (
        f"课次主题：{session_title}\n"
        f"当前题目：{topic}\n"
        f"题目提示：{tip or '无'}\n"
        f"长者说的话：{said}\n"
        "请给出一句温柔、能扩展话题的回复。"
    )
    try:
        data = _call_deepseek_json(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.75,
        )
        reply = str(data.get("reply") or "").strip()
        reply = re.sub(r"\s+", "", reply)
        if not reply:
            reply = fallback
        if len(reply) > 64:
            reply = reply[:62] + "…"
        return {"ok": True, "reply": reply, "source": "deepseek"}
    except Exception:
        return {"ok": True, "reply": fallback, "source": "fallback"}


def _theme_pool(session_num: int) -> list[dict]:
    return list(THEME_VISUALS.get(session_num) or FALLBACK_VISUALS)


def _fallback_questions(
    session_info: dict,
    materials: list[dict],
    *,
    count: int,
    seed: str,
) -> list[dict]:
    rng = random.Random(seed)
    pool = _theme_pool(int(session_info["num"]))
    base_prompts = list(session_info.get("activities") or [])
    for card in session_info.get("visual_cards") or []:
        if card.get("ai_prompt"):
            base_prompts.append(card["ai_prompt"])
    for m in materials:
        tip = m.get("caption") or m.get("title") or ""
        if tip:
            base_prompts.append(f"看看「{m.get('title') or '这份资料'}」：{tip}。您想起了什么？")
        if m.get("text_content"):
            snippet = str(m["text_content"])[:60]
            base_prompts.append(f"这段话写着「{snippet}…」，您有什么感受？")

    if not base_prompts:
        base_prompts = [f"围绕「{session_info['title']}」，您最先想到什么？"]

    rng.shuffle(base_prompts)
    soft = ["可以说一说", "有点印象", "想再看看", "先跳过"]
    questions = []
    for i in range(count):
        prompt = base_prompts[i % len(base_prompts)]
        visual = rng.choice(pool)
        material = materials[i % len(materials)] if materials else None
        qid = f"q{i + 1}_{uuid.uuid4().hex[:6]}"
        item = {
            "id": qid,
            "prompt": prompt if isinstance(prompt, str) else str(prompt),
            "hint": "慢慢想就好，没有对错。",
            "options": list(soft) if rng.random() < 0.35 else rng.sample(
                ["很熟悉", "有点印象", "不太记得", "想再看看", "让我想起家人", "说不准"],
                k=4,
            ),
            "material_id": material["id"] if material and material.get("kind") == "photo" and i % 2 == 0 else (
                material["id"] if material and i % 3 == 0 else None
            ),
            "visual_emoji": visual["emoji"],
            "visual_label": visual["label"],
            "visual_tone": visual["tone"],
            "source": "fallback",
        }
        if item["material_id"] is None and material and material.get("kind") == "photo" and rng.random() < 0.5:
            item["material_id"] = material["id"]
        questions.append(item)
    rng.shuffle(questions)
    return questions[:count]


def _normalize_questions(
    raw_questions: list,
    *,
    materials: list[dict],
    session_num: int,
    seed: str,
    count: int,
) -> list[dict]:
    rng = random.Random(seed + ":norm")
    mat_by_id = {int(m["id"]): m for m in materials}
    pool = _theme_pool(session_num)
    out: list[dict] = []
    for i, raw in enumerate(raw_questions or []):
        if not isinstance(raw, dict):
            continue
        prompt = str(raw.get("prompt") or "").strip()
        if not prompt:
            continue
        options = raw.get("options") or []
        if not isinstance(options, list):
            options = []
        options = [str(o).strip() for o in options if str(o).strip()][:6]
        if len(options) < 3:
            options = ["可以说一说", "有点印象", "想再看看", "先跳过"]
        mid = raw.get("material_id")
        try:
            mid_int = int(mid) if mid is not None and str(mid).strip() != "" else None
        except (TypeError, ValueError):
            mid_int = None
        if mid_int is not None and mid_int not in mat_by_id:
            mid_int = None
        visual = rng.choice(pool)
        out.append(
            {
                "id": str(raw.get("id") or f"q{i + 1}_{uuid.uuid4().hex[:6]}"),
                "prompt": prompt[:180],
                "hint": str(raw.get("hint") or "慢慢想就好，没有对错。")[:80],
                "options": options,
                "material_id": mid_int,
                "visual_emoji": str(raw.get("visual_emoji") or visual["emoji"])[:8],
                "visual_label": str(raw.get("visual_label") or visual["label"])[:20],
                "visual_tone": str(raw.get("visual_tone") or visual["tone"])[:20],
                "source": "deepseek",
            }
        )
    rng.shuffle(out)
    return out[:count]


def generate_practice_questions(
    db: sqlite3.Connection,
    *,
    elder_user_id: int,
    session_num: int,
    created_by: int | None,
    count: int = DEFAULT_QUESTION_COUNT,
    force_new: bool = True,
) -> dict[str, Any]:
    session_info = get_session(session_num)
    if not session_info:
        raise ValueError("未找到该次 CST 课程")

    materials = list_materials(db, elder_user_id, active_only=True)
    seed = uuid.uuid4().hex
    rng = random.Random(seed)
    sampled = materials[:]
    rng.shuffle(sampled)
    sampled = sampled[: min(8, len(sampled))]

    material_brief = [
        {
            "id": m["id"],
            "kind": m["kind"],
            "title": m["title"],
            "caption": m["caption"],
            "has_image": bool(m.get("file_path") and m["kind"] == "photo"),
            "text_excerpt": (m.get("text_content") or "")[:200],
        }
        for m in sampled
    ]

    questions: list[dict]
    used_deepseek = False
    if deepseek_configured():
        system = """你是认知刺激疗法（CST）题目设计师，服务轻中度阿尔茨海默症长者。
必须输出 JSON（不要 Markdown）：
{
  "questions": [
    {
      "id": "q1",
      "prompt": "温和开放题，中文，≤40字",
      "hint": "一句鼓励，≤20字",
      "options": ["选项A","选项B","选项C","选项D"],
      "material_id": null或资料id整数,
      "visual_emoji": "一个emoji",
      "visual_label": "画面标题",
      "visual_tone": "#十六进制色"
    }
  ]
}
规则：
1. 生成恰好指定数量的题目；每题 4 个选项；无标准对错，偏回忆与感受。
2. 尽量结合家属上传资料（人物、地点、习惯）；有图的资料优先用 material_id。
3. 题目彼此不同，角度随机（颜色/人物/声音/味道/地点/情绪）。
4. 禁止医疗诊断、恐吓、政治与负面新闻。
5. visual_tone 用柔和色，如 #0f766e、#c4a040。
"""
        user_msg = (
            f"随机种子：{seed}\n"
            f"课次：第 {session_num} 次「{session_info['title']}」\n"
            f"主题：{session_info.get('ai_theme') or session_info['title']}\n"
            f"焦点：{session_info.get('ai_focus') or session_info['summary']}\n"
            f"需要题目数：{count}\n"
            f"家属上传资料（可引用）：{json.dumps(material_brief, ensure_ascii=False)}\n"
            f"请结合资料与主题，随机生成 {count} 道互不相同的温和练习题。"
        )
        try:
            data = _call_deepseek_json(
                [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_msg},
                ],
                temperature=0.9,
            )
            questions = _normalize_questions(
                data.get("questions") or [],
                materials=materials,
                session_num=session_num,
                seed=seed,
                count=count,
            )
            used_deepseek = True
        except Exception:
            questions = []

    if len(questions) < count:
        fill = _fallback_questions(
            session_info, materials, count=count, seed=seed + ":fb"
        )
        seen = {q["prompt"] for q in questions}
        for q in fill:
            if q["prompt"] in seen:
                continue
            questions.append(q)
            seen.add(q["prompt"])
            if len(questions) >= count:
                break
        random.Random(seed + ":mix").shuffle(questions)
        questions = questions[:count]

    # 丰富图片：尽量轮询有图的资料
    photo_ids = [m["id"] for m in materials if m.get("kind") == "photo" and m.get("file_path")]
    if photo_ids:
        rng2 = random.Random(seed + ":img")
        rng2.shuffle(photo_ids)
        for i, q in enumerate(questions):
            if not q.get("material_id") and i < len(photo_ids):
                q["material_id"] = photo_ids[i % len(photo_ids)]
            elif not q.get("material_id") and photo_ids and rng2.random() < 0.4:
                q["material_id"] = rng2.choice(photo_ids)

    if force_new:
        db.execute(
            """
            UPDATE cst_practice_runs SET status = 'archived'
            WHERE elder_user_id = ? AND session_num = ? AND status = 'active'
            """,
            (elder_user_id, session_num),
        )

    cur = db.execute(
        """
        INSERT INTO cst_practice_runs
            (elder_user_id, session_num, seed, questions_json, material_ids_json, created_by, status)
        VALUES (?, ?, ?, ?, ?, ?, 'active')
        """,
        (
            elder_user_id,
            session_num,
            seed,
            json.dumps(questions, ensure_ascii=False),
            json.dumps([m["id"] for m in sampled], ensure_ascii=False),
            created_by,
        ),
    )
    db.commit()
    run_id = int(cur.lastrowid)
    return {
        "ok": True,
        "run_id": run_id,
        "seed": seed,
        "question_count": len(questions),
        "used_deepseek": used_deepseek,
        "material_count": len(sampled),
        "questions": enrich_questions_for_view(db, elder_user_id, questions),
    }


def enrich_questions_for_view(
    db: sqlite3.Connection, elder_user_id: int, questions: list[dict]
) -> list[dict]:
    out = []
    for q in questions:
        item = dict(q)
        mid = item.get("material_id")
        item["image_url"] = None
        item["material_title"] = ""
        item["material_caption"] = ""
        if mid:
            mat = get_material(db, int(mid), elder_user_id)
            if mat:
                item["material_title"] = mat.get("title") or ""
                item["material_caption"] = mat.get("caption") or ""
                if mat.get("file_path") and mat.get("kind") == "photo":
                    item["image_url"] = f"/cst/materials/{mat['id']}/file"
        out.append(item)
    return out


def get_active_run(
    db: sqlite3.Connection, elder_user_id: int, session_num: int
) -> dict | None:
    row = db.execute(
        """
        SELECT * FROM cst_practice_runs
        WHERE elder_user_id = ? AND session_num = ? AND status = 'active'
        ORDER BY id DESC LIMIT 1
        """,
        (elder_user_id, session_num),
    ).fetchone()
    if not row:
        return None
    run = dict(row)
    try:
        questions = json.loads(run.get("questions_json") or "[]")
    except json.JSONDecodeError:
        questions = []
    run["questions"] = enrich_questions_for_view(db, elder_user_id, questions)
    run["answers"] = list_answers(db, run["id"])
    answered = sorted({a["question_id"] for a in run["answers"]})
    run["answered_ids"] = answered
    run["progress_percent"] = (
        int(round(100 * len(answered) / len(run["questions"])))
        if run["questions"]
        else 0
    )
    return run


def list_answers(db: sqlite3.Connection, run_id: int) -> list[dict]:
    rows = db.execute(
        """
        SELECT a.*, u.username AS answerer_name
        FROM cst_practice_answers a
        LEFT JOIN users u ON u.id = a.answered_by
        WHERE a.run_id = ?
        ORDER BY a.created_at ASC, a.id ASC
        """,
        (run_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def save_answer(
    db: sqlite3.Connection,
    *,
    run_id: int,
    elder_user_id: int,
    question_id: str,
    answer_text: str,
    answered_by: int,
    answerer_role: str,
) -> dict[str, Any]:
    run = db.execute(
        "SELECT * FROM cst_practice_runs WHERE id = ? AND elder_user_id = ?",
        (run_id, elder_user_id),
    ).fetchone()
    if not run or run["status"] != "active":
        return {"ok": False, "error": "未找到进行中的练习"}
    answer_text = (answer_text or "").strip()
    if not answer_text:
        return {"ok": False, "error": "请选择或填写回答"}
    question_id = (question_id or "").strip()
    try:
        questions = json.loads(run["questions_json"] or "[]")
    except json.JSONDecodeError:
        questions = []
    if not any(str(q.get("id")) == question_id for q in questions):
        return {"ok": False, "error": "题目不存在"}

    db.execute(
        """
        INSERT INTO cst_practice_answers
            (run_id, question_id, answer_text, answered_by, answerer_role, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(run_id, question_id, answered_by) DO UPDATE SET
            answer_text = excluded.answer_text,
            answerer_role = excluded.answerer_role,
            created_at = excluded.created_at
        """,
        (run_id, question_id, answer_text[:200], answered_by, answerer_role, _now()),
    )
    db.commit()
    active = get_active_run(db, elder_user_id, int(run["session_num"]))
    return {"ok": True, "run": active}
