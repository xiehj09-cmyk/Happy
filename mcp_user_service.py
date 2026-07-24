"""按用户 Token / 小智 UserId 区分记忆归属"""

from __future__ import annotations

import secrets
import sqlite3
from typing import Any

from user_auth import ROLE_ELDER, ROLE_FAMILY, get_linked_elder
from werkzeug.security import generate_password_hash


def ensure_mcp_user_schema(db: sqlite3.Connection) -> None:
    cols = {row[1] for row in db.execute("PRAGMA table_info(users)").fetchall()}
    if "mcp_token" not in cols:
        db.execute("ALTER TABLE users ADD COLUMN mcp_token TEXT")
    db.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_users_mcp_token
        ON users(mcp_token)
        WHERE mcp_token IS NOT NULL AND mcp_token != ''
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS xiaozhi_user_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            xiaozhi_user_id TEXT NOT NULL UNIQUE,
            xiaozhi_agent_id TEXT,
            elder_user_id INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            last_seen_at TEXT,
            FOREIGN KEY (elder_user_id) REFERENCES users(id)
        )
        """
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_xiaozhi_links_elder ON xiaozhi_user_links(elder_user_id)"
    )
    db.commit()
    # 为尚无 Token 的老人账号补发
    rows = db.execute(
        "SELECT id FROM users WHERE role = ? AND (mcp_token IS NULL OR mcp_token = '')",
        (ROLE_ELDER,),
    ).fetchall()
    for row in rows:
        ensure_user_mcp_token(db, int(row["id"]))


def new_mcp_token() -> str:
    return "mh_" + secrets.token_urlsafe(24)


def ensure_user_mcp_token(db: sqlite3.Connection, user_id: int) -> str:
    row = db.execute("SELECT mcp_token, role FROM users WHERE id = ?", (user_id,)).fetchone()
    if not row:
        raise ValueError("用户不存在")
    token = (row["mcp_token"] or "").strip()
    if token:
        return token
    # 家属：记忆归属绑定老人，Token 仍挂在家属账号上便于配置，解析时转到老人
    for _ in range(5):
        token = new_mcp_token()
        try:
            db.execute("UPDATE users SET mcp_token = ? WHERE id = ?", (token, user_id))
            db.commit()
            return token
        except sqlite3.IntegrityError:
            continue
    raise RuntimeError("无法生成唯一 MCP Token")


def rotate_user_mcp_token(db: sqlite3.Connection, user_id: int) -> str:
    for _ in range(5):
        token = new_mcp_token()
        try:
            db.execute("UPDATE users SET mcp_token = ? WHERE id = ?", (token, user_id))
            db.commit()
            return token
        except sqlite3.IntegrityError:
            continue
    raise RuntimeError("无法刷新 MCP Token")


def elder_id_for_account(db: sqlite3.Connection, user_row: sqlite3.Row) -> int | None:
    role = user_row["role"] if "role" in user_row.keys() else ROLE_ELDER
    if role == ROLE_FAMILY:
        elder = get_linked_elder(db, int(user_row["id"]))
        return int(elder["id"]) if elder else None
    if role == ROLE_ELDER:
        return int(user_row["id"])
    return None


def find_user_by_mcp_token(db: sqlite3.Connection, token: str) -> sqlite3.Row | None:
    if not token:
        return None
    return db.execute(
        "SELECT id, username, email, role, mcp_token, created_at FROM users WHERE mcp_token = ?",
        (token,),
    ).fetchone()


def get_link_by_xiaozhi_user(
    db: sqlite3.Connection, xiaozhi_user_id: str
) -> dict[str, Any] | None:
    row = db.execute(
        "SELECT * FROM xiaozhi_user_links WHERE xiaozhi_user_id = ?",
        (str(xiaozhi_user_id),),
    ).fetchone()
    return dict(row) if row else None


def touch_xiaozhi_link(
    db: sqlite3.Connection,
    xiaozhi_user_id: str,
    *,
    agent_id: str | None = None,
) -> None:
    db.execute(
        """
        UPDATE xiaozhi_user_links
        SET last_seen_at = datetime('now', 'localtime'),
            xiaozhi_agent_id = COALESCE(?, xiaozhi_agent_id)
        WHERE xiaozhi_user_id = ?
        """,
        (agent_id, str(xiaozhi_user_id)),
    )
    db.commit()


def bind_xiaozhi_user(
    db: sqlite3.Connection,
    elder_user_id: int,
    xiaozhi_user_id: str,
    *,
    agent_id: str | None = None,
) -> dict[str, Any]:
    xid = str(xiaozhi_user_id).strip()
    if not xid:
        raise ValueError("小智用户 Id 不能为空")
    existing = get_link_by_xiaozhi_user(db, xid)
    if existing and int(existing["elder_user_id"]) != int(elder_user_id):
        raise ValueError("该小智账号已绑定其他记忆港湾用户")
    if existing:
        touch_xiaozhi_link(db, xid, agent_id=agent_id)
        return get_link_by_xiaozhi_user(db, xid)  # type: ignore[return-value]
    db.execute(
        """
        INSERT INTO xiaozhi_user_links (xiaozhi_user_id, xiaozhi_agent_id, elder_user_id, last_seen_at)
        VALUES (?, ?, ?, datetime('now', 'localtime'))
        """,
        (xid, agent_id, elder_user_id),
    )
    db.commit()
    return get_link_by_xiaozhi_user(db, xid)  # type: ignore[return-value]


def unbind_xiaozhi_user(db: sqlite3.Connection, elder_user_id: int, xiaozhi_user_id: str) -> bool:
    cur = db.execute(
        """
        DELETE FROM xiaozhi_user_links
        WHERE elder_user_id = ? AND xiaozhi_user_id = ?
        """,
        (elder_user_id, str(xiaozhi_user_id).strip()),
    )
    db.commit()
    return cur.rowcount > 0


def list_xiaozhi_links_for_elder(db: sqlite3.Connection, elder_user_id: int) -> list[dict[str, Any]]:
    rows = db.execute(
        """
        SELECT * FROM xiaozhi_user_links
        WHERE elder_user_id = ?
        ORDER BY id DESC
        """,
        (elder_user_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def provision_elder_for_xiaozhi(
    db: sqlite3.Connection,
    xiaozhi_user_id: str,
    *,
    agent_id: str | None = None,
) -> int:
    """首次使用：按小智 UserId 自动创建老人账号并建立绑定。"""
    xid = str(xiaozhi_user_id).strip()
    link = get_link_by_xiaozhi_user(db, xid)
    if link:
        touch_xiaozhi_link(db, xid, agent_id=agent_id)
        return int(link["elder_user_id"])

    base = f"xz{xid}"
    username = base
    n = 1
    while db.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone():
        n += 1
        username = f"{base}_{n}"

    email = f"xiaozhi.{xid}@memory-harbor.local"
    while db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone():
        email = f"xiaozhi.{xid}.{n}@memory-harbor.local"
        n += 1

    token = new_mcp_token()
    pwd = secrets.token_urlsafe(18)
    cur = db.execute(
        """
        INSERT INTO users (username, email, password_hash, role, mcp_token)
        VALUES (?, ?, ?, ?, ?)
        """,
        (username, email, generate_password_hash(pwd), ROLE_ELDER, token),
    )
    elder_id = int(cur.lastrowid)
    db.execute(
        """
        INSERT INTO xiaozhi_user_links (xiaozhi_user_id, xiaozhi_agent_id, elder_user_id, last_seen_at)
        VALUES (?, ?, ?, datetime('now', 'localtime'))
        """,
        (xid, agent_id, elder_id),
    )
    db.commit()
    return elder_id


def resolve_configured_elder_id(
    db: sqlite3.Connection,
    *,
    username: str = "",
    user_id: int = 0,
) -> int:
    """按环境变量解析默认老人账号：优先 username，其次数字 id。"""
    name = (username or "").strip()
    if name:
        row = db.execute(
            "SELECT id, username, role FROM users WHERE username = ?",
            (name,),
        ).fetchone()
        if row:
            elder_id = elder_id_for_account(db, row)
            if elder_id:
                return int(elder_id)
    if user_id:
        row = db.execute(
            "SELECT id, username, role FROM users WHERE id = ?",
            (int(user_id),),
        ).fetchone()
        if row:
            elder_id = elder_id_for_account(db, row)
            if elder_id:
                return int(elder_id)
    return 0


def force_bind_xiaozhi_to_elder(
    db: sqlite3.Connection,
    elder_user_id: int,
    xiaozhi_user_id: str,
    *,
    agent_id: str | None = None,
) -> None:
    """将小智 UserId 强制绑定到指定老人（覆盖旧绑定）。"""
    xid = str(xiaozhi_user_id).strip()
    if not xid or not elder_user_id:
        return
    existing = get_link_by_xiaozhi_user(db, xid)
    if existing and int(existing["elder_user_id"]) == int(elder_user_id):
        touch_xiaozhi_link(db, xid, agent_id=agent_id)
        return
    if existing:
        db.execute(
            """
            UPDATE xiaozhi_user_links
            SET elder_user_id = ?, xiaozhi_agent_id = COALESCE(?, xiaozhi_agent_id),
                last_seen_at = datetime('now', 'localtime')
            WHERE xiaozhi_user_id = ?
            """,
            (int(elder_user_id), agent_id, xid),
        )
        db.commit()
        return
    bind_xiaozhi_user(db, int(elder_user_id), xid, agent_id=agent_id)


def resolve_mcp_identity(
    db: sqlite3.Connection,
    bearer_token: str,
    *,
    global_token: str,
    xiaozhi_user_id: str | None = None,
    xiaozhi_agent_id: str | None = None,
    fallback_elder_id: int = 0,
    allow_auto_provision: bool = True,
) -> dict[str, Any] | None:
    """
    解析 MCP 请求归属的老人账号。
    优先级：
    1) 个人 mcp_token → 对应用户（家属转绑定老人）
    2) 全局 Token + 环境变量默认老人（MCP_ELDER_USERNAME / MCP_ELDER_USER_ID）→ 全部归该账号
    3) 全局 Token + 小智 UserId → 已手动绑定的账号
    4) 未绑定 → 返回 need_bind / need_xiaozhi_id（不自动建档）
    """
    token = (bearer_token or "").strip()
    if not token:
        return None

    user = find_user_by_mcp_token(db, token)
    if user:
        elder_id = elder_id_for_account(db, user)
        if not elder_id:
            return None
        # 个人 Token：只认账号归属，不自动绑定小智（绑定请在网站手动操作）
        return {
            "elder_user_id": elder_id,
            "auth": "user_token",
            "account_user_id": int(user["id"]),
            "xiaozhi_user_id": str(xiaozhi_user_id) if xiaozhi_user_id else None,
        }

    if global_token and token == global_token:
        # 环境变量强制默认账号：所有小智请求都落到该老人
        if fallback_elder_id:
            row = db.execute(
                "SELECT id FROM users WHERE id = ?",
                (int(fallback_elder_id),),
            ).fetchone()
            if row:
                if xiaozhi_user_id:
                    force_bind_xiaozhi_to_elder(
                        db,
                        int(fallback_elder_id),
                        str(xiaozhi_user_id),
                        agent_id=xiaozhi_agent_id,
                    )
                return {
                    "elder_user_id": int(fallback_elder_id),
                    "auth": "env_default",
                    "xiaozhi_user_id": str(xiaozhi_user_id) if xiaozhi_user_id else None,
                }

        if not xiaozhi_user_id:
            return {
                "error": "need_xiaozhi_id",
                "message": "共用桥接需携带小智 UserId，并先在网站工作台手动绑定；或设置 MCP_ELDER_USERNAME",
            }
        link = get_link_by_xiaozhi_user(db, str(xiaozhi_user_id))
        if link:
            touch_xiaozhi_link(db, str(xiaozhi_user_id), agent_id=xiaozhi_agent_id)
            return {
                "elder_user_id": int(link["elder_user_id"]),
                "auth": "xiaozhi_link",
                "xiaozhi_user_id": str(xiaozhi_user_id),
            }
        if allow_auto_provision:
            elder_id = provision_elder_for_xiaozhi(
                db, str(xiaozhi_user_id), agent_id=xiaozhi_agent_id
            )
            return {
                "elder_user_id": elder_id,
                "auth": "xiaozhi_provision",
                "xiaozhi_user_id": str(xiaozhi_user_id),
                "first_use": True,
            }
        return {
            "error": "need_bind",
            "message": f"小智用户 {xiaozhi_user_id} 尚未绑定，请在网站工作台手动绑定后再使用",
            "xiaozhi_user_id": str(xiaozhi_user_id),
        }

    return None
