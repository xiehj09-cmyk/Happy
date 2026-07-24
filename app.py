"""阿尔茨海默症关怀平台 · CST 居家疗程 + 硬件 AI"""

from __future__ import annotations

import os
import re
import sqlite3
from datetime import datetime
from functools import wraps
from pathlib import Path

from flask import (
    Flask,
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash, generate_password_hash

from cst_ai import build_session_system_prompt, get_opening_line, pick_facilitator_reply
from cst_data import get_session, reality_orientation_context
from cst_practice_service import (
    deactivate_material,
    ensure_practice_tables,
    generate_practice_questions,
    get_active_run,
    get_material,
    list_materials,
    material_abs_path,
    render_card_speak_text,
    expand_practice_reply,
    save_answer,
    save_material,
)
from cst_service import (
    build_cst_overview,
    ensure_cst_tables,
    get_all_logs,
    get_cst_profile,
    get_device,
    get_session_log,
)

from assistant_service import run_assistant_chat
from baidu_speech_service import (
    baidu_speech_configured,
    evaluate_soft_answer,
    public_speech_config,
    recognize_speech,
    synthesize_speech,
)
from config import (
    BASE_DIR,
    DATA_DIR,
    DEBUG,
    HOST,
    MCP_API_TOKEN,
    MCP_ELDER_USER_ID,
    MCP_ELDER_USERNAME,
    PORT,
    SECRET_KEY,
    THREADS,
    XIAOZHI_AGENT_ID,
    XIAOZHI_USER_ID,
)
from companion_service import run_companion_chat
from med_ai_service import deepseek_configured, process_smart_add
from mcp_user_service import (
    bind_xiaozhi_user,
    ensure_env_forced_xiaozhi_bind,
    ensure_mcp_user_schema,
    ensure_user_mcp_token,
    list_xiaozhi_links_for_elder,
    parse_xiaozhi_endpoint_token,
    resolve_configured_elder_id,
    resolve_mcp_identity,
    rotate_user_mcp_token,
    unbind_xiaozhi_user,
)
from voice_matter_service import (
    add_matter,
    complete_matter,
    delete_matter,
    ensure_voice_matter_tables,
    list_due_reminders,
    list_matters,
    mark_matter_reminded,
    parse_relative_delay_seconds,
    reopen_matter,
    speak_matters_summary,
    wake_prompt_for_matter,
)
from medication_service import (
    PLACE_OPTIONS,
    STATUS_PROXY,
    STATUS_SKIPPED,
    STATUS_TAKEN,
    add_from_catalog,
    add_medication,
    adherence_summary,
    catalog_by_id,
    catalog_with_status,
    deactivate_medication,
    ensure_medication_tables,
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
    ensure_task_tables,
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
from user_auth import (
    ROLE_ELDER,
    ROLE_FAMILY,
    ROLE_LABELS,
    VALID_ROLES,
    create_family_link,
    elder_local_email,
    ensure_user_auth_schema,
    get_linked_elder,
)

BASE_DIR = Path(__file__).resolve().parent
# 账号与业务数据：Zeabur 请挂载 /data（或设置 DATA_DIR）
DB_PATH = DATA_DIR / "users.db"


def _migrate_legacy_instance_db() -> None:
    """若新数据目录尚无库、旧 instance 有库，则复制过去（一次性）。"""
    legacy = BASE_DIR / "instance" / "users.db"
    if DB_PATH.exists() or not legacy.exists():
        return
    if DB_PATH.resolve() == legacy.resolve():
        return
    try:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        import shutil

        shutil.copy2(legacy, DB_PATH)
    except OSError:
        pass


_migrate_legacy_instance_db()

app = Flask(__name__)
app.secret_key = SECRET_KEY
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["MAX_CONTENT_LENGTH"] = 6 * 1024 * 1024
# 仅在反向代理（如 Zeabur）后启用；局域网直连时不要改写 Host，否则易 500
_TRUST_PROXY = os.environ.get("TRUST_PROXY", "").strip().lower() in {"1", "true", "yes", "on"}
_IS_ZEABUR = bool(os.environ.get("ZEABUR") or os.environ.get("ZEABUR_ENVIRONMENT"))
if _TRUST_PROXY or _IS_ZEABUR:
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
    app.config["SESSION_COOKIE_SECURE"] = True
    app.config["PREFERRED_URL_SCHEME"] = "https"

USERNAME_RE = re.compile(r"^[A-Za-z0-9_\u4e00-\u9fff]{2,32}$")
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        g.db = conn
    return g.db


@app.teardown_appcontext
def close_db(_exc: BaseException | None = None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db() -> None:
    db = get_db()
    ensure_user_auth_schema(db)
    try:
        ensure_mcp_user_schema(db)
    except Exception as exc:  # noqa: BLE001
        app.logger.exception("ensure_mcp_user_schema failed: %s", exc)
    ensure_cst_tables(db)
    ensure_practice_tables(db)
    ensure_medication_tables(db)
    ensure_task_tables(db)
    ensure_voice_matter_tables(db)
    # 单用户强制绑定：环境变量小智 ↔ MCP_ELDER_USERNAME（如 15）
    if MCP_ELDER_USERNAME or MCP_ELDER_USER_ID:
        if XIAOZHI_USER_ID:
            result = ensure_env_forced_xiaozhi_bind(
                db,
                elder_username=MCP_ELDER_USERNAME,
                elder_user_id=MCP_ELDER_USER_ID,
                xiaozhi_user_id=XIAOZHI_USER_ID,
                xiaozhi_agent_id=XIAOZHI_AGENT_ID,
            )
            if result.get("ok"):
                app.logger.info(
                    "forced Xiaozhi bind: userId=%s agentId=%s -> @%s (elder_id=%s)",
                    result.get("xiaozhi_user_id"),
                    result.get("xiaozhi_agent_id") or "-",
                    result.get("username"),
                    result.get("elder_user_id"),
                )
            else:
                app.logger.warning(
                    "forced Xiaozhi bind skipped: %s",
                    result.get("message") or result.get("error"),
                )
        else:
            app.logger.warning(
                "MCP_ELDER_USERNAME=%s set but XIAOZHI_USER_ID empty "
                "(set XIAOZHI_MCP_ENDPOINT or XIAOZHI_USER_ID)",
                MCP_ELDER_USERNAME or MCP_ELDER_USER_ID,
            )


def env_force_bind_active() -> bool:
    """是否启用「环境变量单用户强制绑定」。"""
    return bool((MCP_ELDER_USERNAME or MCP_ELDER_USER_ID) and XIAOZHI_USER_ID)


def xiaozhi_bind_template_vars() -> dict:
    """工作台小智绑定区块所需变量。"""
    return {
        "env_force_bind": env_force_bind_active(),
        "env_force_xiaozhi_user_id": XIAOZHI_USER_ID or "",
        "env_force_xiaozhi_agent_id": XIAOZHI_AGENT_ID or "",
        "env_force_elder_username": MCP_ELDER_USERNAME or (
            str(MCP_ELDER_USER_ID) if MCP_ELDER_USER_ID else ""
        ),
    }


@app.errorhandler(500)
def handle_500(err):
    app.logger.exception("Internal Server Error: %s", err)
    return (
        "<h1>服务暂时出错</h1><p>请稍后刷新。若在局域网访问，请确认使用服务器 IP 与端口，"
        "并已重启最新代码。</p>",
        500,
        {"Content-Type": "text/html; charset=utf-8"},
    )


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        wants_json = request.path.startswith("/api/") or request.accept_mimetypes.best == "application/json"

        def _deny(message: str, code: int = 401):
            if wants_json:
                return jsonify({"ok": False, "error": message, "reply": message}), code
            flash(message, "warning")
            return redirect(url_for("login", next=request.path))

        if not session.get("user_id"):
            return _deny("请先登录后再访问。")
        # Zeabur 重部署后库可能被清空，旧 Cookie 会导致后续页面 500
        user = load_current_user()
        if user is None:
            session.clear()
            return _deny("登录已失效（账号数据已更新），请重新登录或注册。")
        if session.get("role") == ROLE_FAMILY:
            elder_id = session.get("elder_user_id")
            if not elder_id or not _user_exists(int(elder_id)):
                session.clear()
                return _deny("绑定的老人账号不存在，请重新用家属账号登录。")
        return view(*args, **kwargs)

    return wrapped


def _user_exists(user_id: int) -> bool:
    row = get_db().execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
    return row is not None


def _extract_mcp_bearer() -> str:
    auth = request.headers.get("Authorization") or ""
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return (request.headers.get("X-MCP-Token") or "").strip()


def mcp_token_required(view):
    """MCP 鉴权：个人 mcp_token，或全局 Token + 已手动绑定的小智 UserId。"""

    @wraps(view)
    def wrapped(*args, **kwargs):
        db = get_db()
        token = _extract_mcp_bearer()
        if not token:
            return jsonify({"ok": False, "error": "缺少 MCP Token"}), 401
        xiaozhi_user_id = (
            request.headers.get("X-Xiaozhi-User-Id")
            or request.args.get("xiaozhi_user_id")
            or ""
        ).strip()
        xiaozhi_agent_id = (
            request.headers.get("X-Xiaozhi-Agent-Id")
            or request.args.get("xiaozhi_agent_id")
            or ""
        ).strip()
        if request.method in ("POST", "PUT", "PATCH"):
            body = request.get_json(silent=True)
            if isinstance(body, dict):
                xiaozhi_user_id = xiaozhi_user_id or str(body.get("xiaozhi_user_id") or "").strip()
                xiaozhi_agent_id = xiaozhi_agent_id or str(body.get("xiaozhi_agent_id") or "").strip()
        # 单用户模式：请求未带小智 Id 时，用环境变量强制身份
        xiaozhi_user_id = xiaozhi_user_id or XIAOZHI_USER_ID
        xiaozhi_agent_id = xiaozhi_agent_id or XIAOZHI_AGENT_ID

        fallback_elder_id = resolve_configured_elder_id(
            db,
            username=MCP_ELDER_USERNAME,
            user_id=MCP_ELDER_USER_ID,
        )
        identity = resolve_mcp_identity(
            db,
            token,
            global_token=MCP_API_TOKEN,
            xiaozhi_user_id=xiaozhi_user_id or None,
            xiaozhi_agent_id=xiaozhi_agent_id or None,
            fallback_elder_id=fallback_elder_id,
            allow_auto_provision=False,
        )
        if not identity:
            return jsonify({"ok": False, "error": "MCP Token 无效或无法识别用户"}), 401
        if identity.get("error"):
            return (
                jsonify(
                    {
                        "ok": False,
                        "error": identity.get("message") or identity["error"],
                        "need_bind": identity.get("error") == "need_bind",
                        "xiaozhi_user_id": identity.get("xiaozhi_user_id"),
                    }
                ),
                403,
            )
        g.mcp_elder_id = int(identity["elder_user_id"])
        g.mcp_identity = identity
        return view(*args, **kwargs)

    return wrapped


def resolve_mcp_elder_id(db: sqlite3.Connection) -> int | None:
    elder_id = getattr(g, "mcp_elder_id", None)
    if elder_id:
        return int(elder_id)
    configured = resolve_configured_elder_id(
        db,
        username=MCP_ELDER_USERNAME,
        user_id=MCP_ELDER_USER_ID,
    )
    if configured:
        return configured
    row = db.execute(
        "SELECT id FROM users WHERE role = ? ORDER BY id ASC LIMIT 1",
        (ROLE_ELDER,),
    ).fetchone()
    return int(row["id"]) if row else None


def load_current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    db = get_db()
    try:
        ensure_user_mcp_token(db, int(user_id))
    except Exception:  # noqa: BLE001
        pass
    return db.execute(
        "SELECT id, username, email, role, mcp_token, created_at FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()


def effective_care_user_id() -> int | None:
    """业务数据归属：家属登录时使用绑定的老人账号。"""
    if not session.get("user_id"):
        return None
    if session.get("role") == ROLE_FAMILY:
        elder_id = session.get("elder_user_id")
        if elder_id and _user_exists(int(elder_id)):
            return int(elder_id)
        return None
    uid = session.get("user_id")
    return int(uid) if uid and _user_exists(int(uid)) else None


def establish_session(user, elder=None) -> None:
    session.clear()
    session["user_id"] = user["id"]
    session["username"] = user["username"]
    role = user["role"] if "role" in user.keys() else ROLE_ELDER
    session["role"] = role
    if role == ROLE_FAMILY and elder is not None:
        session["elder_user_id"] = elder["id"]
        session["elder_username"] = elder["username"]


def render_dashboard(template: str, active: str, **context):
    user = load_current_user()
    context.setdefault("user", user)
    context["active"] = active
    context["role"] = session.get("role", ROLE_ELDER)
    context["role_label"] = ROLE_LABELS.get(context["role"], "账号")
    context["elder_username"] = session.get("elder_username")
    return render_template(template, **context)


@app.context_processor
def inject_workspace_assistant():
    logged_in = bool(session.get("user_id"))
    return {
        "show_assistant": logged_in,
        "assistant_enabled": deepseek_configured() if logged_in else False,
        "assistant_care_label": session.get("elder_username") or session.get("username") or "",
    }


@app.before_request
def ensure_db_and_protect():
    init_db()
    open_endpoints = {
        "landing",
        "login",
        "register",
        "forgot_password",
        "static",
        "api_mcp_matters_create",
        "api_mcp_matters_list",
        "api_mcp_matters_complete",
        "api_mcp_meds_today",
        "api_mcp_meds_taken",
        "api_mcp_today_agenda",
        "api_mcp_reminders_due",
        "api_mcp_reminder_fired",
        "api_mcp_whoami",
    }
    if request.endpoint in open_endpoints or request.endpoint is None:
        return None
    if not session.get("user_id"):
        flash("请先登录后再访问网站。", "warning")
        return redirect(url_for("login", next=request.path))
    return None


def validate_username(username: str) -> str | None:
    username = username.strip()
    if not username:
        return "请输入用户名。"
    if not USERNAME_RE.match(username):
        return "用户名需为 2–32 位字母、数字、下划线或中文。"
    return None


def validate_email(email: str) -> str | None:
    email = email.strip()
    if not email:
        return "请输入邮箱。"
    if not EMAIL_RE.match(email):
        return "邮箱格式不正确。"
    return None


def validate_password(password: str, confirm: str | None = None) -> str | None:
    if not password:
        return "请输入密码。"
    if len(password) < 6:
        return "密码至少 6 位。"
    if confirm is not None and password != confirm:
        return "两次输入的密码不一致。"
    return None


def validate_role(role: str) -> str | None:
    if role not in VALID_ROLES:
        return "请选择账号类型：老人或家属。"
    return None


def _cst_context(user_id: int) -> dict:
    return build_cst_overview(get_db(), user_id)


@app.route("/")
def landing():
    """公开展示首页（无需登录），登录按钮进入原登录页。"""
    return render_template(
        "landing.html",
        logged_in=bool(session.get("user_id")),
    )


@app.route("/dashboard")
@login_required
def dashboard():
    user = load_current_user()
    elder_id = effective_care_user_id()
    if not user or not elder_id:
        session.clear()
        flash("无法确认照护账号，请重新登录。", "warning")
        return redirect(url_for("login"))
    role = session.get("role", ROLE_ELDER)
    is_family = role == ROLE_FAMILY
    db = get_db()
    board = board_today(db, elder_id)
    device = None if is_family else get_device(db, elder_id)
    # 家属也需要查看绑定老人的 CST 进度（只读）
    cst = _cst_context(elder_id)

    today_tasks = []
    for run in board["tasks"][:5]:
        step_note = "尚未开始"
        if run["status"] == "completed":
            step_note = "今日已完成"
        elif run.get("current_step"):
            step_note = f"第 {run['current_step']['index'] + 1}/{run['total_steps']} 步：{run['current_step']['content']}"
        today_tasks.append(
            {
                "time": run.get("schedule_time") or "今日",
                "title": run["title"],
                "note": f"{run['status_label']} · {step_note}",
                "url": url_for("tasks_page", focus_id=run["task_id"]),
            }
        )
    if not today_tasks:
        if is_family:
            today_tasks = [
                {
                    "time": "随时",
                    "title": "创建今日照护任务",
                    "note": "把复杂事情拆成多步，老人端一次只看当前一步",
                    "url": url_for("tasks_page"),
                },
                {
                    "time": "用药",
                    "title": "核对用药清单",
                    "note": "维护服药时间，查看今日是否按时服用",
                    "url": url_for("medication"),
                },
            ]
        else:
            today_tasks = [
                {
                    "time": "建议上午",
                    "title": f"第 {cst['current_num']} 次 CST · {cst['current_title']}",
                    "note": "45 分钟认知刺激疗程，可在网页或 CST 终端完成",
                    "url": url_for("cst_session", session_num=cst["current_num"]),
                },
                {
                    "time": "随时",
                    "title": "任务清单",
                    "note": "家属可创建多步日程；老人一次只看当前一步",
                    "url": url_for("tasks_page"),
                },
                {
                    "time": "12:00",
                    "title": "午间用药提醒",
                    "note": "请核对当日用药是否按时服用",
                    "url": url_for("medication"),
                },
            ]

    if is_family:
        meds = list_medications(db, elder_id, active_only=True)
        modules = [
            {
                "title": "任务清单",
                "desc": "创建多步照护日程，查看老人完成进度，必要时代为推进。",
                "icon": "brain",
                "status": "可用",
                "url": url_for("tasks_page"),
            },
            {
                "title": "代办清单",
                "desc": "查看与勾选老人的简单代办（吃药提醒等），与小智语音同步。",
                "icon": "brain",
                "status": "可用",
                "url": url_for("todos_page"),
            },
            {
                "title": "用药管理",
                "desc": "维护用药清单与服药时间，远程查看依从记录。",
                "icon": "pill",
                "status": "可用",
                "url": url_for("medication"),
            },
        ]
        care_stats = {
            "task_pending": board.get("pending_count", 0),
            "task_total": board.get("total", 0),
            "med_count": len(meds),
        }
        voice_matters = list_matters(db, elder_id, status=None, limit=15)
        mcp_token = ""
        xiaozhi_links = []
        if user:
            try:
                mcp_token = ensure_user_mcp_token(db, int(user["id"]))
            except Exception:  # noqa: BLE001
                mcp_token = (user["mcp_token"] if "mcp_token" in user.keys() else "") or ""
            xiaozhi_links = list_xiaozhi_links_for_elder(db, elder_id)
        return render_dashboard(
            "index.html",
            "dashboard",
            cst=cst,
            device=None,
            modules=modules,
            today_tasks=today_tasks,
            ro=None,
            care_stats=care_stats,
            voice_matters=voice_matters,
            mcp_token=mcp_token,
            xiaozhi_links=xiaozhi_links,
            **xiaozhi_bind_template_vars(),
        )

    modules = [
        {
            "title": "CST 疗程",
            "desc": "标准 14 次认知刺激疗法，含现实定向、主题讨论与感官活动，延缓轻中度认知衰退。",
            "icon": "brain",
            "status": "可用",
            "url": url_for("cst_index"),
        },
        {
            "title": "任务清单",
            "desc": "把一件事拆成有顺序的多步；老人可暂停续做，进度云端同步。",
            "icon": "brain",
            "status": "可用",
            "url": url_for("tasks_page"),
        },
        {
            "title": "代办清单",
            "desc": "记下今天下午三点吃药等简单事项；可在网站勾选，也可让小智语音查询。",
            "icon": "brain",
            "status": "可用",
            "url": url_for("todos_page"),
        },
        {
            "title": "CST 终端",
            "desc": "按当次课程主题看图说话，AI 引导员主持练习。",
            "icon": "ai",
            "status": "可用" if device else "待绑定",
            "url": url_for("device_index"),
        },
        {
            "title": "AI 陪伴",
            "desc": "轻松闲聊心情与回忆，与 CST 课程练习分开。",
            "icon": "brain",
            "status": "可用" if deepseek_configured() else "待配置",
            "url": url_for("ai_chat_page"),
        },
        {
            "title": "用药管理",
            "desc": "维护用药清单与服药时间，支持家属远程查看依从记录。",
            "icon": "pill",
            "status": "可用",
            "url": url_for("medication"),
        },
    ]
    mcp_token = ""
    xiaozhi_links = []
    if user:
        try:
            mcp_token = ensure_user_mcp_token(db, int(user["id"]))
        except Exception:  # noqa: BLE001
            mcp_token = (user["mcp_token"] if "mcp_token" in user.keys() else "") or ""
        xiaozhi_links = list_xiaozhi_links_for_elder(db, elder_id)
    return render_dashboard(
        "index.html",
        "dashboard",
        cst=cst,
        device=device,
        modules=modules,
        today_tasks=today_tasks,
        ro=reality_orientation_context(),
        care_stats=None,
        voice_matters=list_matters(db, elder_id, status=None, limit=15),
        mcp_token=mcp_token,
        xiaozhi_links=xiaozhi_links,
        **xiaozhi_bind_template_vars(),
    )


def _redirect_family_from_elder_modules():
    """家属端不提供 CST / AI 陪伴等老人训练模块。"""
    if session.get("role") == ROLE_FAMILY:
        flash("记忆练习、CST 终端与 AI 陪伴请在老人账号中使用。家属端可查看进度，并管理任务与用药。", "info")
        return redirect(url_for("dashboard"))
    return None


@app.route("/cst")
@login_required
def cst_index():
    blocked = _redirect_family_from_elder_modules()
    if blocked:
        return blocked
    user = load_current_user()
    cst = _cst_context(effective_care_user_id())
    return render_dashboard("cst/index.html", "cst", cst=cst, ro=reality_orientation_context())


@app.route("/cst/session/<int:session_num>", methods=["GET", "POST"])
@login_required
def cst_session(session_num: int):
    blocked = _redirect_family_from_elder_modules()
    if blocked:
        return blocked
    user = load_current_user()
    info = get_session(session_num)
    if info is None:
        flash("未找到该次 CST 课程。", "error")
        return redirect(url_for("cst_index"))

    db = get_db()
    profile = get_cst_profile(db, effective_care_user_id())
    existing = get_session_log(db, effective_care_user_id(), session_num)

    if request.method == "POST":
        if not info["mvp_ready"]:
            flash("该主题课程内容尚在完善中，请先完成前 3 次标准课。", "warning")
            return redirect(url_for("cst_index"))

        mood = (request.form.get("mood") or "").strip()
        notes = (request.form.get("notes") or "").strip()
        ai_summary = (request.form.get("ai_summary") or "").strip()
        if not ai_summary:
            ai_summary = f"完成第 {session_num} 次 CST「{info['title']}」，共 {len(info['steps'])} 个环节。"

        if existing:
            db.execute(
                """
                UPDATE cst_session_log
                SET mood = ?, notes = ?, ai_summary = ?, status = 'completed',
                    completed_at = datetime('now', 'localtime')
                WHERE user_id = ? AND session_num = ?
                """,
                (mood, notes, ai_summary, effective_care_user_id(), session_num),
            )
        else:
            db.execute(
                """
                INSERT INTO cst_session_log (user_id, session_num, mood, notes, ai_summary)
                VALUES (?, ?, ?, ?, ?)
                """,
                (effective_care_user_id(), session_num, mood, notes, ai_summary),
            )
        db.commit()
        flash(f"第 {session_num} 次 CST「{info['title']}」已记录完成。", "success")
        return redirect(url_for("cst_index"))

    return render_dashboard(
        "cst/session.html",
        "cst",
        session_info=info,
        profile=profile,
        existing=existing,
        ro=reality_orientation_context(),
        cst=_cst_context(effective_care_user_id()),
        is_family=session.get("role") == ROLE_FAMILY,
        care_label=session.get("elder_username") or session.get("username") or "老人",
        materials=list_materials(get_db(), effective_care_user_id()),
        practice_run=get_active_run(get_db(), effective_care_user_id(), session_num),
        ai_enabled=deepseek_configured(),
        speech_enabled=baidu_speech_configured(),
    )


@app.route("/cst/materials/upload", methods=["POST"])
@login_required
def cst_materials_upload():
    if session.get("role") != ROLE_FAMILY:
        flash("仅家属可上传老人资料。", "error")
        return redirect(request.referrer or url_for("cst_index"))
    elder_id = effective_care_user_id()
    session_num = request.form.get("session_num", type=int) or 1
    title = (request.form.get("title") or "").strip()
    caption = (request.form.get("caption") or "").strip()
    text_content = (request.form.get("text_content") or "").strip()
    kind = (request.form.get("kind") or "photo").strip()
    file_storage = request.files.get("file")
    try:
        save_material(
            get_db(),
            elder_user_id=elder_id,
            uploaded_by=session["user_id"],
            title=title,
            caption=caption,
            kind=kind,
            file_storage=file_storage,
            text_content=text_content,
        )
        flash("资料已上传，可用于生成个性化练习题。", "success")
    except ValueError as exc:
        flash(str(exc), "error")
    except Exception as exc:  # noqa: BLE001
        flash(f"上传失败：{exc}", "error")
    return redirect(url_for("cst_session", session_num=session_num) + "#cst-materials")


@app.route("/cst/materials/<int:material_id>/delete", methods=["POST"])
@login_required
def cst_materials_delete(material_id: int):
    if session.get("role") != ROLE_FAMILY:
        flash("仅家属可删除资料。", "error")
        return redirect(request.referrer or url_for("cst_index"))
    session_num = request.form.get("session_num", type=int) or 1
    ok = deactivate_material(get_db(), material_id, effective_care_user_id())
    flash("资料已移除。" if ok else "移除失败。", "success" if ok else "error")
    return redirect(url_for("cst_session", session_num=session_num) + "#cst-materials")


@app.route("/cst/materials/<int:material_id>/file")
@login_required
def cst_materials_file(material_id: int):
    elder_id = effective_care_user_id()
    mat = get_material(get_db(), material_id, elder_id)
    if not mat:
        return ("Not found", 404)
    path = material_abs_path(mat)
    if not path:
        return ("Not found", 404)
    from flask import send_file

    return send_file(path, mimetype=mat.get("mime_type") or None, download_name=mat.get("file_name") or path.name)


@app.route("/api/speech/config", methods=["GET"])
@login_required
def api_speech_config():
    return jsonify({"ok": True, **public_speech_config()})


@app.route("/api/speech/tts", methods=["POST"])
@login_required
def api_speech_tts():
    if not baidu_speech_configured():
        return jsonify({"ok": False, "error": "未配置百度语音凭证，请在 .env 填写 BAIDU_API_KEY/SECRET 或 BAIDU_ACCESS_TOKEN"}), 503
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"ok": False, "error": "text 不能为空"}), 400
    try:
        spd = data.get("spd")
        per = data.get("per")
        pit = data.get("pit")
        vol = data.get("vol")
        aue = data.get("aue")
        audio = synthesize_speech(
            text,
            spd=int(spd) if spd is not None else None,
            per=int(per) if per is not None else None,
            pit=int(pit) if pit is not None else None,
            vol=int(vol) if vol is not None else None,
            aue=int(aue) if aue is not None else None,
            cuid=f"user-{session.get('user_id') or 'web'}",
        )
        from flask import Response

        # aue=3 为 mp3；若前端请求 wav/pcm 仍按实际返回
        mime = "audio/mp3" if (aue is None or int(aue) == 3) else "audio/wav"
        return Response(audio, mimetype=mime)
    except Exception as exc:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.route("/api/speech/recognize", methods=["POST"])
@login_required
def api_speech_recognize():
    if not baidu_speech_configured():
        return jsonify({"ok": False, "error": "未配置百度语音凭证"}), 503
    audio = request.files.get("audio") or request.files.get("file")
    if not audio:
        return jsonify({"ok": False, "error": "请上传音频文件字段 audio"}), 400
    raw = audio.read()
    format_ = (request.form.get("format") or "wav").strip().lower()
    try:
        rate = int(request.form.get("rate") or 16000)
    except ValueError:
        rate = 16000
    try:
        result = recognize_speech(
            raw,
            format_=format_,
            rate=rate,
            cuid=f"user-{session.get('user_id') or 'web'}",
        )
        return jsonify({"ok": True, "text": result["text"], "raw": result.get("raw")})
    except Exception as exc:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.route("/api/speech/evaluate", methods=["POST"])
@login_required
def api_speech_evaluate():
    data = request.get_json(silent=True) or {}
    question = data.get("question") if isinstance(data.get("question"), dict) else {}
    text = str(data.get("text") or "")
    result = evaluate_soft_answer(text, question)
    return jsonify({"ok": True, **result})


# —— 小智 MCP 桥接 API（Token 鉴权，供本机 mcp_exe 调用）——


@app.route("/api/mcp/matters", methods=["POST"])
@mcp_token_required
def api_mcp_matters_create():
    """代办录入 → 同步写入网站（可带提醒时间 / 相对延迟）。"""
    db = get_db()
    elder_id = resolve_mcp_elder_id(db)
    if not elder_id:
        return jsonify({"ok": False, "error": "未找到老人账号，请配置 MCP_ELDER_USER_ID"}), 400
    data = request.get_json(silent=True) or {}
    text = str(data.get("text") or data.get("body") or "").strip()
    due_at = str(data.get("due_at") or data.get("remind_at") or data.get("time") or "").strip()
    delay_raw = data.get("delay_seconds")
    delay_seconds = None
    if delay_raw not in (None, ""):
        try:
            delay_seconds = max(1, int(delay_raw))
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "delay_seconds 必须是正整数"}), 400
    elif due_at:
        parsed_delay = parse_relative_delay_seconds(due_at)
        if parsed_delay is not None:
            delay_seconds = parsed_delay
            due_at = ""
    if not text:
        return jsonify({"ok": False, "error": "事项内容不能为空"}), 400
    try:
        matter = add_matter(
            db,
            elder_id,
            text,
            source="xiaozhi",
            due_at=due_at or None,
            delay_seconds=delay_seconds,
        )
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    wake_text = wake_prompt_for_matter(matter)
    return jsonify(
        {
            "ok": True,
            "matter": matter,
            "wake_text": wake_text,
            "device_schedule": {
                "tool": "self.schedule_reminder",
                "delay_seconds": matter.get("delay_seconds"),
                "message": wake_text,
                "hint": "若设备已烧录记忆港湾提醒固件，请同时调用 self.schedule_reminder，到点将 WakeWordInvoke → SendWakeWordDetected。",
            }
            if matter.get("delay_seconds")
            else None,
        }
    )


@app.route("/api/mcp/reminders/due", methods=["GET"])
@mcp_token_required
def api_mcp_reminders_due():
    """列出已到期、尚未播报的提醒。"""
    db = get_db()
    elder_id = resolve_mcp_elder_id(db)
    if not elder_id:
        return jsonify({"ok": False, "error": "未找到老人账号"}), 400
    items = list_due_reminders(db, elder_id, limit=request.args.get("limit", type=int) or 20)
    prompts = [wake_prompt_for_matter(m) for m in items]
    speak = (
        "有 " + str(len(items)) + " 条到点提醒：" + "；".join(m.get("body") or "" for m in items)
        if items
        else "当前没有到点提醒。"
    )
    return jsonify(
        {
            "ok": True,
            "reminders": items,
            "wake_texts": prompts,
            "count": len(items),
            "speak": speak,
        }
    )


@app.route("/api/mcp/reminders/<int:matter_id>/fired", methods=["POST"])
@mcp_token_required
def api_mcp_reminder_fired(matter_id: int):
    """设备/桥接到点唤醒后回写，避免重复提醒。"""
    db = get_db()
    elder_id = resolve_mcp_elder_id(db)
    if not elder_id:
        return jsonify({"ok": False, "error": "未找到老人账号"}), 400
    matter = mark_matter_reminded(db, elder_id, matter_id)
    if not matter:
        return jsonify({"ok": False, "error": "未找到该代办"}), 404
    return jsonify({"ok": True, "matter": matter})


@app.route("/api/mcp/matters", methods=["GET"])
@mcp_token_required
def api_mcp_matters_list():
    db = get_db()
    elder_id = resolve_mcp_elder_id(db)
    if not elder_id:
        return jsonify({"ok": False, "error": "未找到老人账号"}), 400
    status = request.args.get("status")
    if status == "all":
        status = None
    keyword = request.args.get("keyword") or ""
    limit = request.args.get("limit", type=int) or 20
    items = list_matters(db, elder_id, status=status, keyword=keyword or None, limit=limit)
    return jsonify(
        {
            "ok": True,
            "matters": items,
            "count": len(items),
            "speak": speak_matters_summary(items, keyword=keyword),
        }
    )


@app.route("/api/mcp/matters/complete", methods=["POST"])
@mcp_token_required
def api_mcp_matters_complete():
    """老人完成事项后，同步修改网站状态为已完成。"""
    db = get_db()
    elder_id = resolve_mcp_elder_id(db)
    if not elder_id:
        return jsonify({"ok": False, "error": "未找到老人账号"}), 400
    data = request.get_json(silent=True) or {}
    matter_id = data.get("matter_id") or data.get("id")
    keyword = str(data.get("keyword") or data.get("text") or "").strip()
    mid = int(matter_id) if matter_id not in (None, "") else None
    matter = complete_matter(db, elder_id, matter_id=mid, keyword=keyword or None)
    if not matter:
        return jsonify({"ok": False, "error": "未找到可完成的事项"}), 404
    return jsonify({"ok": True, "matter": matter})


@app.route("/api/mcp/medication/today", methods=["GET"])
@mcp_token_required
def api_mcp_meds_today():
    """今日要吃什么药 → 读取网站用药计划。"""
    db = get_db()
    elder_id = resolve_mcp_elder_id(db)
    if not elder_id:
        return jsonify({"ok": False, "error": "未找到老人账号"}), 400
    plan = today_plan(db, elder_id)
    pending = [p for p in plan if p.get("pending")]
    summary = adherence_summary(db, elder_id)
    lines = []
    for p in plan:
        name = p.get("display_name") or p.get("name") or "药品"
        dose = p.get("dose") or ""
        st = p.get("status_label") or p.get("status") or ""
        tm = p.get("time") or p.get("schedule_time") or ""
        lines.append(f"{tm} {name} {dose}（{st}）".strip())
    speak = "今天没有安排用药。" if not plan else "今天的药有：" + "；".join(lines)
    if pending:
        speak += "。其中还没吃的有：" + "、".join(
            (x.get("display_name") or x.get("name") or "药") for x in pending
        )
    elif plan:
        speak += "。目前该吃的都已记录完成。"
    return jsonify(
        {
            "ok": True,
            "plan": plan,
            "pending": pending,
            "summary": summary,
            "speak": speak,
        }
    )


@app.route("/api/mcp/today", methods=["GET"])
@mcp_token_required
def api_mcp_today_agenda():
    """今日安排：一次返回待办 + 用药，供小智合并口述。"""
    db = get_db()
    elder_id = resolve_mcp_elder_id(db)
    if not elder_id:
        return jsonify({"ok": False, "error": "未找到老人账号"}), 400

    matters = list_matters(db, elder_id, status="open", limit=30)
    plan = today_plan(db, elder_id)
    pending_meds = [p for p in plan if p.get("pending")]

    matter_lines = []
    for i, m in enumerate(matters, 1):
        due = m.get("due_at_label") or ""
        due_part = f"（提醒 {due}）" if due else ""
        matter_lines.append(f"{i}. {m.get('body')}{due_part}")

    med_lines = []
    for p in plan:
        name = p.get("display_name") or p.get("name") or "药品"
        dose = p.get("dose") or ""
        st = p.get("status_label") or p.get("status") or ""
        tm = p.get("time") or p.get("schedule_time") or ""
        med_lines.append(f"{tm} {name} {dose}（{st}）".strip())

    parts: list[str] = ["今天要做的事如下。"]

    if matter_lines:
        parts.append("【代办】共 " + str(len(matter_lines)) + " 件：" + "；".join(matter_lines) + "。")
    else:
        parts.append("【代办】目前没有未完成的代办。")

    if med_lines:
        parts.append("【用药】" + "；".join(med_lines) + "。")
        if pending_meds:
            parts.append(
                "其中还没吃的有："
                + "、".join(
                    (x.get("display_name") or x.get("name") or "药") for x in pending_meds
                )
                + "。"
            )
        else:
            parts.append("目前该吃的药都已记录完成。")
    else:
        parts.append("【用药】今天没有安排用药。")

    speak = "".join(parts)
    return jsonify(
        {
            "ok": True,
            "matters": matters,
            "matters_count": len(matters),
            "medication_plan": plan,
            "medication_pending": pending_meds,
            "speak": speak,
        }
    )


@app.route("/api/mcp/medication/taken", methods=["POST"])
@mcp_token_required
def api_mcp_meds_taken():
    """老人说「我吃过了」→ 按药名匹配并标记已服用。"""
    db = get_db()
    elder_id = resolve_mcp_elder_id(db)
    if not elder_id:
        return jsonify({"ok": False, "error": "未找到老人账号"}), 400
    data = request.get_json(silent=True) or {}
    name = str(data.get("name") or data.get("keyword") or data.get("text") or "").strip()
    med_id = data.get("medication_id") or data.get("med_id")
    plan = today_plan(db, elder_id)
    target = None
    if med_id:
        target = next((p for p in plan if int(p.get("id") or 0) == int(med_id)), None)
    elif name:
        for p in plan:
            label = f"{p.get('display_name') or ''}{p.get('name') or ''}{p.get('alias') or ''}"
            if name in label or (p.get("name") and p.get("name") in name):
                target = p
                break
            # 软匹配
            body = label
            i = 0
            for ch in body:
                if i < len(name) and ch == name[i]:
                    i += 1
                if i >= len(name):
                    target = p
                    break
            if target:
                break
    if not target:
        return jsonify({"ok": False, "error": f"未找到匹配的今日药品：{name or med_id}"}), 404
    ok = record_medication_status(
        db, int(target["id"]), elder_id, STATUS_TAKEN, recorded_by=elder_id
    )
    if not ok:
        return jsonify({"ok": False, "error": "记录服药失败"}), 500
    med_name = target.get("display_name") or target.get("name") or "这药"
    return jsonify(
        {
            "ok": True,
            "medication": target,
            "speak": f"好的，已在网站记下「{med_name}」今天服用过了。",
        }
    )


@app.route("/api/mcp/whoami", methods=["GET"])
@mcp_token_required
def api_mcp_whoami():
    """返回当前 Token 对应的记忆归属（用于核对是否区分到正确用户）。"""
    db = get_db()
    elder_id = resolve_mcp_elder_id(db)
    row = db.execute(
        "SELECT id, username, role, mcp_token FROM users WHERE id = ?",
        (elder_id,),
    ).fetchone()
    identity = getattr(g, "mcp_identity", {}) or {}
    return jsonify(
        {
            "ok": True,
            "elder_user_id": elder_id,
            "username": row["username"] if row else None,
            "auth": identity.get("auth"),
            "first_use": bool(identity.get("first_use")),
            "xiaozhi_user_id": identity.get("xiaozhi_user_id"),
        }
    )


@app.route("/settings/mcp-token", methods=["POST"])
@login_required
def settings_mcp_token():
    """刷新个人语音同步密钥，或用小智 MCP 接入点 Token 绑定。"""
    db = get_db()
    user = load_current_user()
    if not user:
        flash("请先登录。", "warning")
        return redirect(url_for("login"))
    action = (request.form.get("action") or "").strip()
    elder_id = effective_care_user_id()
    if action == "rotate":
        rotate_user_mcp_token(db, int(user["id"]))
        flash("已生成新的语音同步密钥，请同步更新小智 MCP 配置。", "success")
    elif action == "bind_xiaozhi":
        if env_force_bind_active():
            flash(
                f"已启用环境变量强制绑定（小智 {XIAOZHI_USER_ID} → 账号「{MCP_ELDER_USERNAME or MCP_ELDER_USER_ID}」），无需手动绑定。",
                "warning",
            )
            return redirect(url_for("dashboard"))
        raw_token = (
            request.form.get("xiaozhi_token")
            or request.form.get("xiaozhi_user_id")
            or ""
        ).strip()
        try:
            parsed = parse_xiaozhi_endpoint_token(raw_token)
            xid = parsed["xiaozhi_user_id"]
            agent = parsed.get("xiaozhi_agent_id") or None
            bind_xiaozhi_user(db, int(elder_id), xid, agent_id=agent)
            elder_name = db.execute(
                "SELECT username FROM users WHERE id = ?", (elder_id,)
            ).fetchone()
            label = elder_name["username"] if elder_name else str(elder_id)
            extra = f" · Agent {agent}" if agent else ""
            flash(
                f"已用小智 Token 绑定用户 {xid}{extra} → 记忆港湾账号「{label}」。",
                "success",
            )
        except ValueError as exc:
            flash(str(exc), "danger")
    elif action == "unbind_xiaozhi":
        xid = (request.form.get("xiaozhi_user_id") or "").strip()
        if env_force_bind_active() and xid == XIAOZHI_USER_ID:
            flash(
                f"小智用户 {xid} 由环境变量强制绑定到「{MCP_ELDER_USERNAME or MCP_ELDER_USER_ID}」，不能解除。",
                "warning",
            )
            return redirect(url_for("dashboard"))
        if unbind_xiaozhi_user(db, int(elder_id), xid):
            flash(f"已解除与小智用户 {xid} 的绑定。", "success")
        else:
            flash("未找到该绑定记录。", "warning")
    else:
        flash("未知操作。", "warning")
    return redirect(url_for("dashboard"))


@app.route("/api/cst/session/<int:session_num>/card-speak", methods=["POST"])
@login_required
def api_cst_card_speak(session_num: int):
    """课程练习听题：DeepSeek 渲染温柔短句，前端再 TTS 播报。"""
    info = get_session(session_num)
    if not info:
        return jsonify({"ok": False, "error": "未找到该次课程"}), 404
    data = request.get_json(silent=True) or {}
    card_id = (data.get("card_id") or "").strip()
    cards = info.get("visual_cards") or []
    items = info.get("practice_items") or []
    card = next((c for c in cards if str(c.get("id")) == card_id), None)
    if card is None:
        card = next((c for c in items if str(c.get("id")) == card_id), None)
        if card is not None:
            card = {
                "label": card.get("speak_label") or card.get("prompt") or "练习题",
                "caption": card.get("speak_caption") or card.get("hint") or "",
                "ai_prompt": card.get("ai_prompt") or card.get("prompt") or "",
            }
    if card is None and (data.get("label") or data.get("ai_prompt") or data.get("prompt")):
        card = {
            "label": data.get("label") or "练习题",
            "caption": data.get("caption") or data.get("hint") or "",
            "ai_prompt": data.get("ai_prompt") or data.get("prompt") or "",
        }
    if card is None:
        return jsonify({"ok": False, "error": "未找到题目"}), 404

    result = render_card_speak_text(
        session_title=info.get("title") or f"第{session_num}次",
        card_label=str(card.get("label") or "练习题"),
        card_caption=str(card.get("caption") or ""),
        ai_prompt=str(card.get("ai_prompt") or ""),
    )
    return jsonify({"ok": True, **result, "card_id": card_id})


@app.route("/api/cst/session/<int:session_num>/practice-reply", methods=["POST"])
@login_required
def api_cst_practice_reply(session_num: int):
    """课程练习录音后：DeepSeek 根据识别文本温柔扩展话题。"""
    info = get_session(session_num)
    if not info:
        return jsonify({"ok": False, "error": "未找到该次课程"}), 404
    data = request.get_json(silent=True) or {}
    result = expand_practice_reply(
        session_title=info.get("title") or f"第{session_num}次",
        prompt=str(data.get("prompt") or ""),
        transcript=str(data.get("transcript") or data.get("text") or ""),
        hint=str(data.get("hint") or ""),
    )
    return jsonify({"ok": True, **result})


@app.route("/api/cst/practice/<int:session_num>/generate", methods=["POST"])
@login_required
def api_cst_practice_generate(session_num: int):
    if session.get("role") != ROLE_FAMILY:
        return jsonify({"ok": False, "error": "仅家属可生成/刷新练习题"}), 403
    elder_id = effective_care_user_id()
    data = request.get_json(silent=True) or {}
    count = int(data.get("count") or 10)
    count = max(6, min(count, 16))
    try:
        result = generate_practice_questions(
            get_db(),
            elder_user_id=elder_id,
            session_num=session_num,
            created_by=session["user_id"],
            count=count,
            force_new=True,
        )
        return jsonify(result)
    except Exception as exc:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.route("/api/cst/practice/<int:session_num>", methods=["GET"])
@login_required
def api_cst_practice_get(session_num: int):
    elder_id = effective_care_user_id()
    run = get_active_run(get_db(), elder_id, session_num)
    if not run:
        return jsonify({"ok": True, "run": None})
    return jsonify({"ok": True, "run": run})


@app.route("/api/cst/practice/<int:session_num>/answer", methods=["POST"])
@login_required
def api_cst_practice_answer(session_num: int):
    elder_id = effective_care_user_id()
    data = request.get_json(silent=True) or {}
    run_id = data.get("run_id")
    try:
        run_id = int(run_id)
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "run_id 无效"}), 400
    result = save_answer(
        get_db(),
        run_id=run_id,
        elder_user_id=elder_id,
        question_id=str(data.get("question_id") or ""),
        answer_text=str(data.get("answer_text") or ""),
        answered_by=session["user_id"],
        answerer_role=session.get("role") or ROLE_ELDER,
    )
    status = 200 if result.get("ok") else 400
    return jsonify(result), status


@app.route("/training")
@login_required
def training_redirect():
    blocked = _redirect_family_from_elder_modules()
    if blocked:
        return blocked
    return redirect(url_for("cst_index"))


@app.route("/device", methods=["GET", "POST"])
@login_required
def device_index():
    blocked = _redirect_family_from_elder_modules()
    if blocked:
        return blocked
    user = load_current_user()
    db = get_db()
    device = get_device(db, effective_care_user_id())
    cst = _cst_context(effective_care_user_id())
    logs = get_all_logs(db, effective_care_user_id())

    if request.method == "POST":
        action = request.form.get("action", "bind")
        if action == "bind":
            code = (request.form.get("device_code") or "").strip() or "MH-AI-001"
            name = (request.form.get("device_name") or "").strip() or "记忆港湾 CST 终端"
            if device:
                db.execute(
                    """
                    UPDATE device_binding
                    SET device_name = ?, device_code = ?, is_online = 1,
                        last_sync = datetime('now', 'localtime')
                    WHERE user_id = ?
                    """,
                    (name, code, effective_care_user_id()),
                )
            else:
                db.execute(
                    """
                    INSERT INTO device_binding (user_id, device_name, device_code, is_online, last_sync)
                    VALUES (?, ?, ?, 1, datetime('now', 'localtime'))
                    """,
                    (effective_care_user_id(), name, code),
                )
            db.commit()
            flash("CST 终端已绑定并标记为在线。", "success")
        elif action == "unbind":
            db.execute("DELETE FROM device_binding WHERE user_id = ?", (effective_care_user_id(),))
            db.commit()
            flash("已解绑 CST 终端。", "success")
        return redirect(url_for("device_index"))

    current_session = get_session(cst["current_num"])
    profile = get_cst_profile(db, effective_care_user_id())
    ai_opening = ""
    if current_session:
        ai_opening = get_opening_line(current_session, profile["group_name"])
    return render_dashboard(
        "device/index.html",
        "device",
        device=device,
        cst=cst,
        current_session=current_session,
        logs=logs[-5:],
        ro=reality_orientation_context(),
        ai_system_prompt=build_session_system_prompt(current_session) if current_session else "",
        ai_opening=ai_opening,
    )


@app.route("/ai-chat")
@login_required
def ai_chat_page():
    """独立 AI 陪伴闲聊（与 CST 主题引导分离）。"""
    blocked = _redirect_family_from_elder_modules()
    if blocked:
        return blocked
    return render_dashboard(
        "chat/index.html",
        "ai_chat",
        companion_enabled=deepseek_configured(),
    )


@app.route("/api/companion/chat", methods=["POST"])
@login_required
def api_companion_chat():
    blocked = _redirect_family_from_elder_modules()
    if blocked:
        return jsonify({"ok": False, "reply": "请使用老人账号进行陪伴聊天。"}), 403
    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    history = data.get("history") if isinstance(data.get("history"), list) else []
    try:
        result = run_companion_chat(
            message=message,
            username=session.get("username") or "",
            history=history,
        )
    except Exception as exc:  # noqa: BLE001
        app.logger.exception("companion chat failed: %s", exc)
        return jsonify({"ok": False, "reply": f"陪伴服务异常：{exc}"}), 500
    status = 200 if result.get("ok") else 502
    return jsonify(result), status


@app.route("/api/device/script")
@login_required
def api_device_script():
    """供硬件拉取当日 CST 脚本（JSON）。"""
    user = load_current_user()
    cst = _cst_context(effective_care_user_id())
    info = get_session(cst["current_num"])
    if not info:
        return jsonify({"error": "no session"}), 404
    profile = get_cst_profile(get_db(), effective_care_user_id())
    return jsonify(
        {
            "group_name": profile["group_name"],
            "theme_song": profile["theme_song"],
            "session_num": info["num"],
            "session_title": info["title"],
            "session_theme": info.get("ai_theme", info["title"]),
            "duration_minutes": info["duration"],
            "steps": info["steps"],
            "activities": info["activities"],
            "visual_cards": info.get("visual_cards", []),
            "reality_orientation": reality_orientation_context(),
            "system_prompt": build_session_system_prompt(info),
            "opening_line": get_opening_line(info, profile["group_name"]),
            "ai_role": "CST 引导员：围绕当次主题进行看图说话与词语联想，短句、一次一问、不纠正记忆。",
        }
    )


@app.route("/api/device/chat", methods=["POST"])
@login_required
def api_device_chat():
    """CST 主题对话（演示：规则引导；硬件可替换为真实大模型 + 相同 system_prompt）。"""
    user = load_current_user()
    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    turn = int(data.get("turn") or 0)
    session_num = int(data.get("session_num") or _cst_context(effective_care_user_id())["current_num"])

    info = get_session(session_num)
    if not info:
        return jsonify({"error": "invalid session"}), 400

    result = pick_facilitator_reply(info, message, turn)
    card = None
    if result.get("show_card_id"):
        card = next((c for c in info.get("visual_cards", []) if c["id"] == result["show_card_id"]), None)

    return jsonify(
        {
            "reply": result["reply"],
            "step_hint": result.get("step_hint"),
            "visual_card": card,
            "session_title": info["title"],
            "theme": info.get("ai_theme", info["title"]),
        }
    )


@app.route("/medication", methods=["GET", "POST"])
@login_required
def medication():
    db = get_db()
    elder_id = effective_care_user_id()
    role = session.get("role", ROLE_ELDER)
    is_family = role == ROLE_FAMILY

    if request.method == "POST":
        action = request.form.get("action") or "take"
        try:
            med_id = int(request.form.get("med_id") or "0")
        except ValueError:
            med_id = 0

        if action == "add_from_catalog" and is_family:
            catalog_id = (request.form.get("catalog_id") or "").strip()
            schedule_time = (request.form.get("schedule_time") or "").strip()
            alias = (request.form.get("alias") or "").strip()
            place_area = (request.form.get("place_area") or "").strip()
            dose = (request.form.get("dose") or "").strip() or None
            if not catalog_id or not schedule_time:
                flash("请选择药物目录并设定服药时间。", "error")
            elif not catalog_by_id(catalog_id):
                flash("药物目录项无效。", "error")
            else:
                new_id = add_from_catalog(
                    db,
                    elder_id,
                    catalog_id,
                    schedule_time=schedule_time,
                    dose=dose,
                    alias=alias,
                    place_area=place_area,
                    created_by=session.get("user_id"),
                )
                if new_id:
                    flash("已从药物目录添加到每日计划。", "success")
                else:
                    flash("添加失败，请重试。", "error")
        elif action == "update" and is_family:
            dose = (request.form.get("dose") or "").strip()
            schedule_time = (request.form.get("schedule_time") or "").strip()
            alias = (request.form.get("alias") or "").strip()
            place_area = (request.form.get("place_area") or "").strip()
            note = (request.form.get("note") or "").strip()
            if med_id and dose and schedule_time and update_medication(
                db,
                med_id,
                elder_id,
                dose=dose,
                schedule_time=schedule_time,
                alias=alias,
                place_area=place_area,
                note=note,
            ):
                flash("用药计划已更新。", "success")
            else:
                flash("更新失败，请检查填写内容。", "error")
        elif action == "remove" and is_family:
            if med_id and deactivate_medication(db, med_id, elder_id):
                flash("已从每日计划中移除。", "success")
            else:
                flash("移除失败。", "error")
        elif action in {"take", "proxy", "skip"}:
            status_map = {
                "take": STATUS_TAKEN,
                "proxy": STATUS_PROXY,
                "skip": STATUS_SKIPPED,
            }
            if action == "proxy" and not is_family:
                flash("仅家属可代确认服药。", "error")
            elif action == "skip" and not is_family:
                flash("仅家属可标记跳过。", "error")
            elif med_id and record_medication_status(
                db,
                med_id,
                elder_id,
                status_map[action],
                recorded_by=session.get("user_id"),
            ):
                tips = {
                    "take": "已记录本次服药。",
                    "proxy": "已代确认服药。",
                    "skip": "已记录跳过该药物。",
                }
                flash(tips[action], "success")
            else:
                flash("操作失败，请刷新后重试。", "error")
        else:
            flash("当前身份无权执行该操作或未知操作。", "error")
        return redirect(url_for("medication"))

    summary = adherence_summary(db, elder_id)
    return render_dashboard(
        "medication.html",
        "medication",
        meds=summary["plan"],
        taken_count=summary["taken_count"],
        skipped_count=summary["skipped_count"],
        pending_count=summary["pending_count"],
        adherence=summary["adherence"],
        week_log=week_adherence(db, elder_id),
        week_days=week_schedule(db, elder_id) if is_family else [],
        catalog=catalog_with_status(db, elder_id),
        place_options=PLACE_OPTIONS,
        is_family=is_family,
        care_label=session.get("elder_username") if is_family else session.get("username"),
        ai_enabled=deepseek_configured() if is_family else False,
    )


@app.route("/api/medication/ai-chat", methods=["POST"])
@login_required
def medication_ai_chat():
    if session.get("role") != ROLE_FAMILY:
        return jsonify({"ok": False, "reply": "仅家属账号可使用智能加药。", "added": False}), 403
    elder_id = effective_care_user_id()
    if not elder_id:
        return jsonify({"ok": False, "reply": "未找到绑定的老人账号。", "added": False}), 400
    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    try:
        result = process_smart_add(
            get_db(),
            elder_user_id=elder_id,
            family_user_id=session["user_id"],
            message=message,
            elder_username=session.get("elder_username") or "",
        )
        return jsonify(result)
    except Exception as exc:  # noqa: BLE001
        return jsonify(
            {
                "ok": False,
                "added": False,
                "reply": f"智能加药暂时不可用：{exc}",
                "disclaimer": "仅供照护参考，不能替代医嘱。",
            }
        ), 500


def _api_care_context():
    elder_id = effective_care_user_id()
    if not elder_id:
        return None, None, (jsonify({"ok": False, "error": "未找到照护对象"}), 400)
    role = session.get("role", ROLE_ELDER)
    return elder_id, role, None


@app.route("/todos")
@login_required
def todos_page():
    """老人代办清单（简单事项；与小智 MCP 共用数据）。"""
    elder_id = effective_care_user_id()
    role = session.get("role", ROLE_ELDER)
    is_family = role == ROLE_FAMILY
    db = get_db()
    open_items = list_matters(db, elder_id, status="open", limit=50)
    done_items = list_matters(db, elder_id, status="done", limit=20)
    return render_dashboard(
        "todos.html",
        "todos",
        is_family=is_family,
        care_label=session.get("elder_username") or session.get("username") or "",
        open_items=open_items,
        done_items=done_items,
        open_count=len(open_items),
        done_count=len(done_items),
    )


@app.route("/todos/create", methods=["POST"])
@login_required
def todos_create():
    elder_id = effective_care_user_id()
    role = session.get("role", ROLE_ELDER)
    if role not in {ROLE_FAMILY, ROLE_ELDER}:
        flash("无权创建代办。", "warning")
        return redirect(url_for("todos_page"))
    body = (request.form.get("body") or request.form.get("text") or "").strip()
    due_raw = (request.form.get("due_at") or "").strip()
    source = "family" if role == ROLE_FAMILY else "web"
    try:
        add_matter(
            get_db(),
            elder_id,
            body,
            source=source,
            recorded_by=session.get("user_id"),
            due_at=due_raw or None,
        )
        flash("已加入代办清单。", "success")
    except ValueError as exc:
        flash(str(exc), "danger")
    return redirect(url_for("todos_page"))


@app.route("/api/todos/<int:matter_id>/complete", methods=["POST"])
@login_required
def api_todos_complete(matter_id: int):
    elder_id, _role, err = _api_care_context()
    if err:
        return err
    matter = complete_matter(get_db(), elder_id, matter_id=matter_id)
    if not matter:
        return jsonify({"ok": False, "error": "未找到该代办"}), 404
    return jsonify({"ok": True, "matter": matter})


@app.route("/api/todos/<int:matter_id>/reopen", methods=["POST"])
@login_required
def api_todos_reopen(matter_id: int):
    elder_id, _role, err = _api_care_context()
    if err:
        return err
    matter = reopen_matter(get_db(), elder_id, matter_id)
    if not matter:
        return jsonify({"ok": False, "error": "未找到该代办"}), 404
    return jsonify({"ok": True, "matter": matter})


@app.route("/api/todos/<int:matter_id>/delete", methods=["POST"])
@login_required
def api_todos_delete(matter_id: int):
    elder_id, _role, err = _api_care_context()
    if err:
        return err
    if not delete_matter(get_db(), elder_id, matter_id):
        return jsonify({"ok": False, "error": "未找到该代办"}), 404
    return jsonify({"ok": True})


@app.route("/tasks")
@login_required
def tasks_page():
    elder_id = effective_care_user_id()
    role = session.get("role", ROLE_ELDER)
    is_family = role == ROLE_FAMILY
    db = get_db()
    board = board_today(db, elder_id)
    week = week_overview(db, elder_id)
    templates = list_tasks(db, elder_id, active_only=True)
    focus = None
    focus_id = request.args.get("focus_id", type=int)
    if not is_family:
        if focus_id:
            for run in board["tasks"]:
                if run["task_id"] == focus_id:
                    focus = run
                    break
        if focus is None:
            for run in board["tasks"]:
                if run["status"] in {"in_progress", "paused"}:
                    focus = run
                    break
        if focus is None and board["tasks"]:
            focus = board["tasks"][0]
    care_label = session.get("elder_username") or session.get("username") or "老人"
    return render_dashboard(
        "tasks.html",
        "tasks",
        is_family=is_family,
        board=board,
        week=week,
        templates=templates,
        focus=focus,
        care_label=care_label,
    )


@app.route("/tasks/create", methods=["POST"])
@login_required
def tasks_create():
    role = session.get("role", ROLE_ELDER)
    if role not in {ROLE_FAMILY, ROLE_ELDER}:
        flash("无权创建任务。", "error")
        return redirect(url_for("tasks_page"))
    elder_id = effective_care_user_id()
    title = (request.form.get("title") or "").strip()
    note = (request.form.get("note") or "").strip()
    schedule_time = (request.form.get("schedule_time") or "").strip()
    steps = request.form.getlist("steps")
    try:
        create_task(
            get_db(),
            elder_id,
            title=title,
            steps=steps,
            note=note,
            schedule_time=schedule_time,
            created_by=session.get("user_id"),
        )
        flash("任务已创建。", "success")
    except ValueError as exc:
        flash(str(exc), "error")
    return redirect(url_for("tasks_page") + "#create-task")


@app.route("/tasks/<int:task_id>/update", methods=["POST"])
@login_required
def tasks_update(task_id: int):
    role = session.get("role", ROLE_ELDER)
    if role not in {ROLE_FAMILY, ROLE_ELDER}:
        flash("无权修改任务。", "error")
        return redirect(url_for("tasks_page"))
    elder_id = effective_care_user_id()
    title = (request.form.get("title") or "").strip()
    note = (request.form.get("note") or "").strip()
    schedule_time = (request.form.get("schedule_time") or "").strip()
    steps = request.form.getlist("steps")
    try:
        ok = update_task(
            get_db(),
            task_id,
            elder_id,
            title=title,
            steps=steps,
            note=note,
            schedule_time=schedule_time,
        )
        flash("任务已保存。今日已开始的进度仍按开始时的步骤继续。" if ok else "保存失败。", "success" if ok else "error")
    except ValueError as exc:
        flash(str(exc), "error")
    return redirect(url_for("tasks_page") + "#manage-tasks")


@app.route("/tasks/<int:task_id>/delete", methods=["POST"])
@login_required
def tasks_delete(task_id: int):
    role = session.get("role", ROLE_ELDER)
    if role not in {ROLE_FAMILY, ROLE_ELDER}:
        flash("无权停用任务。", "error")
        return redirect(url_for("tasks_page"))
    ok = deactivate_task(get_db(), task_id, effective_care_user_id())
    flash("任务已停用。" if ok else "停用失败。", "success" if ok else "error")
    return redirect(url_for("tasks_page") + "#manage-tasks")


@app.route("/api/tasks/today", methods=["GET"])
@login_required
def api_tasks_today():
    elder_id, role, err = _api_care_context()
    if err:
        return err
    board = board_today(get_db(), elder_id)
    if role != ROLE_FAMILY:
        slim = []
        for run in board["tasks"]:
            slim.append(
                {
                    "task_id": run["task_id"],
                    "title": run["title"],
                    "status": run["status"],
                    "status_label": run["status_label"],
                    "current_step": run.get("current_step"),
                    "current_step_index": run["current_step_index"],
                    "done_count": run["done_count"],
                    "total_steps": run["total_steps"],
                    "progress_percent": run["progress_percent"],
                }
            )
        board = {**board, "tasks": slim}
    return jsonify({"ok": True, **board})


@app.route("/api/tasks/week", methods=["GET"])
@login_required
def api_tasks_week():
    elder_id, _role, err = _api_care_context()
    if err:
        return err
    return jsonify({"ok": True, "week": week_overview(get_db(), elder_id)})


@app.route("/api/tasks/<int:task_id>/start", methods=["POST"])
@login_required
def api_tasks_start(task_id: int):
    elder_id, _role, err = _api_care_context()
    if err:
        return err
    if not get_task(get_db(), task_id, elder_id):
        return jsonify({"ok": False, "error": "任务不存在"}), 404
    data = request.get_json(silent=True) or {}
    result = start_task(
        get_db(), task_id, elder_id, action_id=(data.get("action_id") or "").strip() or None
    )
    return jsonify(result)


@app.route("/api/tasks/<int:task_id>/pause", methods=["POST"])
@login_required
def api_tasks_pause(task_id: int):
    elder_id, _role, err = _api_care_context()
    if err:
        return err
    data = request.get_json(silent=True) or {}
    result = pause_task(
        get_db(), task_id, elder_id, action_id=(data.get("action_id") or "").strip() or None
    )
    return jsonify(result)


@app.route("/api/tasks/<int:task_id>/resume", methods=["POST"])
@login_required
def api_tasks_resume(task_id: int):
    elder_id, _role, err = _api_care_context()
    if err:
        return err
    data = request.get_json(silent=True) or {}
    result = resume_task(
        get_db(), task_id, elder_id, action_id=(data.get("action_id") or "").strip() or None
    )
    return jsonify(result)


@app.route("/api/tasks/<int:task_id>/advance", methods=["POST"])
@login_required
def api_tasks_advance(task_id: int):
    elder_id, role, err = _api_care_context()
    if err:
        return err
    data = request.get_json(silent=True) or {}
    action_id = (data.get("action_id") or "").strip()
    if not action_id:
        return jsonify({"ok": False, "error": "缺少 action_id"}), 400
    try:
        expected = int(data.get("expected_step_index"))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "expected_step_index 无效"}), 400
    action = (data.get("action") or "").strip()
    result = advance_current_step(
        get_db(),
        task_id,
        elder_id,
        action=action,
        expected_step_index=expected,
        action_id=action_id,
        user_id=session["user_id"],
        is_family=(role == ROLE_FAMILY),
    )
    status = 200 if result.get("ok") else (409 if result.get("conflict") else 400)
    return jsonify(result), status


@app.route("/api/tasks/<int:task_id>/complete-all", methods=["POST"])
@login_required
def api_tasks_complete_all(task_id: int):
    elder_id, role, err = _api_care_context()
    if err:
        return err
    if role not in {ROLE_FAMILY, ROLE_ELDER}:
        return jsonify({"ok": False, "error": "无权完成整件任务"}), 403
    data = request.get_json(silent=True) or {}
    action_id = (data.get("action_id") or "").strip()
    if not action_id:
        return jsonify({"ok": False, "error": "缺少 action_id"}), 400
    result = proxy_complete_all(
        get_db(), task_id, elder_id, user_id=session["user_id"], action_id=action_id
    )
    return jsonify(result)


@app.route("/api/tasks/<int:task_id>/reset", methods=["POST"])
@login_required
def api_tasks_reset(task_id: int):
    elder_id, role, err = _api_care_context()
    if err:
        return err
    if role != ROLE_FAMILY:
        return jsonify({"ok": False, "error": "仅家属可重置今日进度"}), 403
    data = request.get_json(silent=True) or {}
    action_id = (data.get("action_id") or "").strip()
    if not action_id:
        return jsonify({"ok": False, "error": "缺少 action_id"}), 400
    result = reset_today_run(get_db(), task_id, elder_id, action_id=action_id)
    return jsonify(result)


@app.route("/api/medication", methods=["GET", "POST"])
@login_required
def api_medication_collection():
    elder_id, role, err = _api_care_context()
    if err:
        return err
    db = get_db()
    is_family = role == ROLE_FAMILY

    if request.method == "GET":
        active_only = (request.args.get("active") or "1") != "0"
        meds = list_medications(db, elder_id, active_only=active_only)
        return jsonify({"ok": True, "medications": [dict(m) for m in meds]})

    if not is_family:
        return jsonify({"ok": False, "error": "仅家属可新增用药"}), 403
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    dose = (data.get("dose") or "").strip()
    schedule_time = (data.get("schedule_time") or "").strip()
    if not name or not dose or not schedule_time:
        return jsonify({"ok": False, "error": "name、dose、schedule_time 必填"}), 400
    place = (data.get("place_area") or "").strip()
    if place and place not in PLACE_OPTIONS:
        place = ""
    med_id = add_medication(
        db,
        elder_id,
        name=name,
        dose=dose,
        schedule_time=schedule_time,
        note=(data.get("note") or "").strip(),
        alias=(data.get("alias") or "").strip(),
        place_area=place,
        catalog_id=(data.get("catalog_id") or None),
        created_by=session.get("user_id"),
    )
    return jsonify({"ok": True, "id": med_id}), 201


@app.route("/api/medication/today", methods=["GET"])
@login_required
def api_medication_today():
    elder_id, _role, err = _api_care_context()
    if err:
        return err
    summary = adherence_summary(get_db(), elder_id)
    return jsonify({"ok": True, **summary})


@app.route("/api/medication/today/pending", methods=["GET"])
@login_required
def api_medication_today_pending():
    elder_id, _role, err = _api_care_context()
    if err:
        return err
    plan = today_plan(get_db(), elder_id)
    pending = [p for p in plan if p.get("pending")]
    return jsonify({"ok": True, "pending_count": len(pending), "total": len(plan), "pending": pending})


@app.route("/api/medication/week", methods=["GET"])
@login_required
def api_medication_week():
    elder_id, _role, err = _api_care_context()
    if err:
        return err
    db = get_db()
    return jsonify(
        {
            "ok": True,
            "week_log": week_adherence(db, elder_id),
            "week_days": week_schedule(db, elder_id),
        }
    )


@app.route("/api/medication/<int:med_id>", methods=["GET", "PUT", "PATCH", "DELETE"])
@login_required
def api_medication_item(med_id: int):
    elder_id, role, err = _api_care_context()
    if err:
        return err
    db = get_db()
    is_family = role == ROLE_FAMILY
    row = db.execute(
        "SELECT * FROM medications WHERE id = ? AND elder_user_id = ?",
        (med_id, elder_id),
    ).fetchone()
    if not row:
        return jsonify({"ok": False, "error": "未找到该药物"}), 404

    if request.method == "GET":
        return jsonify({"ok": True, "medication": dict(row)})

    if request.method == "DELETE":
        if not is_family:
            return jsonify({"ok": False, "error": "仅家属可删除用药"}), 403
        ok = deactivate_medication(db, med_id, elder_id)
        return jsonify({"ok": ok})

    if not is_family:
        return jsonify({"ok": False, "error": "仅家属可修改用药"}), 403
    data = request.get_json(silent=True) or {}
    dose = (data.get("dose") or row["dose"] or "").strip()
    schedule_time = (data.get("schedule_time") or row["schedule_time"] or "").strip()
    alias = data.get("alias") if "alias" in data else (row["alias"] if "alias" in row.keys() else "")
    place = data.get("place_area") if "place_area" in data else (row["place_area"] if "place_area" in row.keys() else "")
    note = data.get("note") if "note" in data else row["note"]
    place = (place or "").strip()
    if place and place not in PLACE_OPTIONS:
        place = ""
    ok = update_medication(
        db,
        med_id,
        elder_id,
        dose=dose,
        schedule_time=schedule_time,
        alias=(alias or "").strip(),
        place_area=place,
        note=(note or "").strip(),
    )
    return jsonify({"ok": ok})


@app.route("/api/medication/<int:med_id>/status", methods=["POST"])
@login_required
def api_medication_status(med_id: int):
    elder_id, role, err = _api_care_context()
    if err:
        return err
    data = request.get_json(silent=True) or {}
    status = (data.get("status") or request.form.get("status") or "").strip()
    is_family = role == ROLE_FAMILY
    if status == STATUS_PROXY and not is_family:
        return jsonify({"ok": False, "error": "仅家属可代确认"}), 403
    if status == STATUS_SKIPPED and not is_family:
        return jsonify({"ok": False, "error": "仅家属可跳过"}), 403
    if status not in {STATUS_TAKEN, STATUS_PROXY, STATUS_SKIPPED}:
        return jsonify({"ok": False, "error": "status 须为 taken/proxy/skipped"}), 400
    ok = record_medication_status(
        get_db(), med_id, elder_id, status, recorded_by=session.get("user_id")
    )
    return jsonify({"ok": ok, "status": status})


@app.route("/api/assistant/chat", methods=["POST"])
@login_required
def api_assistant_chat():
    elder_id, role, err = _api_care_context()
    if err:
        return err
    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    history = data.get("history") if isinstance(data.get("history"), list) else []
    try:
        result = run_assistant_chat(
            get_db(),
            message=message,
            elder_user_id=elder_id,
            user_id=session["user_id"],
            role=role,
            elder_username=session.get("elder_username") or session.get("username") or "",
            history=history,
        )
        status = 200 if result.get("ok") else 400
        return jsonify(result), status
    except Exception as exc:  # noqa: BLE001
        return jsonify(
            {
                "ok": False,
                "reply": f"助手暂时不可用：{exc}",
                "disclaimer": "仅供照护参考，不能替代医嘱。",
            }
        ), 500


@app.route("/safety")
@login_required
def safety():
    devices = [
        {"name": "定位手环", "type": "band", "status": "在线", "battery": 78, "signal": "良好", "updated": "2 分钟前", "desc": "实时上报位置与活动状态"},
        {"name": "大门门磁", "type": "door", "status": "在线", "battery": 92, "signal": "良好", "updated": "5 分钟前", "desc": "监测入户门开闭状态"},
        {"name": "卧室活动传感器", "type": "motion", "status": "在线", "battery": 65, "signal": "一般", "updated": "1 分钟前", "desc": "检测夜间起床与长时间静止"},
        {"name": "客厅紧急按钮", "type": "sos", "status": "离线", "battery": 12, "signal": "无", "updated": "3 小时前", "desc": "一键呼叫家属，需更换电池"},
    ]
    alerts = [
        {"time": "07:42", "level": "info", "title": "正常起床活动", "desc": "卧室传感器检测到起床，活动状态正常。"},
        {"time": "11:15", "level": "warn", "title": "大门开启", "desc": "主门磁触发，患者短暂外出，已在 15 分钟内返回。"},
        {"time": "02:18", "level": "warn", "title": "夜间游走", "desc": "凌晨检测到客厅活动，建议关注睡眠与定向力变化。"},
    ]
    contacts = [
        {"name": "张女士", "relation": "女儿", "phone": "138****5621"},
        {"name": "李先生", "relation": "儿子", "phone": "139****8830"},
        {"name": "社区医生", "relation": "签约家庭医生", "phone": "010-****6688"},
    ]
    location = {"name": "居家 · 安全区域内", "address": "北京市朝阳区 ** 小区 3 号楼附近", "updated": "2 分钟前"}
    online_count = sum(1 for d in devices if d["status"] == "在线")
    return render_dashboard(
        "safety.html",
        "safety",
        devices=devices,
        alerts=alerts,
        contacts=contacts,
        location=location,
        online_count=online_count,
        alert_count=len(alerts),
    )


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))
    login_role = (request.form.get("role") or request.args.get("role") or ROLE_ELDER).strip()
    if login_role not in VALID_ROLES:
        login_role = ROLE_ELDER
    username = (request.form.get("username") or "").strip()
    if request.method == "POST":
        password = request.form.get("password") or ""
        error = (
            validate_role(login_role)
            or validate_username(username)
            or (None if password else "请输入密码。")
        )
        if error:
            flash(error, "error")
            return render_template("login.html", username=username, role=login_role)
        user = get_db().execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        if user is None or not check_password_hash(user["password_hash"], password):
            flash("用户名或密码错误。", "error")
            return render_template("login.html", username=username, role=login_role)
        user_role = user["role"] if "role" in user.keys() else ROLE_ELDER
        if user_role != login_role:
            expect = ROLE_LABELS[login_role]
            actual = ROLE_LABELS.get(user_role, "未知类型")
            flash(f"该账号是「{actual}」，请切换到对应入口登录。", "error")
            return render_template("login.html", username=username, role=login_role)
        elder = None
        if user_role == ROLE_FAMILY:
            elder = get_linked_elder(get_db(), user["id"])
            if elder is None:
                flash("家属账号未绑定老人，请重新注册并创建老人账号。", "error")
                return render_template("login.html", username=username, role=login_role)
        establish_session(user, elder)
        label = ROLE_LABELS[user_role]
        if elder:
            flash(f"欢迎回来，{user['username']}（{label} · 照护 {elder['username']}）。", "success")
        else:
            flash(f"欢迎回来，{user['username']}（{label}）。", "success")
        next_url = request.args.get("next")
        if next_url and next_url.startswith("/"):
            return redirect(next_url)
        return redirect(url_for("dashboard"))
    return render_template("login.html", username=username, role=login_role)


@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))
    role = (request.form.get("role") or request.args.get("role") or ROLE_FAMILY).strip()
    if role not in VALID_ROLES:
        role = ROLE_FAMILY
    form = {
        "role": role,
        "username": (request.form.get("username") or "").strip(),
        "email": (request.form.get("email") or "").strip(),
        "elder_username": (request.form.get("elder_username") or "").strip(),
        "relation": (request.form.get("relation") or "家属").strip() or "家属",
        "family_username": (request.form.get("family_username") or "").strip(),
        "family_email": (request.form.get("family_email") or "").strip(),
        "family_relation": (request.form.get("family_relation") or "家属").strip() or "家属",
    }
    if request.method == "POST":
        password = request.form.get("password") or ""
        confirm = request.form.get("confirm_password") or ""
        error = (
            validate_role(role)
            or validate_username(form["username"])
            or validate_email(form["email"])
            or validate_password(password, confirm)
        )
        elder_password = request.form.get("elder_password") or ""
        elder_confirm = request.form.get("elder_confirm_password") or ""
        family_password = request.form.get("family_password") or ""
        family_confirm = request.form.get("family_confirm_password") or ""
        if role == ROLE_FAMILY and not error:
            error = validate_username(form["elder_username"])
            if not error and form["elder_username"].casefold() == form["username"].casefold():
                error = "老人用户名不能与家属用户名相同。"
            if not error:
                error = validate_password(elder_password, elder_confirm)
        if role == ROLE_ELDER and not error:
            error = validate_username(form["family_username"])
            if not error:
                error = validate_email(form["family_email"])
            if not error and form["family_username"].casefold() == form["username"].casefold():
                error = "家属用户名不能与老人用户名相同。"
            if not error and form["family_email"].casefold() == form["email"].casefold():
                error = "家属邮箱不能与老人邮箱相同。"
            if not error:
                error = validate_password(family_password, family_confirm)
        if error:
            flash(error, "error")
            return render_template("register.html", **form)

        db = get_db()
        exists = db.execute(
            "SELECT id FROM users WHERE username = ? OR email = ?",
            (form["username"], form["email"]),
        ).fetchone()
        if exists:
            flash("用户名或邮箱已被注册。", "error")
            return render_template("register.html", **form)

        if role == ROLE_ELDER:
            family_clash = db.execute(
                "SELECT id FROM users WHERE username = ? OR email = ?",
                (form["family_username"], form["family_email"]),
            ).fetchone()
            if family_clash:
                flash("家属用户名或邮箱已被占用，请更换后重试。", "error")
                return render_template("register.html", **form)
            try:
                cur = db.execute(
                    "INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, ?)",
                    (
                        form["username"],
                        form["email"],
                        generate_password_hash(password),
                        ROLE_ELDER,
                    ),
                )
                elder_id = cur.lastrowid
                cur = db.execute(
                    "INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, ?)",
                    (
                        form["family_username"],
                        form["family_email"],
                        generate_password_hash(family_password),
                        ROLE_FAMILY,
                    ),
                )
                family_id = cur.lastrowid
                create_family_link(db, family_id, elder_id, form["family_relation"])
                db.commit()
            except sqlite3.IntegrityError:
                db.rollback()
                flash("注册失败，用户名或邮箱可能已被占用。", "error")
                return render_template("register.html", **form)
            flash(
                f"注册成功：老人「{form['username']}」已绑定家属「{form['family_username']}」。"
                "请用老人账号登录，家属可用其账号登录。",
                "success",
            )
            return redirect(url_for("login", role=ROLE_ELDER))

        elder_exists = db.execute(
            "SELECT id FROM users WHERE username = ?",
            (form["elder_username"],),
        ).fetchone()
        if elder_exists:
            flash("老人用户名已被占用，请更换后重试。", "error")
            return render_template("register.html", **form)

        elder_email = elder_local_email(form["elder_username"])
        email_clash = db.execute("SELECT id FROM users WHERE email = ?", (elder_email,)).fetchone()
        if email_clash:
            flash("无法创建老人账号（邮箱冲突），请更换老人用户名。", "error")
            return render_template("register.html", **form)

        try:
            cur = db.execute(
                "INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, ?)",
                (
                    form["elder_username"],
                    elder_email,
                    generate_password_hash(elder_password),
                    ROLE_ELDER,
                ),
            )
            elder_id = cur.lastrowid
            cur = db.execute(
                "INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, ?)",
                (
                    form["username"],
                    form["email"],
                    generate_password_hash(password),
                    ROLE_FAMILY,
                ),
            )
            family_id = cur.lastrowid
            create_family_link(db, family_id, elder_id, form["relation"])
            db.commit()
        except sqlite3.IntegrityError:
            db.rollback()
            flash("注册失败，用户名或邮箱可能已被占用。", "error")
            return render_template("register.html", **form)

        flash(
            f"注册成功：家属「{form['username']}」已绑定老人「{form['elder_username']}」。请用家属账号登录。",
            "success",
        )
        return redirect(url_for("login", role=ROLE_FAMILY))

    return render_template(
        "register.html",
        role=role,
        username="",
        email="",
        elder_username="",
        relation="家属",
        family_username="",
        family_email="",
        family_relation="家属",
    )


@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))
    role = (request.form.get("role") or request.args.get("role") or ROLE_ELDER).strip()
    if role not in VALID_ROLES:
        role = ROLE_ELDER
    form = {
        "username": (request.form.get("username") or "").strip(),
        "email": (request.form.get("email") or "").strip(),
        "role": role,
        "verified": False,
    }
    if request.method == "POST":
        action = request.form.get("action") or "verify"
        password = request.form.get("password") or ""
        confirm = request.form.get("confirm_password") or ""
        error = validate_role(role) or validate_username(form["username"]) or validate_email(form["email"])
        if error:
            flash(error, "error")
            return render_template("forgot_password.html", **form)
        db = get_db()
        user = db.execute(
            "SELECT * FROM users WHERE username = ? AND email = ?",
            (form["username"], form["email"]),
        ).fetchone()
        if user is None:
            flash("用户名与邮箱不匹配，请核对后重试。", "error")
            return render_template("forgot_password.html", **form)
        user_role = user["role"] if "role" in user.keys() else ROLE_ELDER
        if user_role != role:
            flash(
                f"该账号实际是「{ROLE_LABELS.get(user_role, '未知')}」，请切换上方账号类型后再试。",
                "error",
            )
            return render_template("forgot_password.html", **form)
        if action == "verify":
            form["verified"] = True
            flash("校验通过，请设置新密码。", "success")
            return render_template("forgot_password.html", **form)
        error = validate_password(password, confirm)
        if error:
            form["verified"] = True
            flash(error, "error")
            return render_template("forgot_password.html", **form)
        db.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (generate_password_hash(password), user["id"]),
        )
        db.commit()
        flash("密码已重置，请使用新密码登录。", "success")
        return redirect(url_for("login", role=role))
    return render_template("forgot_password.html", **form)


@app.route("/logout", methods=["POST"])
@login_required
def logout():
    session.clear()
    flash("您已安全退出。", "success")
    return redirect(url_for("landing"))


if __name__ == "__main__":
    with app.app_context():
        init_db()
    # 强制关闭调试重载，避免局域网访问异常；需要调试时设 FLASK_DEBUG=1 且本机访问
    use_debug = DEBUG and HOST in {"127.0.0.1", "localhost"}
    if use_debug:
        app.run(debug=True, host=HOST, port=PORT)
    else:
        from waitress import serve

        print(f"记忆港湾已启动 · http://{HOST}:{PORT}（Waitress）")
        serve(app, host=HOST, port=PORT, threads=THREADS)
