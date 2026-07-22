"""CST 进度与设备绑定 · 数据访问"""

from __future__ import annotations

import sqlite3

from cst_data import CST_SESSIONS, MVP_SESSIONS, get_session


def ensure_cst_tables(db: sqlite3.Connection) -> None:
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS cst_profile (
            user_id INTEGER PRIMARY KEY,
            group_name TEXT NOT NULL DEFAULT '记忆港湾小组',
            theme_song TEXT NOT NULL DEFAULT '一条熟悉的老歌',
            phase TEXT NOT NULL DEFAULT 'intensive',
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS cst_session_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            session_num INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'completed',
            mood TEXT,
            notes TEXT,
            ai_summary TEXT,
            completed_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            UNIQUE(user_id, session_num),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS device_binding (
            user_id INTEGER PRIMARY KEY,
            device_name TEXT NOT NULL DEFAULT '记忆港湾 AI 终端',
            device_code TEXT,
            is_online INTEGER NOT NULL DEFAULT 0,
            last_sync TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
        """
    )
    db.commit()


def get_cst_profile(db: sqlite3.Connection, user_id: int) -> sqlite3.Row:
    row = db.execute(
        "SELECT * FROM cst_profile WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    if row is None:
        db.execute(
            "INSERT INTO cst_profile (user_id) VALUES (?)",
            (user_id,),
        )
        db.commit()
        row = db.execute(
            "SELECT * FROM cst_profile WHERE user_id = ?",
            (user_id,),
        ).fetchone()
    return row


def get_completed_sessions(db: sqlite3.Connection, user_id: int) -> set[int]:
    rows = db.execute(
        "SELECT session_num FROM cst_session_log WHERE user_id = ? AND status = 'completed'",
        (user_id,),
    ).fetchall()
    return {r["session_num"] for r in rows}


def get_session_log(db: sqlite3.Connection, user_id: int, session_num: int):
    return db.execute(
        "SELECT * FROM cst_session_log WHERE user_id = ? AND session_num = ?",
        (user_id, session_num),
    ).fetchone()


def get_all_logs(db: sqlite3.Connection, user_id: int) -> list:
    return db.execute(
        """
        SELECT session_num, mood, notes, ai_summary, completed_at
        FROM cst_session_log WHERE user_id = ?
        ORDER BY session_num ASC
        """,
        (user_id,),
    ).fetchall()


def get_current_session_num(completed: set[int]) -> int:
    for s in CST_SESSIONS:
        if s["num"] not in completed:
            return s["num"]
    return 14


def build_cst_overview(db: sqlite3.Connection, user_id: int) -> dict:
    profile = get_cst_profile(db, user_id)
    completed = get_completed_sessions(db, user_id)
    current = get_current_session_num(completed)
    current_info = get_session(current)
    sessions = []
    for s in CST_SESSIONS:
        num = s["num"]
        log = get_session_log(db, user_id, num)
        sessions.append(
            {
                "num": num,
                "title": s["title"],
                "summary": s["summary"],
                "status": "completed" if num in completed else ("current" if num == current else "pending"),
                "mvp_ready": num in MVP_SESSIONS,
                "completed_at": log["completed_at"] if log else None,
            }
        )
    total = len(CST_SESSIONS)
    done = len(completed)
    return {
        "profile": profile,
        "sessions": sessions,
        "current_num": current,
        "current_title": current_info["title"] if current_info else "",
        "current_mvp_ready": current in MVP_SESSIONS,
        "completed_count": done,
        "total_count": total,
        "progress_percent": round(done / total * 100) if total else 0,
        "phase_label": "强化期（14 次）" if profile["phase"] == "intensive" else "维持期 MCST",
        "all_done": done >= total,
    }


def get_device(db: sqlite3.Connection, user_id: int):
    return db.execute(
        "SELECT * FROM device_binding WHERE user_id = ?",
        (user_id,),
    ).fetchone()
