"""FastAPI 依赖项。"""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from psycopg import Connection

from ..auth import decode_access_token
from ..config import JwtConfig, PostgresConfig, load_jwt_config, load_postgres_config
from ..db import connect_db
from ..permissions import is_admin_user
from ..services.auth_service import get_user_by_id


def get_project_root() -> Path:
    """获取后端项目根目录。

    Returns:
        Path: 返回 ai_voip_backend 项目根目录绝对路径。
    """

    return Path(__file__).resolve().parents[3]


def get_postgres_config() -> PostgresConfig:
    """读取当前 FastAPI 进程使用的 PostgreSQL 配置。

    Returns:
        PostgresConfig: 返回数据库连接配置对象。
    """

    return load_postgres_config(get_project_root())


def get_jwt_config() -> JwtConfig:
    """读取当前 FastAPI 进程使用的 JWT 配置。

    Returns:
        JwtConfig: 返回 JWT 配置对象。
    """

    return load_jwt_config(get_project_root())


def get_db_connection() -> Generator[Connection, None, None]:
    """为每个请求提供独立数据库连接。

    Yields:
        Connection: 返回可用于执行 SQL 的 psycopg 数据库连接对象。
    """

    connection = connect_db(get_postgres_config())
    try:
        yield connection
    finally:
        connection.close()


bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    connection: Connection = Depends(get_db_connection),
    jwt_config: JwtConfig = Depends(get_jwt_config),
) -> dict:
    """获取当前登录用户。

    Args:
        credentials: 请求头中的 Bearer 令牌凭证。
        connection: 通过 FastAPI 依赖注入得到的 PostgreSQL 连接对象。
        jwt_config: 通过 FastAPI 依赖注入得到的 JWT 配置对象。

    Returns:
        dict: 返回当前登录用户信息字典。
    """

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供访问令牌",
        )

    try:
        payload = decode_access_token(jwt_config, credentials.credentials)
        user_id = int(payload["sub"])
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="访问令牌无效或已过期",
        ) from exc

    user = get_user_by_id(connection, user_id)
    if user is None or user["status"] != "active":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="当前用户不存在或已禁用",
        )
    return user


def get_current_admin_user(current_user: dict = Depends(get_current_user)) -> dict:
    """获取当前登录管理员用户。

    Args:
        current_user: 当前登录用户信息字典。

    Returns:
        dict: 返回当前管理员用户信息字典。
    """

    if not is_admin_user(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="当前账号无管理员权限",
        )
    return current_user
