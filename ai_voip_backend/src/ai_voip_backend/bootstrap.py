"""系统初始化相关工具。"""

from __future__ import annotations

from contextlib import closing

from .config import PostgresConfig
from .db import connect_db
from .security import hash_password


def bootstrap_admin_user(
    config: PostgresConfig,
    username: str,
    password: str,
    display_name: str,
) -> None:
    """创建或更新超级管理员账号。

    Args:
        config: PostgreSQL 连接配置对象。
        username: 超级管理员登录用户名。
        password: 超级管理员登录密码明文。
        display_name: 超级管理员显示名称。
    """

    password_hash = hash_password(password)
    with closing(connect_db(config)) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO sys_user (
                    username,
                    password_hash,
                    display_name,
                    status
                ) VALUES (
                    %(username)s,
                    %(password_hash)s,
                    %(display_name)s,
                    'active'
                )
                ON CONFLICT (username) DO UPDATE SET
                    password_hash = EXCLUDED.password_hash,
                    display_name = EXCLUDED.display_name,
                    status = 'active',
                    updated_at = NOW()
                RETURNING id
                """,
                {
                    "username": username,
                    "password_hash": password_hash,
                    "display_name": display_name,
                },
            )
            user_id = cursor.fetchone()[0]

            cursor.execute(
                """
                SELECT id
                FROM sys_role
                WHERE role_code = 'super_admin'
                LIMIT 1
                """
            )
            role_row = cursor.fetchone()
            if role_row is None:
                raise RuntimeError("未找到 super_admin 角色，请先执行初始化 SQL。")

            role_id = role_row[0]
            cursor.execute(
                """
                INSERT INTO sys_user_role (user_id, role_id)
                VALUES (%(user_id)s, %(role_id)s)
                ON CONFLICT (user_id, role_id) DO NOTHING
                """,
                {"user_id": user_id, "role_id": role_id},
            )
        connection.commit()
