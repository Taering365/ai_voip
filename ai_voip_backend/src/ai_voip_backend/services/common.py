"""通用数据库服务辅助函数。"""

from __future__ import annotations

from psycopg import Connection
from psycopg.types.json import Jsonb


def jsonb_value(value: object) -> Jsonb:
    """将 Python 对象包装为 psycopg 可识别的 JSONB 参数。

    Args:
        value: 需要写入 PostgreSQL JSONB 字段的 Python 对象。

    Returns:
        Jsonb: 返回可直接用于 SQL 参数绑定的 Jsonb 包装对象。
    """

    return Jsonb(value)


def soft_delete_by_id(connection: Connection, table_name: str, record_id: int) -> bool:
    """按主键对指定表执行软删除。

    Args:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        table_name: 需要执行软删除的表名。
        record_id: 需要删除的记录主键。

    Returns:
        bool: 成功更新到记录时返回 True，否则返回 False。
    """

    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            UPDATE {table_name}
            SET deleted_at = NOW(),
                updated_at = NOW()
            WHERE id = %(record_id)s
              AND deleted_at IS NULL
            """,
            {"record_id": record_id},
        )
        deleted = cursor.rowcount > 0
    connection.commit()
    return deleted
