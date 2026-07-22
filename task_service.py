"""照护任务清单 · 多步骤日程、今日进度、本周概况"""

from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, timedelta
from typing import Any

STATUS_NOT_STARTED = "not_started"
STATUS_IN_PROGRESS = "in_progress"
STATUS_PAUSED = "paused"
STATUS_COMPLETED = "completed"

STEP_PENDING = "pending"
STEP_DONE = "done"
STEP_SKIPPED = "skipped"
STEP_PROXY = "proxy_done"

STEP_DONE_SET = {STEP_DONE, STEP_SKIPPED, STEP_PROXY}

STATUS_LABELS = {
    STATUS_NOT_STARTED: "未开始",
    STATUS_IN_PROGRESS: "进行中",
    STATUS_PAUSED: "已暂停",
    STATUS_COMPLETED: "已完成",
}

STEP_LABELS = {
    STEP_PENDING: "待做",
    STEP_DONE: "已完成",
    STEP_SKIPPED: "已跳过",
    STEP_PROXY: "家属代完成",
}


def ensure_task_tables(db: sqlite3.Connection) -> None:
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS care_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            elder_user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            note TEXT NOT NULL DEFAULT '',
            schedule_time TEXT NOT NULL DEFAULT '',
            is_active INTEGER NOT NULL DEFAULT 1,
            sort_order INTEGER NOT NULL DEFAULT 0,
            created_by INTEGER,
            created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (elder_user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS care_task_steps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL,
            step_order INTEGER NOT NULL,
            content TEXT NOT NULL,
            FOREIGN KEY (task_id) REFERENCES care_tasks(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS care_task_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL,
            elder_user_id INTEGER NOT NULL,
            run_date TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'not_started',
            current_step_index INTEGER NOT NULL DEFAULT 0,
            steps_snapshot TEXT,
            started_at TEXT,
            paused_at TEXT,
            completed_at TEXT,
            updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            UNIQUE(task_id, run_date),
            FOREIGN KEY (task_id) REFERENCES care_tasks(id) ON DELETE CASCADE,
            FOREIGN KEY (elder_user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS care_task_step_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            step_index INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            completed_by INTEGER,
            completed_at TEXT,
            UNIQUE(run_id, step_index),
            FOREIGN KEY (run_id) REFERENCES care_task_runs(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS care_task_actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            action_id TEXT NOT NULL,
            result_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            UNIQUE(run_id, action_id),
            FOREIGN KEY (run_id) REFERENCES care_task_runs(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_care_tasks_elder
            ON care_tasks(elder_user_id, is_active);
        CREATE INDEX IF NOT EXISTS idx_care_runs_elder_date
            ON care_task_runs(elder_user_id, run_date);
        """
    )
    db.commit()


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _today() -> str:
    return date.today().isoformat()


def _parse_steps_snapshot(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    return [str(x).strip() for x in data if str(x).strip()]


def list_template_steps(db: sqlite3.Connection, task_id: int) -> list[dict]:
    rows = db.execute(
        """
        SELECT id, step_order, content
        FROM care_task_steps
        WHERE task_id = ?
        ORDER BY step_order ASC, id ASC
        """,
        (task_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def list_tasks(
    db: sqlite3.Connection, elder_user_id: int, *, active_only: bool = True
) -> list[dict]:
    sql = """
        SELECT * FROM care_tasks
        WHERE elder_user_id = ?
    """
    params: list[Any] = [elder_user_id]
    if active_only:
        sql += " AND is_active = 1"
    sql += " ORDER BY sort_order ASC, schedule_time ASC, id ASC"
    rows = db.execute(sql, params).fetchall()
    out = []
    for row in rows:
        item = dict(row)
        item["steps"] = list_template_steps(db, item["id"])
        item["step_count"] = len(item["steps"])
        out.append(item)
    return out


def get_task(db: sqlite3.Connection, task_id: int, elder_user_id: int) -> dict | None:
    row = db.execute(
        "SELECT * FROM care_tasks WHERE id = ? AND elder_user_id = ?",
        (task_id, elder_user_id),
    ).fetchone()
    if not row:
        return None
    item = dict(row)
    item["steps"] = list_template_steps(db, task_id)
    item["step_count"] = len(item["steps"])
    return item


def create_task(
    db: sqlite3.Connection,
    elder_user_id: int,
    *,
    title: str,
    steps: list[str],
    note: str = "",
    schedule_time: str = "",
    created_by: int | None = None,
) -> int:
    title = (title or "").strip()
    cleaned = [s.strip() for s in steps if (s or "").strip()]
    if not title:
        raise ValueError("请填写任务名称")
    if len(cleaned) < 1:
        raise ValueError("至少需要一步")
    schedule_time = (schedule_time or "").strip()
    cur = db.execute(
        """
        INSERT INTO care_tasks (elder_user_id, title, note, schedule_time, created_by)
        VALUES (?, ?, ?, ?, ?)
        """,
        (elder_user_id, title, (note or "").strip(), schedule_time, created_by),
    )
    task_id = int(cur.lastrowid)
    for i, content in enumerate(cleaned, start=1):
        db.execute(
            "INSERT INTO care_task_steps (task_id, step_order, content) VALUES (?, ?, ?)",
            (task_id, i, content),
        )
    db.commit()
    return task_id


def update_task(
    db: sqlite3.Connection,
    task_id: int,
    elder_user_id: int,
    *,
    title: str,
    steps: list[str],
    note: str = "",
    schedule_time: str = "",
) -> bool:
    """更新任务模板。已开始的今日 run 仍使用 steps_snapshot，不受影响。"""
    task = get_task(db, task_id, elder_user_id)
    if not task or not task["is_active"]:
        return False
    title = (title or "").strip()
    cleaned = [s.strip() for s in steps if (s or "").strip()]
    if not title or not cleaned:
        raise ValueError("名称与步骤不能为空")
    db.execute(
        """
        UPDATE care_tasks
        SET title = ?, note = ?, schedule_time = ?, updated_at = ?
        WHERE id = ? AND elder_user_id = ?
        """,
        (title, (note or "").strip(), (schedule_time or "").strip(), _now(), task_id, elder_user_id),
    )
    db.execute("DELETE FROM care_task_steps WHERE task_id = ?", (task_id,))
    for i, content in enumerate(cleaned, start=1):
        db.execute(
            "INSERT INTO care_task_steps (task_id, step_order, content) VALUES (?, ?, ?)",
            (task_id, i, content),
        )
    db.commit()
    return True


def deactivate_task(db: sqlite3.Connection, task_id: int, elder_user_id: int) -> bool:
    cur = db.execute(
        """
        UPDATE care_tasks SET is_active = 0, updated_at = ?
        WHERE id = ? AND elder_user_id = ? AND is_active = 1
        """,
        (_now(), task_id, elder_user_id),
    )
    db.commit()
    return cur.rowcount > 0


def _get_run_row(db: sqlite3.Connection, run_id: int) -> sqlite3.Row | None:
    return db.execute("SELECT * FROM care_task_runs WHERE id = ?", (run_id,)).fetchone()


def _ensure_step_logs(db: sqlite3.Connection, run_id: int, step_count: int) -> None:
    for i in range(step_count):
        db.execute(
            """
            INSERT OR IGNORE INTO care_task_step_logs (run_id, step_index, status)
            VALUES (?, ?, ?)
            """,
            (run_id, i, STEP_PENDING),
        )


def ensure_today_run(
    db: sqlite3.Connection, task_id: int, elder_user_id: int, day: str | None = None
) -> dict:
    day = day or _today()
    row = db.execute(
        """
        SELECT * FROM care_task_runs
        WHERE task_id = ? AND run_date = ?
        """,
        (task_id, day),
    ).fetchone()
    if row:
        return _hydrate_run(db, dict(row))

    db.execute(
        """
        INSERT INTO care_task_runs (task_id, elder_user_id, run_date, status, current_step_index)
        VALUES (?, ?, ?, ?, 0)
        """,
        (task_id, elder_user_id, day, STATUS_NOT_STARTED),
    )
    db.commit()
    row = db.execute(
        "SELECT * FROM care_task_runs WHERE task_id = ? AND run_date = ?",
        (task_id, day),
    ).fetchone()
    return _hydrate_run(db, dict(row))


def _lock_snapshot_if_needed(db: sqlite3.Connection, run: dict) -> dict:
    """首次真正开始时锁定步骤快照，之后模板改动不影响今天。"""
    if run.get("steps_snapshot"):
        return run
    task = get_task(db, run["task_id"], run["elder_user_id"])
    if not task:
        raise ValueError("任务不存在")
    steps = [s["content"] for s in task["steps"]]
    if not steps:
        raise ValueError("任务没有步骤")
    snapshot = json.dumps(steps, ensure_ascii=False)
    now = _now()
    db.execute(
        """
        UPDATE care_task_runs
        SET steps_snapshot = ?, started_at = COALESCE(started_at, ?), updated_at = ?
        WHERE id = ?
        """,
        (snapshot, now, now, run["id"]),
    )
    _ensure_step_logs(db, run["id"], len(steps))
    db.commit()
    refreshed = _get_run_row(db, run["id"])
    return _hydrate_run(db, dict(refreshed))


def _step_logs_map(db: sqlite3.Connection, run_id: int) -> dict[int, dict]:
    rows = db.execute(
        "SELECT * FROM care_task_step_logs WHERE run_id = ? ORDER BY step_index",
        (run_id,),
    ).fetchall()
    return {int(r["step_index"]): dict(r) for r in rows}


def _hydrate_run(db: sqlite3.Connection, run: dict) -> dict:
    snapshot = _parse_steps_snapshot(run.get("steps_snapshot"))
    task = get_task(db, run["task_id"], run["elder_user_id"])
    template_steps = [s["content"] for s in (task["steps"] if task else [])]
    # 未开始且无快照时，展示用模板；已锁定则用快照
    effective_steps = snapshot if snapshot else template_steps
    logs = _step_logs_map(db, run["id"])
    step_details = []
    done_count = 0
    for i, content in enumerate(effective_steps):
        log = logs.get(i) or {"status": STEP_PENDING}
        st = log.get("status") or STEP_PENDING
        if st in STEP_DONE_SET:
            done_count += 1
        step_details.append(
            {
                "index": i,
                "content": content,
                "status": st,
                "status_label": STEP_LABELS.get(st, st),
                "is_current": (
                    run["status"] != STATUS_COMPLETED
                    and i == int(run["current_step_index"])
                ),
                "completed_at": log.get("completed_at"),
            }
        )
    total = len(effective_steps)
    progress_percent = int(round(100 * done_count / total)) if total else 0
    current_index = int(run["current_step_index"] or 0)
    current_step = None
    if total and run["status"] != STATUS_COMPLETED and current_index < total:
        current_step = step_details[current_index]

    run["task"] = task
    run["title"] = task["title"] if task else "任务"
    run["note"] = task["note"] if task else ""
    run["schedule_time"] = task["schedule_time"] if task else ""
    run["steps"] = step_details
    run["steps_locked"] = bool(snapshot)
    run["total_steps"] = total
    run["done_count"] = done_count
    run["progress_percent"] = progress_percent
    run["status_label"] = STATUS_LABELS.get(run["status"], run["status"])
    run["current_step"] = current_step
    run["current_step_index"] = current_index
    return run


def board_today(db: sqlite3.Connection, elder_user_id: int, day: str | None = None) -> dict:
    day = day or _today()
    tasks = list_tasks(db, elder_user_id, active_only=True)
    items = []
    for task in tasks:
        run = ensure_today_run(db, task["id"], elder_user_id, day)
        items.append(run)

    completed = sum(1 for r in items if r["status"] == STATUS_COMPLETED)
    in_progress = sum(1 for r in items if r["status"] in {STATUS_IN_PROGRESS, STATUS_PAUSED})
    total = len(items)
    overall = int(round(100 * completed / total)) if total else 0
    return {
        "date": day,
        "tasks": items,
        "total": total,
        "completed_count": completed,
        "in_progress_count": in_progress,
        "pending_count": total - completed,
        "overall_percent": overall,
    }


def week_overview(db: sqlite3.Connection, elder_user_id: int, days: int = 7) -> list[dict]:
    tasks = list_tasks(db, elder_user_id, active_only=True)
    task_ids = [t["id"] for t in tasks]
    total_active = len(task_ids)
    out = []
    today = date.today()
    for offset in range(days - 1, -1, -1):
        d = today - timedelta(days=offset)
        day_s = d.isoformat()
        completed = 0
        if task_ids:
            placeholders = ",".join("?" * len(task_ids))
            row = db.execute(
                f"""
                SELECT COUNT(*) AS c FROM care_task_runs
                WHERE elder_user_id = ? AND run_date = ? AND status = ?
                  AND task_id IN ({placeholders})
                """,
                (elder_user_id, day_s, STATUS_COMPLETED, *task_ids),
            ).fetchone()
            completed = int(row["c"] if row else 0)
        percent = int(round(100 * completed / total_active)) if total_active else 0
        out.append(
            {
                "date": day_s,
                "label": "今天" if d == today else d.strftime("%m/%d"),
                "weekday": "一二三四五六日"[d.weekday()],
                "completed": completed,
                "total": total_active,
                "percent": percent,
                "is_today": d == today,
            }
        )
    return out


def _remember_action(db: sqlite3.Connection, run_id: int, action_id: str, payload: dict) -> None:
    db.execute(
        """
        INSERT OR IGNORE INTO care_task_actions (run_id, action_id, result_json)
        VALUES (?, ?, ?)
        """,
        (run_id, action_id, json.dumps(payload, ensure_ascii=False)),
    )
    db.commit()


def _cached_action(db: sqlite3.Connection, run_id: int, action_id: str) -> dict | None:
    row = db.execute(
        "SELECT result_json FROM care_task_actions WHERE run_id = ? AND action_id = ?",
        (run_id, action_id),
    ).fetchone()
    if not row:
        return None
    try:
        return json.loads(row["result_json"])
    except json.JSONDecodeError:
        return None


def start_task(
    db: sqlite3.Connection,
    task_id: int,
    elder_user_id: int,
    *,
    action_id: str | None = None,
) -> dict:
    run = ensure_today_run(db, task_id, elder_user_id)
    if action_id:
        cached = _cached_action(db, run["id"], action_id)
        if cached:
            return cached

    if run["status"] == STATUS_COMPLETED:
        result = {"ok": True, "run": run, "message": "今日已完成"}
    else:
        run = _lock_snapshot_if_needed(db, run)
        status = STATUS_IN_PROGRESS
        db.execute(
            """
            UPDATE care_task_runs
            SET status = ?, paused_at = NULL, updated_at = ?
            WHERE id = ?
            """,
            (status, _now(), run["id"]),
        )
        db.commit()
        run = _hydrate_run(db, dict(_get_run_row(db, run["id"])))
        result = {"ok": True, "run": run, "message": "已开始"}

    if action_id:
        _remember_action(db, run["id"], action_id, result)
    return result


def pause_task(
    db: sqlite3.Connection,
    task_id: int,
    elder_user_id: int,
    *,
    action_id: str | None = None,
) -> dict:
    run = ensure_today_run(db, task_id, elder_user_id)
    if action_id:
        cached = _cached_action(db, run["id"], action_id)
        if cached:
            return cached

    if run["status"] == STATUS_COMPLETED:
        result = {"ok": True, "run": run, "message": "今日已完成，无需暂停"}
    elif run["status"] == STATUS_NOT_STARTED:
        result = {"ok": True, "run": run, "message": "尚未开始"}
    else:
        db.execute(
            """
            UPDATE care_task_runs
            SET status = ?, paused_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (STATUS_PAUSED, _now(), _now(), run["id"]),
        )
        db.commit()
        run = _hydrate_run(db, dict(_get_run_row(db, run["id"])))
        result = {"ok": True, "run": run, "message": "已暂停，稍后可继续"}

    if action_id:
        _remember_action(db, run["id"], action_id, result)
    return result


def resume_task(
    db: sqlite3.Connection,
    task_id: int,
    elder_user_id: int,
    *,
    action_id: str | None = None,
) -> dict:
    run = ensure_today_run(db, task_id, elder_user_id)
    if action_id:
        cached = _cached_action(db, run["id"], action_id)
        if cached:
            return cached

    if run["status"] == STATUS_COMPLETED:
        result = {"ok": True, "run": run, "message": "今日已完成"}
    else:
        run = _lock_snapshot_if_needed(db, run)
        db.execute(
            """
            UPDATE care_task_runs
            SET status = ?, paused_at = NULL, updated_at = ?
            WHERE id = ?
            """,
            (STATUS_IN_PROGRESS, _now(), run["id"]),
        )
        db.commit()
        run = _hydrate_run(db, dict(_get_run_row(db, run["id"])))
        result = {"ok": True, "run": run, "message": "已继续"}

    if action_id:
        _remember_action(db, run["id"], action_id, result)
    return result


def advance_current_step(
    db: sqlite3.Connection,
    task_id: int,
    elder_user_id: int,
    *,
    action: str,
    expected_step_index: int,
    action_id: str,
    user_id: int,
    is_family: bool = False,
) -> dict:
    """完成或跳过当前步。必须带 expected_step_index + action_id，防连点与跳步。"""
    if action not in {"done", "skip", "proxy"}:
        return {"ok": False, "error": "无效操作"}
    if action == "proxy" and not is_family:
        return {"ok": False, "error": "仅家属可代完成"}

    run = ensure_today_run(db, task_id, elder_user_id)
    cached = _cached_action(db, run["id"], action_id)
    if cached:
        return cached

    if run["status"] == STATUS_COMPLETED:
        result = {"ok": True, "run": run, "message": "今日已完成", "duplicate": False}
        _remember_action(db, run["id"], action_id, result)
        return result

    run = _lock_snapshot_if_needed(db, run)
    current = int(run["current_step_index"])
    total = int(run["total_steps"])

    if expected_step_index != current:
        result = {
            "ok": False,
            "error": "步骤已变化，请刷新后重试",
            "run": run,
            "conflict": True,
        }
        # 不缓存冲突，允许客户端用新 action_id 重试
        return result

    if current >= total:
        db.execute(
            """
            UPDATE care_task_runs
            SET status = ?, completed_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (STATUS_COMPLETED, _now(), _now(), run["id"]),
        )
        db.commit()
        run = _hydrate_run(db, dict(_get_run_row(db, run["id"])))
        result = {"ok": True, "run": run, "message": "已完成"}
        _remember_action(db, run["id"], action_id, result)
        return result

    step_status = {
        "done": STEP_DONE,
        "skip": STEP_SKIPPED,
        "proxy": STEP_PROXY,
    }[action]

    now = _now()
    db.execute(
        """
        INSERT INTO care_task_step_logs (run_id, step_index, status, completed_by, completed_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(run_id, step_index) DO UPDATE SET
            status = excluded.status,
            completed_by = excluded.completed_by,
            completed_at = excluded.completed_at
        """,
        (run["id"], current, step_status, user_id, now),
    )

    next_index = current + 1
    if next_index >= total:
        db.execute(
            """
            UPDATE care_task_runs
            SET current_step_index = ?, status = ?, completed_at = ?,
                paused_at = NULL, updated_at = ?
            WHERE id = ? AND current_step_index = ?
            """,
            (next_index, STATUS_COMPLETED, now, now, run["id"], current),
        )
    else:
        db.execute(
            """
            UPDATE care_task_runs
            SET current_step_index = ?, status = ?, paused_at = NULL, updated_at = ?
            WHERE id = ? AND current_step_index = ?
            """,
            (next_index, STATUS_IN_PROGRESS, now, run["id"], current),
        )

    if db.execute("SELECT changes()").fetchone()[0] == 0:
        # 并发下未更新成功
        run = _hydrate_run(db, dict(_get_run_row(db, run["id"])))
        return {"ok": False, "error": "进度已更新，请刷新", "run": run, "conflict": True}

    db.commit()
    run = _hydrate_run(db, dict(_get_run_row(db, run["id"])))
    result = {
        "ok": True,
        "run": run,
        "message": "整件任务已完成" if run["status"] == STATUS_COMPLETED else "已进入下一步",
        "duplicate": False,
    }
    _remember_action(db, run["id"], action_id, result)
    return result


def proxy_complete_all(
    db: sqlite3.Connection,
    task_id: int,
    elder_user_id: int,
    *,
    user_id: int,
    action_id: str,
) -> dict:
    run = ensure_today_run(db, task_id, elder_user_id)
    cached = _cached_action(db, run["id"], action_id)
    if cached:
        return cached

    run = _lock_snapshot_if_needed(db, run)
    now = _now()
    for i in range(run["total_steps"]):
        log = next((s for s in run["steps"] if s["index"] == i), None)
        if log and log["status"] in STEP_DONE_SET:
            continue
        db.execute(
            """
            INSERT INTO care_task_step_logs (run_id, step_index, status, completed_by, completed_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(run_id, step_index) DO UPDATE SET
                status = excluded.status,
                completed_by = excluded.completed_by,
                completed_at = excluded.completed_at
            """,
            (run["id"], i, STEP_PROXY, user_id, now),
        )
    db.execute(
        """
        UPDATE care_task_runs
        SET current_step_index = ?, status = ?, completed_at = ?,
            paused_at = NULL, updated_at = ?
        WHERE id = ?
        """,
        (run["total_steps"], STATUS_COMPLETED, now, now, run["id"]),
    )
    db.commit()
    run = _hydrate_run(db, dict(_get_run_row(db, run["id"])))
    result = {"ok": True, "run": run, "message": "家属已代完成整件任务"}
    _remember_action(db, run["id"], action_id, result)
    return result


def reset_today_run(
    db: sqlite3.Connection,
    task_id: int,
    elder_user_id: int,
    *,
    action_id: str,
) -> dict:
    run = ensure_today_run(db, task_id, elder_user_id)
    cached = _cached_action(db, run["id"], action_id)
    if cached:
        return cached

    db.execute("DELETE FROM care_task_step_logs WHERE run_id = ?", (run["id"],))
    db.execute("DELETE FROM care_task_actions WHERE run_id = ?", (run["id"],))
    db.execute(
        """
        UPDATE care_task_runs
        SET status = ?, current_step_index = 0, steps_snapshot = NULL,
            started_at = NULL, paused_at = NULL, completed_at = NULL, updated_at = ?
        WHERE id = ?
        """,
        (STATUS_NOT_STARTED, _now(), run["id"]),
    )
    db.commit()
    run = _hydrate_run(db, dict(_get_run_row(db, run["id"])))
    result = {"ok": True, "run": run, "message": "今日进度已重置"}
    # 重置后旧 action 已清空；新 action 写入
    _remember_action(db, run["id"], action_id, result)
    return result


def elder_focus_view(db: sqlite3.Connection, elder_user_id: int) -> dict:
    """老人端：今日任务列表 + 当前聚焦任务（优先进行中/暂停）。"""
    board = board_today(db, elder_user_id)
    focus = None
    for run in board["tasks"]:
        if run["status"] in {STATUS_IN_PROGRESS, STATUS_PAUSED}:
            focus = run
            break
    if focus is None:
        for run in board["tasks"]:
            if run["status"] == STATUS_NOT_STARTED:
                focus = run
                break
    return {"board": board, "focus": focus}
