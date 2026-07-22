"""用药中心 · 药物目录、计划、今日记录与 7 日分析"""

from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta

STATUS_TAKEN = "taken"
STATUS_PROXY = "proxy"
STATUS_SKIPPED = "skipped"
DONE_STATUSES = {STATUS_TAKEN, STATUS_PROXY}

STATUS_LABELS = {
    STATUS_TAKEN: "已服用",
    STATUS_PROXY: "家属代确认",
    STATUS_SKIPPED: "已跳过",
    "pending": "待处理",
}

PLACE_OPTIONS = [
    "客厅药盒",
    "卧室床头",
    "厨房药柜",
    "餐厅桌边",
    "冰箱冷藏",
    "随身小药盒",
    "其他",
]

# 药物目录清单（参考信息，非处方；须遵医嘱）
MEDICATION_CATALOG = [
    {
        "id": "donepezil",
        "name": "盐酸多奈哌齐",
        "dose": "5mg",
        "time": "21:00",
        "category": "认知改善",
        "effect": "改善记忆与注意力，延缓轻中度认知衰退",
        "description": "胆碱酯酶抑制剂，通过提高脑内乙酰胆碱水平帮助改善认知功能。常用于轻至中度阿尔茨海默病。初始多为每日 5mg，睡前服用，具体剂量由医生调整。",
        "tip": "固定时间服用；关注恶心、腹泻、失眠等反应。",
    },
    {
        "id": "memantine",
        "name": "盐酸美金刚",
        "dose": "10mg",
        "time": "08:00",
        "category": "认知改善",
        "effect": "调节谷氨酸兴奋性，改善中重度认知与日常功能",
        "description": "NMDA 受体拮抗剂，多用于中重度阿尔茨海默病，也可与多奈哌齐等联用。有助于改善定向、语言及部分精神行为症状。",
        "tip": "建议固定时间；头晕、便秘时及时告知医生。",
    },
    {
        "id": "rivastigmine",
        "name": "卡巴拉汀",
        "dose": "1.5mg",
        "time": "08:00",
        "category": "认知改善",
        "effect": "改善认知与日常生活能力",
        "description": "胆碱酯酶抑制剂，有口服与透皮贴剂等形式。常与餐同服，剂量需医生逐步滴定，以减轻胃肠道不适。",
        "tip": "餐后服用可减轻胃肠道不适。",
    },
    {
        "id": "galantamine",
        "name": "加兰他敏",
        "dose": "4mg",
        "time": "08:00",
        "category": "认知改善",
        "effect": "增强胆碱能传递，辅助改善认知",
        "description": "胆碱酯酶抑制剂，多日服 1–2 次。适用于轻中度患者，具体方案以医嘱为准。",
        "tip": "可设早晚两次计划；勿自行加量。",
    },
    {
        "id": "oxiracetam",
        "name": "奥拉西坦",
        "dose": "0.4g",
        "time": "12:00",
        "category": "辅助认知",
        "effect": "促智辅助，可能改善学习记忆相关功能",
        "description": "促智类药物，常作为辅助用药。疗效因人而异，需医生评估后使用，不可替代一线抗痴呆药物。",
        "tip": "按时服用；效果因人而异。",
    },
    {
        "id": "ginkgo",
        "name": "银杏叶提取物",
        "dose": "1 片",
        "time": "08:00",
        "category": "辅助循环",
        "effect": "改善微循环，辅助脑部供血相关不适",
        "description": "植物提取物制剂，部分患者用于改善脑供血相关症状。是否使用、剂量与疗程须遵医嘱或药师指导。",
        "tip": "如同时使用抗凝药，需提前告知医生。",
    },
    {
        "id": "vitamin_b",
        "name": "复合维生素 B",
        "dose": "1 片",
        "time": "08:00",
        "category": "营养支持",
        "effect": "补充 B 族维生素，支持神经与代谢",
        "description": "营养支持类补充剂，非特效抗痴呆药。可按营养师或医生建议补充，餐后服用更温和。",
        "tip": "餐后服用更温和。",
    },
    {
        "id": "vitamin_d",
        "name": "维生素 D",
        "dose": "1 粒",
        "time": "08:00",
        "category": "营养支持",
        "effect": "维持骨健康与免疫相关营养",
        "description": "常见营养补充剂。长者若有缺乏风险，可在医生指导下补充；剂量不可自行盲目加大。",
        "tip": "建议随餐服用以利吸收。",
    },
    {
        "id": "sleep_aid",
        "name": "助眠补充剂",
        "dose": "1 粒",
        "time": "21:30",
        "category": "睡眠支持",
        "effect": "辅助改善入睡与睡眠节律",
        "description": "非处方助眠类补充剂示例（如含褪黑素等成分的产品）。选购与剂量遵专业建议，勿与镇静催眠药随意叠加。",
        "tip": "睡前约 30 分钟；勿与镇静药随意叠加。",
    },
    {
        "id": "aspirin_low",
        "name": "阿司匹林肠溶片",
        "dose": "100mg",
        "time": "08:00",
        "category": "合并症常用",
        "effect": "抗血小板聚集（心脑血管二级预防等）",
        "description": "仅当医生因合并症开具时使用，并非阿尔茨海默病特效药。有出血倾向或溃疡史者需特别谨慎。",
        "tip": "餐后服用；出血倾向者需医生评估。",
    },
    {
        "id": "amlodipine",
        "name": "苯磺酸氨氯地平",
        "dose": "5mg",
        "time": "08:00",
        "category": "合并症常用",
        "effect": "控制血压，降低心脑血管风险",
        "description": "常见降压药示例。长者常合并高血压，须按心内科/全科医嘱服用，不可因「感觉良好」自行停药。",
        "tip": "每日固定时间；监测血压与脚踝水肿。",
    },
    {
        "id": "metformin",
        "name": "盐酸二甲双胍",
        "dose": "0.5g",
        "time": "08:00",
        "category": "合并症常用",
        "effect": "辅助控制血糖",
        "description": "2 型糖尿病常用药示例。与餐同服可减少胃肠道反应。低血糖与肾功能相关问题需医生监测。",
        "tip": "随餐服用；勿自行调整剂量。",
    },
]


def _migrate_columns(db: sqlite3.Connection, table: str, columns: dict[str, str]) -> None:
    existing = {row[1] for row in db.execute(f"PRAGMA table_info({table})").fetchall()}
    for name, decl in columns.items():
        if name not in existing:
            db.execute(f"ALTER TABLE {table} ADD COLUMN {name} {decl}")


def ensure_medication_tables(db: sqlite3.Connection) -> None:
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS medications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            elder_user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            dose TEXT NOT NULL,
            schedule_time TEXT NOT NULL,
            note TEXT NOT NULL DEFAULT '',
            alias TEXT NOT NULL DEFAULT '',
            place_area TEXT NOT NULL DEFAULT '',
            catalog_id TEXT,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_by INTEGER,
            created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (elder_user_id) REFERENCES users(id),
            FOREIGN KEY (created_by) REFERENCES users(id)
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS medication_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            medication_id INTEGER NOT NULL,
            elder_user_id INTEGER NOT NULL,
            taken_date TEXT NOT NULL,
            taken_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'taken',
            recorded_by INTEGER,
            UNIQUE(medication_id, taken_date),
            FOREIGN KEY (medication_id) REFERENCES medications(id),
            FOREIGN KEY (elder_user_id) REFERENCES users(id),
            FOREIGN KEY (recorded_by) REFERENCES users(id)
        )
        """
    )
    _migrate_columns(
        db,
        "medications",
        {
            "alias": "TEXT NOT NULL DEFAULT ''",
            "place_area": "TEXT NOT NULL DEFAULT ''",
        },
    )
    _migrate_columns(
        db,
        "medication_log",
        {
            "status": "TEXT NOT NULL DEFAULT 'taken'",
        },
    )
    db.commit()


def catalog_by_id(catalog_id: str) -> dict | None:
    return next((item for item in MEDICATION_CATALOG if item["id"] == catalog_id), None)


def all_catalog() -> list[dict]:
    return [dict(item) for item in MEDICATION_CATALOG]


def list_medications(db: sqlite3.Connection, elder_user_id: int, active_only: bool = True) -> list[dict]:
    sql = "SELECT * FROM medications WHERE elder_user_id = ?"
    params: list = [elder_user_id]
    if active_only:
        sql += " AND is_active = 1"
    sql += " ORDER BY schedule_time ASC, id ASC"
    return [dict(row) for row in db.execute(sql, params).fetchall()]


def add_medication(
    db: sqlite3.Connection,
    elder_user_id: int,
    *,
    name: str,
    dose: str,
    schedule_time: str,
    note: str = "",
    alias: str = "",
    place_area: str = "",
    catalog_id: str | None = None,
    created_by: int | None = None,
) -> int:
    cur = db.execute(
        """
        INSERT INTO medications
            (elder_user_id, name, dose, schedule_time, note, alias, place_area, catalog_id, created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            elder_user_id,
            name.strip(),
            dose.strip(),
            schedule_time.strip(),
            note.strip(),
            alias.strip(),
            place_area.strip(),
            catalog_id,
            created_by,
        ),
    )
    db.commit()
    return int(cur.lastrowid)


def add_from_catalog(
    db: sqlite3.Connection,
    elder_user_id: int,
    catalog_id: str,
    *,
    schedule_time: str | None = None,
    dose: str | None = None,
    alias: str = "",
    place_area: str = "",
    created_by: int | None = None,
) -> int | None:
    item = catalog_by_id(catalog_id)
    if not item:
        return None
    return add_medication(
        db,
        elder_user_id,
        name=item["name"],
        dose=dose or item["dose"],
        schedule_time=schedule_time or item["time"],
        note=item.get("description") or item.get("tip") or "",
        alias=alias,
        place_area=place_area,
        catalog_id=catalog_id,
        created_by=created_by,
    )


def update_medication(
    db: sqlite3.Connection,
    med_id: int,
    elder_user_id: int,
    *,
    dose: str,
    schedule_time: str,
    alias: str,
    place_area: str,
    note: str = "",
) -> bool:
    cur = db.execute(
        """
        UPDATE medications
        SET dose = ?, schedule_time = ?, alias = ?, place_area = ?, note = ?
        WHERE id = ? AND elder_user_id = ? AND is_active = 1
        """,
        (
            dose.strip(),
            schedule_time.strip(),
            alias.strip(),
            place_area.strip(),
            note.strip(),
            med_id,
            elder_user_id,
        ),
    )
    db.commit()
    return cur.rowcount > 0


def deactivate_medication(db: sqlite3.Connection, med_id: int, elder_user_id: int) -> bool:
    cur = db.execute(
        "UPDATE medications SET is_active = 0 WHERE id = ? AND elder_user_id = ?",
        (med_id, elder_user_id),
    )
    db.commit()
    return cur.rowcount > 0


def record_medication_status(
    db: sqlite3.Connection,
    med_id: int,
    elder_user_id: int,
    status: str,
    *,
    recorded_by: int | None = None,
    when: datetime | None = None,
) -> bool:
    if status not in {STATUS_TAKEN, STATUS_PROXY, STATUS_SKIPPED}:
        return False
    med = db.execute(
        "SELECT id FROM medications WHERE id = ? AND elder_user_id = ? AND is_active = 1",
        (med_id, elder_user_id),
    ).fetchone()
    if not med:
        return False
    now = when or datetime.now()
    db.execute(
        """
        INSERT INTO medication_log
            (medication_id, elder_user_id, taken_date, taken_at, status, recorded_by)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(medication_id, taken_date) DO UPDATE SET
            taken_at = excluded.taken_at,
            status = excluded.status,
            recorded_by = excluded.recorded_by
        """,
        (
            med_id,
            elder_user_id,
            now.strftime("%Y-%m-%d"),
            now.strftime("%H:%M"),
            status,
            recorded_by,
        ),
    )
    db.commit()
    return True


def mark_taken(
    db: sqlite3.Connection,
    med_id: int,
    elder_user_id: int,
    *,
    recorded_by: int | None = None,
    when: datetime | None = None,
) -> bool:
    return record_medication_status(
        db, med_id, elder_user_id, STATUS_TAKEN, recorded_by=recorded_by, when=when
    )


def display_name(med: dict) -> str:
    alias = (med.get("alias") or "").strip()
    name = med.get("name") or ""
    return f"{alias}（{name}）" if alias else name


def today_plan(db: sqlite3.Connection, elder_user_id: int, day: date | None = None) -> list[dict]:
    day = day or date.today()
    day_str = day.strftime("%Y-%m-%d")
    meds = list_medications(db, elder_user_id, active_only=True)
    logs = {
        row["medication_id"]: dict(row)
        for row in db.execute(
            """
            SELECT medication_id, taken_at, status, recorded_by
            FROM medication_log
            WHERE elder_user_id = ? AND taken_date = ?
            """,
            (elder_user_id, day_str),
        ).fetchall()
    }
    plan = []
    for med in meds:
        log = logs.get(med["id"])
        status = log["status"] if log else "pending"
        # 兼容旧数据：无 status 字段时视为 taken
        if log and not status:
            status = STATUS_TAKEN
        plan.append(
            {
                "id": med["id"],
                "name": med["name"],
                "alias": med.get("alias") or "",
                "display_name": display_name(med),
                "dose": med["dose"],
                "time": med["schedule_time"],
                "note": med["note"],
                "place_area": med.get("place_area") or "",
                "catalog_id": med.get("catalog_id"),
                "status": status,
                "status_label": STATUS_LABELS.get(status, status),
                "taken": status in DONE_STATUSES,
                "skipped": status == STATUS_SKIPPED,
                "pending": status == "pending",
                "taken_at": log["taken_at"] if log else "",
            }
        )
    return plan


def adherence_summary(db: sqlite3.Connection, elder_user_id: int, day: date | None = None) -> dict:
    plan = today_plan(db, elder_user_id, day)
    total = len(plan)
    done = sum(1 for item in plan if item["taken"])
    skipped = sum(1 for item in plan if item["skipped"])
    pending = sum(1 for item in plan if item["pending"])
    return {
        "total": total,
        "taken_count": done,
        "skipped_count": skipped,
        "pending_count": pending,
        "adherence": round(done / total * 100) if total else 0,
        "plan": plan,
    }


def week_schedule(db: sqlite3.Connection, elder_user_id: int) -> list[dict]:
    """近 7 日日程（含今日），用于家属日程表与分析。"""
    today = date.today()
    weekday_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    days = []
    for offset in range(6, -1, -1):
        day = today - timedelta(days=offset)
        summary = adherence_summary(db, elder_user_id, day)
        days.append(
            {
                "date": day.strftime("%Y-%m-%d"),
                "date_short": day.strftime("%m/%d"),
                "label": weekday_names[day.weekday()],
                "is_today": day == today,
                "total": summary["total"],
                "taken_count": summary["taken_count"],
                "skipped_count": summary["skipped_count"],
                "pending_count": summary["pending_count"],
                "adherence": summary["adherence"],
                "plan": summary["plan"],
            }
        )
    return days


def week_adherence(db: sqlite3.Connection, elder_user_id: int) -> list[dict]:
    schedule = week_schedule(db, elder_user_id)
    return [
        {
            "label": day["label"],
            "date_short": day["date_short"],
            "rate": day["adherence"],
            "taken_count": day["taken_count"],
            "skipped_count": day["skipped_count"],
            "pending_count": day["pending_count"],
            "total": day["total"],
            "is_today": day["is_today"],
            "future": False,
        }
        for day in schedule
    ]


def catalog_with_status(db: sqlite3.Connection, elder_user_id: int) -> list[dict]:
    active_ids = {
        row["catalog_id"]
        for row in db.execute(
            """
            SELECT catalog_id FROM medications
            WHERE elder_user_id = ? AND is_active = 1 AND catalog_id IS NOT NULL
            """,
            (elder_user_id,),
        ).fetchall()
        if row["catalog_id"]
    }
    items = []
    for item in MEDICATION_CATALOG:
        entry = dict(item)
        entry["already_added"] = item["id"] in active_ids
        items.append(entry)
    return items
