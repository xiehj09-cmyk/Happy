"""老人代办清单 · 网站与小智 MCP 共用（原 voice_matters）"""

from __future__ import annotations

import re
import sqlite3
from datetime import datetime, timedelta
from typing import Any


STATUS_OPEN = "open"
STATUS_DONE = "done"
STATUS_CANCELLED = "cancelled"

STATUS_LABELS = {
    STATUS_OPEN: "待完成",
    STATUS_DONE: "已完成",
    STATUS_CANCELLED: "已取消",
}

SOURCE_LABELS = {
    "xiaozhi": "小智",
    "web": "网站",
    "family": "家属",
}


def ensure_voice_matter_tables(db: sqlite3.Connection) -> None:
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS voice_matters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            elder_user_id INTEGER NOT NULL,
            body TEXT NOT NULL,
            source TEXT NOT NULL DEFAULT 'xiaozhi',
            status TEXT NOT NULL DEFAULT 'open',
            created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            completed_at TEXT,
            recorded_by INTEGER,
            due_at TEXT
        )
        """
    )
    cols = {row[1] for row in db.execute("PRAGMA table_info(voice_matters)").fetchall()}
    if "due_at" not in cols:
        db.execute("ALTER TABLE voice_matters ADD COLUMN due_at TEXT")
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_voice_matters_elder_status "
        "ON voice_matters(elder_user_id, status, created_at DESC)"
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_voice_matters_due "
        "ON voice_matters(elder_user_id, status, due_at)"
    )
    db.commit()


def normalize_due_at(raw: str | None) -> str | None:
    """
    把提醒时间规范成 'YYYY-MM-DD HH:MM:SS'。
    支持：完整日期时间、今天的 HH:MM、相对「今天/明天 + 时间」。
    """
    text = (raw or "").strip()
    if not text:
        return None

    # datetime-local: 2026-07-24T15:00
    text = text.replace("T", " ").replace("/", "-")

    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
    ):
        try:
            dt = datetime.strptime(text, fmt)
            if fmt == "%Y-%m-%d":
                dt = dt.replace(hour=9, minute=0, second=0)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            pass

    # 仅时间：15:00 / 15:00:00 → 今天
    m = re.fullmatch(r"(\d{1,2}):(\d{2})(?::(\d{2}))?", text)
    if m:
        hour, minute = int(m.group(1)), int(m.group(2))
        second = int(m.group(3) or 0)
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            now = datetime.now()
            dt = now.replace(hour=hour, minute=minute, second=second, microsecond=0)
            return dt.strftime("%Y-%m-%d %H:%M:%S")

    # 今天/明天 + 时间
    m2 = re.match(
        r"^(今天|明天)\s*(\d{1,2})[:点时](\d{0,2})\s*分?$",
        text,
    )
    if m2:
        day_word, hour_s, min_s = m2.group(1), m2.group(2), m2.group(3)
        hour, minute = int(hour_s), int(min_s or 0)
        base = datetime.now().replace(second=0, microsecond=0)
        if day_word == "明天":
            base = base + timedelta(days=1)
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            dt = base.replace(hour=hour, minute=minute)
            return dt.strftime("%Y-%m-%d %H:%M:%S")

    # 下午3点 / 上午10点
    m3 = re.match(r"^(今天|明天)?\s*(上午|下午|晚上)?\s*(\d{1,2})\s*点\s*(\d{0,2})\s*分?$", text)
    if m3:
        day_word, ampm, hour_s, min_s = m3.groups()
        hour, minute = int(hour_s), int(min_s or 0)
        if ampm == "下午" and 1 <= hour <= 11:
            hour += 12
        elif ampm == "晚上" and hour < 12:
            hour += 12
        elif ampm == "上午" and hour == 12:
            hour = 0
        base = datetime.now().replace(second=0, microsecond=0)
        if day_word == "明天":
            base = base + timedelta(days=1)
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            dt = base.replace(hour=hour, minute=minute)
            return dt.strftime("%Y-%m-%d %H:%M:%S")

    raise ValueError("提醒时间格式不正确，可用如：2026-07-24 15:00、15:00、今天下午3点")


def add_matter(
    db: sqlite3.Connection,
    elder_user_id: int,
    body: str,
    *,
    source: str = "xiaozhi",
    recorded_by: int | None = None,
    due_at: str | None = None,
) -> dict[str, Any]:
    text = (body or "").strip()
    if not text:
        raise ValueError("事项内容不能为空")
    due = normalize_due_at(due_at) if due_at else None
    cur = db.execute(
        """
        INSERT INTO voice_matters (elder_user_id, body, source, recorded_by, due_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (elder_user_id, text, source or "xiaozhi", recorded_by, due),
    )
    db.commit()
    return get_matter(db, int(cur.lastrowid), elder_user_id)  # type: ignore[arg-type]


def get_matter(
    db: sqlite3.Connection, matter_id: int, elder_user_id: int
) -> dict[str, Any] | None:
    row = db.execute(
        "SELECT * FROM voice_matters WHERE id = ? AND elder_user_id = ?",
        (matter_id, elder_user_id),
    ).fetchone()
    return _serialize(row) if row else None


def list_matters(
    db: sqlite3.Connection,
    elder_user_id: int,
    *,
    status: str | None = STATUS_OPEN,
    keyword: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    limit = max(1, min(50, int(limit or 20)))
    sql = "SELECT * FROM voice_matters WHERE elder_user_id = ?"
    params: list[Any] = [elder_user_id]
    if status:
        sql += " AND status = ?"
        params.append(status)
    if keyword and keyword.strip():
        sql += " AND body LIKE ?"
        params.append(f"%{keyword.strip()}%")
    # 待办优先：未完成在前；有提醒时间的按时间升序；否则按新建倒序
    sql += """
        ORDER BY
          CASE status WHEN 'open' THEN 0 WHEN 'done' THEN 1 ELSE 2 END,
          CASE WHEN due_at IS NULL OR due_at = '' THEN 1 ELSE 0 END,
          due_at ASC,
          id DESC
        LIMIT ?
    """
    params.append(limit)
    rows = db.execute(sql, params).fetchall()
    return [_serialize(r) for r in rows]


def complete_matter(
    db: sqlite3.Connection,
    elder_user_id: int,
    *,
    matter_id: int | None = None,
    keyword: str | None = None,
) -> dict[str, Any] | None:
    matter = None
    if matter_id:
        matter = get_matter(db, matter_id, elder_user_id)
    elif keyword and keyword.strip():
        key = keyword.strip()
        rows = list_matters(db, elder_user_id, status=STATUS_OPEN, keyword=key, limit=5)
        if not rows:
            open_rows = list_matters(db, elder_user_id, status=STATUS_OPEN, limit=30)
            rows = [r for r in open_rows if _soft_match(r["body"], key)]
        matter = rows[0] if rows else None
    if not matter:
        return None
    if matter["status"] == STATUS_DONE:
        return matter
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db.execute(
        """
        UPDATE voice_matters
        SET status = ?, completed_at = ?
        WHERE id = ? AND elder_user_id = ?
        """,
        (STATUS_DONE, now, matter["id"], elder_user_id),
    )
    db.commit()
    return get_matter(db, matter["id"], elder_user_id)


def reopen_matter(
    db: sqlite3.Connection, elder_user_id: int, matter_id: int
) -> dict[str, Any] | None:
    matter = get_matter(db, matter_id, elder_user_id)
    if not matter:
        return None
    db.execute(
        """
        UPDATE voice_matters
        SET status = ?, completed_at = NULL
        WHERE id = ? AND elder_user_id = ?
        """,
        (STATUS_OPEN, matter_id, elder_user_id),
    )
    db.commit()
    return get_matter(db, matter_id, elder_user_id)


def delete_matter(
    db: sqlite3.Connection, elder_user_id: int, matter_id: int
) -> bool:
    cur = db.execute(
        "DELETE FROM voice_matters WHERE id = ? AND elder_user_id = ?",
        (matter_id, elder_user_id),
    )
    db.commit()
    return cur.rowcount > 0


def speak_matters_summary(items: list[dict[str, Any]], *, keyword: str = "") -> str:
    if not items:
        if keyword:
            return f"没有找到包含「{keyword}」的代办。"
        return "代办清单还是空的。可以说「帮我记一下今天下午三点吃药」。"
    lines = []
    for i, m in enumerate(items, 1):
        due = m.get("due_at_label") or ""
        st = m.get("status_label") or ""
        due_part = f"，提醒 {due}" if due else ""
        lines.append(f"{i}. {m.get('body')}（{st}{due_part}）")
    head = (
        f"找到 {len(items)} 条与「{keyword}」相关的代办："
        if keyword
        else f"代办清单共 {len(items)} 条："
    )
    return head + "\n" + "\n".join(lines)


def _soft_match(line: str, key: str) -> bool:
    if not key:
        return True
    if key in line:
        return True
    i = 0
    for ch in line:
        if i < len(key) and ch == key[i]:
            i += 1
        if i >= len(key):
            return True
    return False


def _serialize(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    item["status_label"] = STATUS_LABELS.get(item.get("status") or "", item.get("status") or "")
    item["source_label"] = SOURCE_LABELS.get(item.get("source") or "", item.get("source") or "")
    due = (item.get("due_at") or "").strip()
    item["due_at_label"] = _format_due_label(due) if due else ""
    return item


def _format_due_label(due: str) -> str:
    try:
        dt = datetime.strptime(due[:19], "%Y-%m-%d %H:%M:%S")
    except ValueError:
        try:
            dt = datetime.strptime(due[:16], "%Y-%m-%d %H:%M")
        except ValueError:
            return due
    today = datetime.now().date()
    if dt.date() == today:
        return f"今天 {dt.strftime('%H:%M')}"
    if dt.date() == today + timedelta(days=1):
        return f"明天 {dt.strftime('%H:%M')}"
    return dt.strftime("%m-%d %H:%M")
