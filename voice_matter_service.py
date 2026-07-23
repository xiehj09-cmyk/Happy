"""语音事项 · 与小智 MCP / txt 同步"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any


STATUS_OPEN = "open"
STATUS_DONE = "done"
STATUS_CANCELLED = "cancelled"

STATUS_LABELS = {
    STATUS_OPEN: "待完成",
    STATUS_DONE: "已完成",
    STATUS_CANCELLED: "已取消",
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
            recorded_by INTEGER
        )
        """
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_voice_matters_elder_status "
        "ON voice_matters(elder_user_id, status, created_at DESC)"
    )
    db.commit()


def add_matter(
    db: sqlite3.Connection,
    elder_user_id: int,
    body: str,
    *,
    source: str = "xiaozhi",
    recorded_by: int | None = None,
) -> dict[str, Any]:
    text = (body or "").strip()
    if not text:
        raise ValueError("事项内容不能为空")
    cur = db.execute(
        """
        INSERT INTO voice_matters (elder_user_id, body, source, recorded_by)
        VALUES (?, ?, ?, ?)
        """,
        (elder_user_id, text, source or "xiaozhi", recorded_by),
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
    sql += " ORDER BY id DESC LIMIT ?"
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
        # 优先未完成事项
        rows = list_matters(db, elder_user_id, status=STATUS_OPEN, keyword=key, limit=5)
        if not rows:
            # 子序列软匹配
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
    return item
