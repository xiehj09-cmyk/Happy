"""用户角色与家属–老人绑定"""

from __future__ import annotations

import sqlite3

ROLE_ELDER = "elder"
ROLE_FAMILY = "family"
VALID_ROLES = {ROLE_ELDER, ROLE_FAMILY}

ROLE_LABELS = {
    ROLE_ELDER: "老人账号",
    ROLE_FAMILY: "家属账号",
}


def ensure_user_auth_schema(db: sqlite3.Connection) -> None:
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE COLLATE NOCASE,
            email TEXT NOT NULL UNIQUE COLLATE NOCASE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'elder',
            created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
        )
        """
    )
    cols = {row[1] for row in db.execute("PRAGMA table_info(users)").fetchall()}
    if "role" not in cols:
        db.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'elder'")
        db.execute("UPDATE users SET role = 'elder' WHERE role IS NULL OR role = ''")

    db.execute(
        """
        CREATE TABLE IF NOT EXISTS family_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            family_user_id INTEGER NOT NULL UNIQUE,
            elder_user_id INTEGER NOT NULL,
            relation TEXT NOT NULL DEFAULT '家属',
            created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (family_user_id) REFERENCES users(id),
            FOREIGN KEY (elder_user_id) REFERENCES users(id)
        )
        """
    )
    db.commit()


def get_linked_elder(db: sqlite3.Connection, family_user_id: int):
    return db.execute(
        """
        SELECT u.id, u.username, u.email, u.role, u.created_at, fl.relation
        FROM family_links fl
        JOIN users u ON u.id = fl.elder_user_id
        WHERE fl.family_user_id = ?
        """,
        (family_user_id,),
    ).fetchone()


def create_family_link(
    db: sqlite3.Connection,
    family_user_id: int,
    elder_user_id: int,
    relation: str = "家属",
) -> None:
    db.execute(
        """
        INSERT INTO family_links (family_user_id, elder_user_id, relation)
        VALUES (?, ?, ?)
        """,
        (family_user_id, elder_user_id, relation or "家属"),
    )


def elder_local_email(username: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in username.strip())
    return f"elder.{safe}@memory-harbor.local"
