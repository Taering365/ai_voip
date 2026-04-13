"""数据库连接与初始化工具。"""

from __future__ import annotations

from contextlib import closing

import psycopg
from psycopg import Connection

from .config import PostgresConfig


def mask_secret(value: str) -> str:
    """对敏感字符串做掩码展示。

    Args:
        value: 原始敏感字符串内容。

    Returns:
        str: 返回脱敏后的字符串，便于日志和调试输出。
    """

    if len(value) <= 2:
        return "*" * len(value)
    return value[0] + "*" * (len(value) - 2) + value[-1]


def build_dsn(config: PostgresConfig) -> str:
    """根据 PostgreSQL 配置生成 DSN 字符串。

    Args:
        config: PostgreSQL 连接配置对象。

    Returns:
        str: 返回 psycopg 可直接使用的 DSN 字符串。
    """

    return (
        f"host={config.host} "
        f"port={config.port} "
        f"user={config.user} "
        f"password={config.password} "
        f"dbname={config.database} "
        f"sslmode={config.sslmode}"
    )


def describe_config(config: PostgresConfig) -> str:
    """生成适合展示的数据库配置信息摘要。

    Args:
        config: PostgreSQL 连接配置对象。

    Returns:
        str: 返回脱敏后的数据库配置摘要字符串。
    """

    return (
        f"host={config.host}, "
        f"port={config.port}, "
        f"user={config.user}, "
        f"password={mask_secret(config.password)}, "
        f"database={config.database}, "
        f"sslmode={config.sslmode}"
    )


def connect_db(config: PostgresConfig) -> Connection:
    """建立 PostgreSQL 数据库连接。

    Args:
        config: PostgreSQL 连接配置对象。

    Returns:
        Connection: 返回已建立好的 psycopg 连接对象。
    """

    return psycopg.connect(build_dsn(config))


def check_db_connection(config: PostgresConfig) -> tuple[str, str]:
    """检查数据库连通性并返回版本信息。

    Args:
        config: PostgreSQL 连接配置对象。

    Returns:
        tuple[str, str]: 返回数据库名和 PostgreSQL 版本字符串。
    """

    with closing(connect_db(config)) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_database(), version()")
            database_name, version_text = cursor.fetchone()
    return database_name, version_text


def execute_sql_text(config: PostgresConfig, sql_text: str) -> None:
    """执行一段 SQL 文本。

    Args:
        config: PostgreSQL 连接配置对象。
        sql_text: 需要在数据库中执行的 SQL 文本内容。
    """

    with closing(connect_db(config)) as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql_text)
        connection.commit()


def execute_sql_file(config: PostgresConfig, sql_file: str) -> None:
    """执行指定 SQL 文件内容。

    Args:
        config: PostgreSQL 连接配置对象。
        sql_file: 需要执行的 SQL 文件路径字符串。
    """

    with open(sql_file, "r", encoding="utf-8") as file_handle:
        execute_sql_text(config, file_handle.read())
