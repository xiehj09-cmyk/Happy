"""工作台助手 · DeepSeek 工具调用，读写真实用药与任务清单数据"""

from __future__ import annotations

import json
import uuid
import urllib.error
import urllib.request
from typing import Any

from config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL, DEEPSEEK_TIMEOUT
from med_ai_service import DISCLAIMER, deepseek_configured, process_smart_add
from medication_service import (
    PLACE_OPTIONS,
    STATUS_PROXY,
    STATUS_SKIPPED,
    STATUS_TAKEN,
    add_medication,
    adherence_summary,
    deactivate_medication,
    list_medications,
    record_medication_status,
    today_plan,
    update_medication,
    week_adherence,
    week_schedule,
)
from task_service import (
    advance_current_step,
    board_today,
    create_task,
    deactivate_task,
    get_task,
    list_tasks,
    pause_task,
    proxy_complete_all,
    reset_today_run,
    resume_task,
    start_task,
    update_task,
    week_overview,
)

ASSISTANT_SYSTEM = """你是「记忆港湾」工作台助手，协助家属/老人管理用药与任务清单（日程多步任务）。
你必须通过工具查询或修改真实数据库，禁止编造药单或任务内容。

【用药】
回答「今天哪些药还没吃 / 待服用」时，务必先调用 get_today_pending，再根据返回结果用中文简洁回答。
增删改药、代确认、跳过、标记已服也必须调用对应工具。

【任务清单 / 日程】
- 创建日程任务（如「准备午饭：洗手、拿碗、盛饭」）用 create_care_task，steps 必须按顺序数组传入。
- 修改任务名称或步骤用 update_care_task（需 task_id；可先 list_care_tasks 或 get_today_tasks）。
- 查询今日任务进度用 get_today_tasks；查任务模板用 list_care_tasks；本周完成情况用 get_tasks_week。
- 停用任务用 remove_care_task；家属代完成一步/整件/重置今日用对应工具。
- 仅家属可创建、修改、停用、代完成、重置任务；老人可查询进度，并可 start/pause/resume/advance 自己的任务。
- 若用户说「加一个任务」「创建清单」「改一下步骤」，必须调用工具，不要只口头答应。

回复使用简体中文，短句清晰；不要长篇免责声明（界面已有）。
若工具报错或权限不足，如实告知用户。
"""

MED_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_today_plan",
            "description": "查询今日完整用药计划与状态（已服用/代确认/跳过/待处理）",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_today_pending",
            "description": "查询今天尚未服用（待处理）的药物列表，回答「今天哪些药还没吃」时必须使用",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_medications",
            "description": "列出当前生效的每日用药计划（药名、剂量、时间、别名、放置区）",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_week_summary",
            "description": "查询近 7 日用药依从与日程摘要",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_medication",
            "description": "新增一条用药计划到老人药单",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "药名"},
                    "dose": {"type": "string", "description": "剂量"},
                    "schedule_time": {"type": "string", "description": "HH:MM"},
                    "alias": {"type": "string"},
                    "place_area": {"type": "string"},
                    "note": {"type": "string"},
                },
                "required": ["name", "dose", "schedule_time"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_medication",
            "description": "更新已有用药计划（剂量、时间、别名、放置区、备注）",
            "parameters": {
                "type": "object",
                "properties": {
                    "med_id": {"type": "integer"},
                    "dose": {"type": "string"},
                    "schedule_time": {"type": "string"},
                    "alias": {"type": "string"},
                    "place_area": {"type": "string"},
                    "note": {"type": "string"},
                },
                "required": ["med_id", "dose", "schedule_time"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "remove_medication",
            "description": "从每日计划中移除（停用）某药物",
            "parameters": {
                "type": "object",
                "properties": {"med_id": {"type": "integer"}},
                "required": ["med_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "record_status",
            "description": "记录今日服药状态：taken=已服，proxy=家属代确认，skipped=跳过",
            "parameters": {
                "type": "object",
                "properties": {
                    "med_id": {"type": "integer"},
                    "status": {"type": "string", "enum": ["taken", "proxy", "skipped"]},
                },
                "required": ["med_id", "status"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "smart_add_drug",
            "description": "用自然语言智能加药：联网检索说明书后整理并写入药单（如「加入布洛芬」）",
            "parameters": {
                "type": "object",
                "properties": {"message": {"type": "string"}},
                "required": ["message"],
                "additionalProperties": False,
            },
        },
    },
]

TASK_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_care_tasks",
            "description": "列出当前生效的任务清单模板（含 task_id、标题、建议时间、有序步骤）",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_today_tasks",
            "description": "查询今日任务看板：每件事进度、当前做到第几步、是否完成",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_tasks_week",
            "description": "查询近 7 日任务完成概况",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_care_task",
            "description": "创建一条多步日程任务。例如标题「准备午饭」，steps 为 [\"洗手\",\"拿碗\",\"盛饭\"]",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "任务名称"},
                    "steps": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "按顺序的步骤文案列表，至少 1 步",
                    },
                    "schedule_time": {"type": "string", "description": "可选，HH:MM"},
                    "note": {"type": "string"},
                },
                "required": ["title", "steps"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_care_task",
            "description": "修改任务模板的标题/步骤/时间/备注。今天已开始做的那次仍按开始时快照继续",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "integer"},
                    "title": {"type": "string"},
                    "steps": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "完整有序步骤列表（会整体替换）",
                    },
                    "schedule_time": {"type": "string"},
                    "note": {"type": "string"},
                },
                "required": ["task_id", "title", "steps"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "remove_care_task",
            "description": "停用（删除）一条任务清单",
            "parameters": {
                "type": "object",
                "properties": {"task_id": {"type": "integer"}},
                "required": ["task_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "proxy_task_step",
            "description": "家属代完成任务的当前一步",
            "parameters": {
                "type": "object",
                "properties": {"task_id": {"type": "integer"}},
                "required": ["task_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "complete_care_task_today",
            "description": "家属代完成整件今日任务",
            "parameters": {
                "type": "object",
                "properties": {"task_id": {"type": "integer"}},
                "required": ["task_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "reset_care_task_today",
            "description": "重置某任务今日进度",
            "parameters": {
                "type": "object",
                "properties": {"task_id": {"type": "integer"}},
                "required": ["task_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "start_care_task",
            "description": "开始今日某任务（锁定步骤快照）",
            "parameters": {
                "type": "object",
                "properties": {"task_id": {"type": "integer"}},
                "required": ["task_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "pause_care_task",
            "description": "暂停今日某任务（先不做了）",
            "parameters": {
                "type": "object",
                "properties": {"task_id": {"type": "integer"}},
                "required": ["task_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "resume_care_task",
            "description": "继续今日某任务（停在离开的那一步）",
            "parameters": {
                "type": "object",
                "properties": {"task_id": {"type": "integer"}},
                "required": ["task_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "advance_care_task",
            "description": "推进当前步骤：done=做好了，skip=跳过本步",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "integer"},
                    "action": {"type": "string", "enum": ["done", "skip"]},
                },
                "required": ["task_id", "action"],
                "additionalProperties": False,
            },
        },
    },
]

TOOLS = MED_TOOLS + TASK_TOOLS


def call_deepseek_chat(
    messages: list[dict],
    *,
    tools: list[dict] | None = None,
    json_mode: bool = False,
    temperature: float = 0.2,
    max_tokens: int = 1600,
) -> dict[str, Any]:
    if not DEEPSEEK_API_KEY:
        raise RuntimeError("未配置 DEEPSEEK_API_KEY")

    payload: dict[str, Any] = {
        "model": DEEPSEEK_MODEL or "deepseek-v4-flash",
        "messages": messages,
        "thinking": {"type": "disabled"},
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if tools:
        payload["tools"] = tools
    if json_mode:
        payload["response_format"] = {"type": "json_object"}

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
        with urllib.request.urlopen(req, timeout=DEEPSEEK_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"DeepSeek API 错误 {exc.code}: {detail[:400]}") from exc

    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError("DeepSeek 无返回内容")
    return choices[0].get("message") or {}


def _tool_message_for_history(message: dict) -> dict:
    out: dict[str, Any] = {
        "role": "assistant",
        "content": message.get("content") or "",
    }
    if message.get("tool_calls"):
        out["tool_calls"] = message["tool_calls"]
    if message.get("reasoning_content"):
        out["reasoning_content"] = message["reasoning_content"]
    return out


def _new_action_id() -> str:
    return str(uuid.uuid4())


def _slim_run(run: dict) -> dict:
    return {
        "task_id": run.get("task_id"),
        "title": run.get("title"),
        "status": run.get("status"),
        "status_label": run.get("status_label"),
        "schedule_time": run.get("schedule_time") or "",
        "current_step_index": run.get("current_step_index"),
        "current_step": run.get("current_step"),
        "done_count": run.get("done_count"),
        "total_steps": run.get("total_steps"),
        "progress_percent": run.get("progress_percent"),
        "steps": [
            {
                "index": s["index"],
                "content": s["content"],
                "status": s["status"],
                "status_label": s["status_label"],
                "is_current": s["is_current"],
            }
            for s in (run.get("steps") or [])
        ],
    }


def execute_assistant_tool(
    db,
    name: str,
    arguments: dict,
    *,
    elder_user_id: int,
    user_id: int,
    role: str,
    elder_username: str = "",
) -> dict[str, Any]:
    is_family = role == "family"

    if name == "get_today_plan":
        return {"ok": True, "summary": adherence_summary(db, elder_user_id)}

    if name == "get_today_pending":
        plan = today_plan(db, elder_user_id)
        pending = [p for p in plan if p.get("pending")]
        return {
            "ok": True,
            "pending_count": len(pending),
            "total": len(plan),
            "pending": [
                {
                    "id": p["id"],
                    "display_name": p["display_name"],
                    "name": p["name"],
                    "alias": p.get("alias") or "",
                    "time": p["time"],
                    "dose": p["dose"],
                    "place_area": p.get("place_area") or "",
                    "status": p["status"],
                }
                for p in pending
            ],
        }

    if name == "list_medications":
        meds = [dict(m) for m in list_medications(db, elder_user_id, active_only=True)]
        return {
            "ok": True,
            "medications": [
                {
                    "id": m["id"],
                    "name": m["name"],
                    "alias": m.get("alias") or "",
                    "dose": m["dose"],
                    "schedule_time": m["schedule_time"],
                    "place_area": m.get("place_area") or "",
                    "note": m.get("note") or "",
                }
                for m in meds
            ],
        }

    if name == "get_week_summary":
        return {
            "ok": True,
            "week_log": week_adherence(db, elder_user_id),
            "week_days": [
                {
                    "date": d["date"],
                    "label": d["label"],
                    "adherence": d["adherence"],
                    "taken_count": d["taken_count"],
                    "skipped_count": d["skipped_count"],
                    "pending_count": d["pending_count"],
                    "total": d["total"],
                    "is_today": d["is_today"],
                }
                for d in week_schedule(db, elder_user_id)
            ],
        }

    if name == "add_medication":
        if not is_family:
            return {"ok": False, "error": "仅家属可新增用药计划"}
        med_name = str(arguments.get("name") or "").strip()
        dose = str(arguments.get("dose") or "").strip()
        schedule_time = str(arguments.get("schedule_time") or "").strip()
        if not med_name or not dose or not schedule_time:
            return {"ok": False, "error": "name/dose/schedule_time 必填"}
        place = str(arguments.get("place_area") or "").strip()
        if place and place not in PLACE_OPTIONS:
            place = ""
        med_id = add_medication(
            db,
            elder_user_id,
            name=med_name,
            dose=dose,
            schedule_time=schedule_time,
            note=str(arguments.get("note") or "").strip(),
            alias=str(arguments.get("alias") or "").strip(),
            place_area=place,
            created_by=user_id,
        )
        return {"ok": True, "medication_id": med_id}

    if name == "update_medication":
        if not is_family:
            return {"ok": False, "error": "仅家属可修改用药计划"}
        try:
            med_id = int(arguments.get("med_id"))
        except (TypeError, ValueError):
            return {"ok": False, "error": "med_id 无效"}
        dose = str(arguments.get("dose") or "").strip()
        schedule_time = str(arguments.get("schedule_time") or "").strip()
        if not dose or not schedule_time:
            return {"ok": False, "error": "dose/schedule_time 必填"}
        place = str(arguments.get("place_area") or "").strip()
        if place and place not in PLACE_OPTIONS:
            place = ""
        ok = update_medication(
            db,
            med_id,
            elder_user_id,
            dose=dose,
            schedule_time=schedule_time,
            alias=str(arguments.get("alias") or "").strip(),
            place_area=place,
            note=str(arguments.get("note") or "").strip(),
        )
        return {"ok": ok, "error": None if ok else "更新失败，请确认 med_id"}

    if name == "remove_medication":
        if not is_family:
            return {"ok": False, "error": "仅家属可移除用药计划"}
        try:
            med_id = int(arguments.get("med_id"))
        except (TypeError, ValueError):
            return {"ok": False, "error": "med_id 无效"}
        ok = deactivate_medication(db, med_id, elder_user_id)
        return {"ok": ok, "error": None if ok else "移除失败"}

    if name == "record_status":
        status = str(arguments.get("status") or "").strip()
        try:
            med_id = int(arguments.get("med_id"))
        except (TypeError, ValueError):
            return {"ok": False, "error": "med_id 无效"}
        if status == STATUS_PROXY and not is_family:
            return {"ok": False, "error": "仅家属可代确认"}
        if status == STATUS_SKIPPED and not is_family:
            return {"ok": False, "error": "仅家属可标记跳过"}
        if status not in {STATUS_TAKEN, STATUS_PROXY, STATUS_SKIPPED}:
            return {"ok": False, "error": "status 须为 taken/proxy/skipped"}
        ok = record_medication_status(
            db, med_id, elder_user_id, status, recorded_by=user_id
        )
        return {"ok": ok, "status": status, "error": None if ok else "记录失败"}

    if name == "smart_add_drug":
        if not is_family:
            return {"ok": False, "error": "仅家属可使用智能加药"}
        message = str(arguments.get("message") or "").strip()
        if not message:
            return {"ok": False, "error": "message 不能为空"}
        return process_smart_add(
            db,
            elder_user_id=elder_user_id,
            family_user_id=user_id,
            message=message,
            elder_username=elder_username,
        )

    if name == "list_care_tasks":
        tasks = list_tasks(db, elder_user_id, active_only=True)
        return {
            "ok": True,
            "tasks": [
                {
                    "task_id": t["id"],
                    "title": t["title"],
                    "note": t.get("note") or "",
                    "schedule_time": t.get("schedule_time") or "",
                    "steps": [s["content"] for s in t.get("steps") or []],
                    "step_count": t.get("step_count") or 0,
                }
                for t in tasks
            ],
        }

    if name == "get_today_tasks":
        board = board_today(db, elder_user_id)
        return {
            "ok": True,
            "date": board["date"],
            "total": board["total"],
            "completed_count": board["completed_count"],
            "in_progress_count": board["in_progress_count"],
            "pending_count": board["pending_count"],
            "overall_percent": board["overall_percent"],
            "tasks": [_slim_run(r) for r in board["tasks"]],
        }

    if name == "get_tasks_week":
        return {"ok": True, "week": week_overview(db, elder_user_id)}

    if name == "create_care_task":
        if not is_family:
            return {"ok": False, "error": "仅家属可创建任务清单"}
        title = str(arguments.get("title") or "").strip()
        raw_steps = arguments.get("steps") or []
        if not isinstance(raw_steps, list):
            return {"ok": False, "error": "steps 须为字符串数组"}
        steps = [str(s).strip() for s in raw_steps if str(s).strip()]
        try:
            task_id = create_task(
                db,
                elder_user_id,
                title=title,
                steps=steps,
                note=str(arguments.get("note") or "").strip(),
                schedule_time=str(arguments.get("schedule_time") or "").strip(),
                created_by=user_id,
            )
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}
        task = get_task(db, task_id, elder_user_id)
        return {
            "ok": True,
            "task_id": task_id,
            "title": task["title"] if task else title,
            "steps": [s["content"] for s in (task["steps"] if task else [])],
            "schedule_time": (task or {}).get("schedule_time") or "",
        }

    if name == "update_care_task":
        if not is_family:
            return {"ok": False, "error": "仅家属可修改任务清单"}
        try:
            task_id = int(arguments.get("task_id"))
        except (TypeError, ValueError):
            return {"ok": False, "error": "task_id 无效"}
        title = str(arguments.get("title") or "").strip()
        raw_steps = arguments.get("steps") or []
        if not isinstance(raw_steps, list):
            return {"ok": False, "error": "steps 须为字符串数组"}
        steps = [str(s).strip() for s in raw_steps if str(s).strip()]
        try:
            ok = update_task(
                db,
                task_id,
                elder_user_id,
                title=title,
                steps=steps,
                note=str(arguments.get("note") or "").strip(),
                schedule_time=str(arguments.get("schedule_time") or "").strip(),
            )
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}
        if not ok:
            return {"ok": False, "error": "更新失败，请确认 task_id"}
        task = get_task(db, task_id, elder_user_id)
        return {
            "ok": True,
            "task_id": task_id,
            "title": task["title"] if task else title,
            "steps": [s["content"] for s in (task["steps"] if task else [])],
            "note": "模板已更新；若今天已开始，今日进度仍按开始时的步骤继续",
        }

    if name == "remove_care_task":
        if not is_family:
            return {"ok": False, "error": "仅家属可停用任务"}
        try:
            task_id = int(arguments.get("task_id"))
        except (TypeError, ValueError):
            return {"ok": False, "error": "task_id 无效"}
        ok = deactivate_task(db, task_id, elder_user_id)
        return {"ok": ok, "error": None if ok else "停用失败"}

    if name == "proxy_task_step":
        if not is_family:
            return {"ok": False, "error": "仅家属可代完成步骤"}
        try:
            task_id = int(arguments.get("task_id"))
        except (TypeError, ValueError):
            return {"ok": False, "error": "task_id 无效"}
        board = board_today(db, elder_user_id)
        run = next((r for r in board["tasks"] if r["task_id"] == task_id), None)
        if not run:
            return {"ok": False, "error": "未找到该任务"}
        if run["status"] == "completed":
            return {"ok": True, "run": _slim_run(run), "message": "今日已完成"}
        expected = int(run["current_step_index"])
        result = advance_current_step(
            db,
            task_id,
            elder_user_id,
            action="proxy",
            expected_step_index=expected,
            action_id=_new_action_id(),
            user_id=user_id,
            is_family=True,
        )
        if result.get("run"):
            result["run"] = _slim_run(result["run"])
        return result

    if name == "complete_care_task_today":
        if not is_family:
            return {"ok": False, "error": "仅家属可代完成整件"}
        try:
            task_id = int(arguments.get("task_id"))
        except (TypeError, ValueError):
            return {"ok": False, "error": "task_id 无效"}
        result = proxy_complete_all(
            db, task_id, elder_user_id, user_id=user_id, action_id=_new_action_id()
        )
        if result.get("run"):
            result["run"] = _slim_run(result["run"])
        return result

    if name == "reset_care_task_today":
        if not is_family:
            return {"ok": False, "error": "仅家属可重置今日进度"}
        try:
            task_id = int(arguments.get("task_id"))
        except (TypeError, ValueError):
            return {"ok": False, "error": "task_id 无效"}
        result = reset_today_run(db, task_id, elder_user_id, action_id=_new_action_id())
        if result.get("run"):
            result["run"] = _slim_run(result["run"])
        return result

    if name == "start_care_task":
        try:
            task_id = int(arguments.get("task_id"))
        except (TypeError, ValueError):
            return {"ok": False, "error": "task_id 无效"}
        result = start_task(db, task_id, elder_user_id, action_id=_new_action_id())
        if result.get("run"):
            result["run"] = _slim_run(result["run"])
        return result

    if name == "pause_care_task":
        try:
            task_id = int(arguments.get("task_id"))
        except (TypeError, ValueError):
            return {"ok": False, "error": "task_id 无效"}
        result = pause_task(db, task_id, elder_user_id, action_id=_new_action_id())
        if result.get("run"):
            result["run"] = _slim_run(result["run"])
        return result

    if name == "resume_care_task":
        try:
            task_id = int(arguments.get("task_id"))
        except (TypeError, ValueError):
            return {"ok": False, "error": "task_id 无效"}
        result = resume_task(db, task_id, elder_user_id, action_id=_new_action_id())
        if result.get("run"):
            result["run"] = _slim_run(result["run"])
        return result

    if name == "advance_care_task":
        try:
            task_id = int(arguments.get("task_id"))
        except (TypeError, ValueError):
            return {"ok": False, "error": "task_id 无效"}
        action = str(arguments.get("action") or "").strip()
        if action not in {"done", "skip"}:
            return {"ok": False, "error": "action 须为 done 或 skip"}
        board = board_today(db, elder_user_id)
        run = next((r for r in board["tasks"] if r["task_id"] == task_id), None)
        if not run:
            return {"ok": False, "error": "未找到该任务"}
        expected = int(run["current_step_index"])
        result = advance_current_step(
            db,
            task_id,
            elder_user_id,
            action=action,
            expected_step_index=expected,
            action_id=_new_action_id(),
            user_id=user_id,
            is_family=is_family,
        )
        if result.get("run"):
            result["run"] = _slim_run(result["run"])
        return result

    return {"ok": False, "error": f"未知工具: {name}"}


execute_med_tool = execute_assistant_tool


def run_assistant_chat(
    db,
    *,
    message: str,
    elder_user_id: int,
    user_id: int,
    role: str,
    elder_username: str = "",
    history: list[dict] | None = None,
) -> dict[str, Any]:
    message = (message or "").strip()
    if not message:
        return {
            "ok": False,
            "reply": "请输入问题，例如：今天哪些药还没有吃？或：创建一个准备午饭的任务。",
            "disclaimer": DISCLAIMER,
        }
    if not deepseek_configured():
        return {
            "ok": False,
            "reply": "工作台助手未配置 DeepSeek API Key。",
            "disclaimer": DISCLAIMER,
        }

    messages: list[dict] = [{"role": "system", "content": ASSISTANT_SYSTEM}]
    for item in (history or [])[-8:]:
        role_name = item.get("role")
        content = (item.get("content") or "").strip()
        if role_name in {"user", "assistant"} and content:
            messages.append({"role": role_name, "content": content})
    messages.append(
        {
            "role": "user",
            "content": (
                f"当前身份：{'家属' if role == 'family' else '老人'}；"
                f"照护对象：{elder_username or '老人'}。\n"
                f"用户问题：{message}"
            ),
        }
    )

    tool_trace: list[dict] = []
    final_text = ""
    for _ in range(8):
        msg = call_deepseek_chat(messages, tools=TOOLS, json_mode=False)
        tool_calls = msg.get("tool_calls") or []
        if not tool_calls:
            final_text = (msg.get("content") or "").strip()
            break

        messages.append(_tool_message_for_history(msg))
        for call in tool_calls:
            fn = call.get("function") or {}
            name = fn.get("name") or ""
            raw_args = fn.get("arguments") or "{}"
            try:
                args = json.loads(raw_args) if isinstance(raw_args, str) else (raw_args or {})
            except json.JSONDecodeError:
                args = {}
            result = execute_assistant_tool(
                db,
                name,
                args if isinstance(args, dict) else {},
                elder_user_id=elder_user_id,
                user_id=user_id,
                role=role,
                elder_username=elder_username,
            )
            tool_trace.append({"name": name, "arguments": args, "result": result})
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.get("id") or name,
                    "content": json.dumps(result, ensure_ascii=False),
                }
            )
    else:
        final_text = "处理步骤过多，请换一种说法再问一次。"

    if not final_text:
        final_text = "我已查询相关数据，但没有生成文字回复。请再问一次。"

    return {
        "ok": True,
        "reply": final_text,
        "tool_trace": tool_trace,
        "disclaimer": DISCLAIMER,
    }
