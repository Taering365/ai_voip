"""用户管理接口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from psycopg import Connection
from psycopg.errors import UniqueViolation

from ...services.user_service import (
    create_user,
    get_user_by_id_with_roles,
    list_user_trunk_assignments,
    list_users,
    replace_user_trunk_assignments,
    update_user,
)
from ..dependencies import get_current_admin_user, get_db_connection
from ..schemas.common import ApiResponse
from ..schemas.trunk import TrunkItem
from ..schemas.user import UserCreateRequest, UserItem, UserTrunkAssignmentRequest, UserUpdateRequest

router = APIRouter()


@router.get("", response_model=ApiResponse)
def get_user_list(
    connection: Connection = Depends(get_db_connection),
    current_user: dict = Depends(get_current_admin_user),
) -> ApiResponse:
    """获取全部系统用户列表。

    Args:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        current_user: 当前登录管理员信息。

    Returns:
        ApiResponse: 返回用户列表响应。
    """

    _ = current_user
    return ApiResponse(data=[UserItem(**item) for item in list_users(connection)])


@router.post("", response_model=ApiResponse)
def create_user_item(
    payload: UserCreateRequest,
    connection: Connection = Depends(get_db_connection),
    current_user: dict = Depends(get_current_admin_user),
) -> ApiResponse:
    """创建新系统用户。

    Args:
        payload: 创建用户请求体。
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        current_user: 当前登录管理员信息。

    Returns:
        ApiResponse: 返回创建后的用户详情响应。
    """

    _ = current_user
    try:
        item = create_user(
            connection,
            payload.username,
            payload.password,
            payload.display_name,
            payload.mobile,
            payload.email,
            payload.status,
            payload.role_codes,
        )
    except UniqueViolation as exc:
        connection.rollback()
        raise HTTPException(status_code=409, detail="用户名已存在") from exc
    return ApiResponse(message="created", data=UserItem(**item))


@router.get("/{user_id}", response_model=ApiResponse)
def get_user_detail(
    user_id: int,
    connection: Connection = Depends(get_db_connection),
    current_user: dict = Depends(get_current_admin_user),
) -> ApiResponse:
    """获取指定用户详情。

    Args:
        user_id: 用户主键。
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        current_user: 当前登录管理员信息。

    Returns:
        ApiResponse: 返回用户详情响应。
    """

    _ = current_user
    item = get_user_by_id_with_roles(connection, user_id)
    if item is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    return ApiResponse(data=UserItem(**item))


@router.put("/{user_id}", response_model=ApiResponse)
def update_user_item(
    user_id: int,
    payload: UserUpdateRequest,
    connection: Connection = Depends(get_db_connection),
    current_user: dict = Depends(get_current_admin_user),
) -> ApiResponse:
    """更新指定用户信息。

    Args:
        user_id: 用户主键。
        payload: 更新用户请求体。
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        current_user: 当前登录管理员信息。

    Returns:
        ApiResponse: 返回更新后的用户详情响应。
    """

    _ = current_user
    item = update_user(
        connection,
        user_id,
        payload.display_name,
        payload.mobile,
        payload.email,
        payload.status,
        payload.role_codes,
        payload.password,
    )
    if item is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    return ApiResponse(message="updated", data=UserItem(**item))


@router.get("/{user_id}/trunks", response_model=ApiResponse)
def get_user_trunks(
    user_id: int,
    connection: Connection = Depends(get_db_connection),
    current_user: dict = Depends(get_current_admin_user),
) -> ApiResponse:
    """获取指定用户已分配的线路列表。

    Args:
        user_id: 用户主键。
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        current_user: 当前登录管理员信息。

    Returns:
        ApiResponse: 返回线路分配列表响应。
    """

    _ = current_user
    return ApiResponse(data=[TrunkItem(**item) for item in list_user_trunk_assignments(connection, user_id)])


@router.put("/{user_id}/trunks", response_model=ApiResponse)
def replace_user_trunks(
    user_id: int,
    payload: UserTrunkAssignmentRequest,
    connection: Connection = Depends(get_db_connection),
    current_user: dict = Depends(get_current_admin_user),
) -> ApiResponse:
    """重置指定用户的线路分配关系。

    Args:
        user_id: 用户主键。
        payload: 线路分配请求体。
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        current_user: 当前登录管理员信息。

    Returns:
        ApiResponse: 返回最新线路分配结果。
    """

    _ = current_user
    items = replace_user_trunk_assignments(connection, user_id, payload.trunk_ids)
    return ApiResponse(message="updated", data=[TrunkItem(**item) for item in items])
