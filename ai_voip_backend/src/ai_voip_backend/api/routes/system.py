"""系统配置接口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from psycopg import Connection

from ..dependencies import get_current_admin_user, get_current_user, get_db_connection
from ..schemas.common import ApiResponse
from ..schemas.auth import CurrentUserData
from ..schemas.system import ConfigItem
from ...services.system_service import list_system_configs

router = APIRouter()


@router.get("/configs", response_model=ApiResponse)
def get_system_configs(
    connection: Connection = Depends(get_db_connection),
    current_user: dict = Depends(get_current_admin_user),
) -> ApiResponse:
    """获取系统配置列表。

    Args:
        connection: 通过 FastAPI 依赖注入得到的 PostgreSQL 连接对象。

    Returns:
        ApiResponse: 返回系统配置列表响应。
    """

    _ = current_user
    configs = [ConfigItem(**item) for item in list_system_configs(connection)]
    return ApiResponse(data=configs)


@router.get("/me", response_model=ApiResponse)
def get_current_user_info(current_user: dict = Depends(get_current_user)) -> ApiResponse:
    """获取当前登录用户信息。

    Args:
        current_user: 通过 FastAPI 依赖注入得到的当前登录用户信息。

    Returns:
        ApiResponse: 返回当前登录用户基础信息响应。
    """

    return ApiResponse(data=CurrentUserData(**current_user))
