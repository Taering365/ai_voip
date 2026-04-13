"""系统配置服务。"""

from __future__ import annotations

from psycopg import Connection


def get_database_status(connection: Connection) -> tuple[str, str]:
    """读取数据库名称与版本信息。

    Args:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。

    Returns:
        tuple[str, str]: 返回数据库名称和 PostgreSQL 版本字符串。
    """

    with connection.cursor() as cursor:
        cursor.execute("SELECT current_database(), version()")
        database_name, version_text = cursor.fetchone()
    return database_name, version_text


def list_system_configs(connection: Connection) -> list[dict]:
    """查询系统配置列表。

    Args:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。

    Returns:
        list[dict]: 返回包含配置键、配置值和说明的字典列表。
    """

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT config_key, config_value, description
            FROM sys_config
            WHERE deleted_at IS NULL
            ORDER BY config_key
            """
        )
        rows = cursor.fetchall()
    return [
        {
            "config_key": row[0],
            "config_value": row[1],
            "description": row[2],
        }
        for row in rows
    ]
