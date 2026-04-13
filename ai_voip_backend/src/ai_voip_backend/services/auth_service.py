"""登录鉴权服务。"""

from __future__ import annotations

from psycopg import Connection

from ..security import verify_password


def authenticate_user(connection: Connection, username: str, password: str) -> dict | None:
    """校验用户名和密码，并返回用户信息。

    Args:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        username: 登录用户名。
        password: 登录密码明文。

    Returns:
        dict | None: 登录成功时返回用户信息字典，否则返回 None。
    """

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                u.id,
                u.username,
                u.password_hash,
                u.display_name,
                u.status,
                COALESCE(array_remove(array_agg(r.role_code), NULL), ARRAY[]::varchar[]) AS role_codes
            FROM sys_user u
            LEFT JOIN sys_user_role ur
              ON ur.user_id = u.id
             AND ur.deleted_at IS NULL
            LEFT JOIN sys_role r
              ON r.id = ur.role_id
             AND r.deleted_at IS NULL
            WHERE u.deleted_at IS NULL
              AND u.username = %(username)s
            GROUP BY u.id
            LIMIT 1
            """,
            {"username": username},
        )
        row = cursor.fetchone()

    if row is None:
        return None
    if row[4] != "active":
        return None
    if not verify_password(password, row[2]):
        return None

    return {
        "id": row[0],
        "username": row[1],
        "display_name": row[3],
        "status": row[4],
        "role_codes": list(row[5]),
    }


def get_user_by_id(connection: Connection, user_id: int) -> dict | None:
    """根据用户主键查询当前用户信息。

    Args:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        user_id: 当前登录用户主键。

    Returns:
        dict | None: 找到用户时返回用户信息字典，否则返回 None。
    """

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                u.id,
                u.username,
                u.display_name,
                u.status,
                COALESCE(array_remove(array_agg(r.role_code), NULL), ARRAY[]::varchar[]) AS role_codes
            FROM sys_user u
            LEFT JOIN sys_user_role ur
              ON ur.user_id = u.id
             AND ur.deleted_at IS NULL
            LEFT JOIN sys_role r
              ON r.id = ur.role_id
             AND r.deleted_at IS NULL
            WHERE u.deleted_at IS NULL
              AND u.id = %(user_id)s
            GROUP BY u.id
            LIMIT 1
            """,
            {"user_id": user_id},
        )
        row = cursor.fetchone()

    if row is None:
        return None

    return {
        "id": row[0],
        "username": row[1],
        "display_name": row[2],
        "status": row[3],
        "role_codes": list(row[4]),
    }
