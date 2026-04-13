"""用户与用户线路分配服务。"""

from __future__ import annotations

from psycopg import Connection

from ..security import hash_password
from .trunk_service import get_trunk_by_id


def list_users(connection: Connection) -> list[dict]:
    """查询系统用户列表。

    Args:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。

    Returns:
        list[dict]: 返回用户详情字典列表。
    """

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                u.id,
                u.username,
                u.display_name,
                u.mobile,
                u.email,
                u.status,
                COALESCE(array_remove(array_agg(r.role_code), NULL), ARRAY[]::varchar[]) AS role_codes,
                u.created_at,
                u.updated_at
            FROM sys_user u
            LEFT JOIN sys_user_role ur
              ON ur.user_id = u.id
             AND ur.deleted_at IS NULL
            LEFT JOIN sys_role r
              ON r.id = ur.role_id
             AND r.deleted_at IS NULL
            WHERE u.deleted_at IS NULL
            GROUP BY u.id
            ORDER BY u.id DESC
            """
        )
        rows = cursor.fetchall()
    return [_build_user_item(row) for row in rows]


def get_user_by_id_with_roles(connection: Connection, user_id: int) -> dict | None:
    """根据主键查询用户详情及其角色。

    Args:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        user_id: 需要查询的用户主键。

    Returns:
        dict | None: 查询成功时返回用户详情字典，否则返回 None。
    """

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                u.id,
                u.username,
                u.display_name,
                u.mobile,
                u.email,
                u.status,
                COALESCE(array_remove(array_agg(r.role_code), NULL), ARRAY[]::varchar[]) AS role_codes,
                u.created_at,
                u.updated_at
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
    return _build_user_item(row) if row else None


def create_user(
    connection: Connection,
    username: str,
    password: str,
    display_name: str,
    mobile: str | None,
    email: str | None,
    status: str,
    role_codes: list[str],
) -> dict:
    """创建新用户并绑定角色。

    Args:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        username: 用户登录名。
        password: 用户密码明文。
        display_name: 用户显示名称。
        mobile: 用户手机号。
        email: 用户邮箱。
        status: 用户状态。
        role_codes: 用户角色编码列表。

    Returns:
        dict: 返回创建完成后的用户详情字典。
    """

    password_hash = hash_password(password)
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO sys_user (
                username, password_hash, display_name, mobile, email, status
            ) VALUES (
                %(username)s, %(password_hash)s, %(display_name)s, %(mobile)s, %(email)s, %(status)s
            )
            RETURNING id
            """,
            {
                "username": username,
                "password_hash": password_hash,
                "display_name": display_name,
                "mobile": mobile,
                "email": email,
                "status": status,
            },
        )
        user_id = cursor.fetchone()[0]
        _replace_user_roles(cursor, user_id, role_codes)
    connection.commit()
    return get_user_by_id_with_roles(connection, user_id)  # type: ignore[return-value]


def update_user(
    connection: Connection,
    user_id: int,
    display_name: str,
    mobile: str | None,
    email: str | None,
    status: str,
    role_codes: list[str],
    password: str | None = None,
) -> dict | None:
    """更新指定用户信息与角色。

    Args:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        user_id: 需要更新的用户主键。
        display_name: 用户显示名称。
        mobile: 用户手机号。
        email: 用户邮箱。
        status: 用户状态。
        role_codes: 用户角色编码列表。
        password: 可选的新密码明文。

    Returns:
        dict | None: 更新成功时返回用户详情字典，不存在时返回 None。
    """

    update_sql = """
        UPDATE sys_user
        SET display_name = %(display_name)s,
            mobile = %(mobile)s,
            email = %(email)s,
            status = %(status)s,
            updated_at = NOW()
    """
    params: dict[str, object] = {
        "display_name": display_name,
        "mobile": mobile,
        "email": email,
        "status": status,
        "user_id": user_id,
    }
    if password:
        update_sql += ", password_hash = %(password_hash)s"
        params["password_hash"] = hash_password(password)
    update_sql += " WHERE id = %(user_id)s AND deleted_at IS NULL"

    with connection.cursor() as cursor:
        cursor.execute(update_sql, params)
        if cursor.rowcount == 0:
            connection.rollback()
            return None
        _replace_user_roles(cursor, user_id, role_codes)
    connection.commit()
    return get_user_by_id_with_roles(connection, user_id)


def list_user_trunk_assignments(connection: Connection, user_id: int) -> list[dict]:
    """查询指定用户当前已分配的线路列表。

    Args:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        user_id: 用户主键。

    Returns:
        list[dict]: 返回已分配线路详情列表。
    """

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT trunk_id
            FROM user_trunk_assignment
            WHERE user_id = %(user_id)s
              AND deleted_at IS NULL
            ORDER BY trunk_id ASC
            """,
            {"user_id": user_id},
        )
        trunk_ids = [row[0] for row in cursor.fetchall()]

    return [trunk for trunk_id in trunk_ids if (trunk := get_trunk_by_id(connection, trunk_id)) is not None]


def replace_user_trunk_assignments(connection: Connection, user_id: int, trunk_ids: list[int]) -> list[dict]:
    """重置指定用户的线路分配关系。

    Args:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        user_id: 用户主键。
        trunk_ids: 需要分配给用户的线路主键列表。

    Returns:
        list[dict]: 返回重置完成后的线路详情列表。
    """

    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE user_trunk_assignment
            SET deleted_at = NOW(),
                updated_at = NOW()
            WHERE user_id = %(user_id)s
              AND deleted_at IS NULL
            """,
            {"user_id": user_id},
        )
        for trunk_id in trunk_ids:
            cursor.execute(
                """
                INSERT INTO user_trunk_assignment (user_id, trunk_id)
                VALUES (%(user_id)s, %(trunk_id)s)
                """,
                {"user_id": user_id, "trunk_id": trunk_id},
            )
    connection.commit()
    return list_user_trunk_assignments(connection, user_id)


def _replace_user_roles(cursor, user_id: int, role_codes: list[str]) -> None:
    """替换指定用户当前绑定的角色集合。

    Args:
        cursor: 当前事务使用的数据库游标对象。
        user_id: 用户主键。
        role_codes: 需要重新绑定的角色编码列表。
    """

    cursor.execute(
        """
        UPDATE sys_user_role
        SET deleted_at = NOW(),
            updated_at = NOW()
        WHERE user_id = %(user_id)s
          AND deleted_at IS NULL
        """,
        {"user_id": user_id},
    )
    if not role_codes:
        role_codes = ["agent_user"]
    cursor.execute(
        """
        SELECT id, role_code
        FROM sys_role
        WHERE role_code = ANY(%(role_codes)s)
          AND deleted_at IS NULL
        """,
        {"role_codes": role_codes},
    )
    role_rows = cursor.fetchall()
    for role_row in role_rows:
        cursor.execute(
            """
            INSERT INTO sys_user_role (user_id, role_id)
            VALUES (%(user_id)s, %(role_id)s)
            """,
            {"user_id": user_id, "role_id": role_row[0]},
        )


def _build_user_item(row: tuple) -> dict:
    """将用户查询结果行转换为响应字典。

    Args:
        row: PostgreSQL 查询返回的单行元组对象。

    Returns:
        dict: 返回转换完成的用户详情字典。
    """

    return {
        "id": row[0],
        "username": row[1],
        "display_name": row[2],
        "mobile": row[3],
        "email": row[4],
        "status": row[5],
        "role_codes": list(row[6]),
        "created_at": row[7].isoformat(),
        "updated_at": row[8].isoformat(),
    }
