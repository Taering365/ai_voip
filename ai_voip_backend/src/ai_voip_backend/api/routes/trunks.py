"""SIP 线路接口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from psycopg import Connection
from psycopg.errors import UniqueViolation

from ...permissions import is_admin_user
from ..dependencies import get_current_admin_user, get_current_user, get_db_connection
from ..schemas.common import ApiResponse
from ..schemas.trunk import TrunkCreateRequest, TrunkItem, TrunkStatusUpdateRequest, TrunkUpdateRequest
from ...services.trunk_service import (
    create_trunk,
    delete_trunk,
    get_trunk_by_id,
    list_trunks,
    probe_trunk,
    update_trunk,
    update_trunk_status,
)

router = APIRouter()


@router.get("", response_model=ApiResponse)
def get_trunk_list(
    connection: Connection = Depends(get_db_connection),
    current_user: dict = Depends(get_current_user),
) -> ApiResponse:
    """获取 SIP 线路列表。

    Args:
        connection: 通过 FastAPI 依赖注入得到的 PostgreSQL 连接对象。

    Returns:
        ApiResponse: 返回线路列表响应。
    """

    trunks = [TrunkItem(**item) for item in list_trunks(connection, current_user["id"], is_admin_user(current_user))]
    return ApiResponse(data=trunks)


@router.get("/{trunk_id}", response_model=ApiResponse)
def get_trunk_detail(
    trunk_id: int,
    connection: Connection = Depends(get_db_connection),
    current_user: dict = Depends(get_current_user),
) -> ApiResponse:
    """获取单条 SIP 线路详情。

    Args:
        trunk_id: 需要查询的线路主键。
        connection: 通过 FastAPI 依赖注入得到的 PostgreSQL 连接对象。

    Returns:
        ApiResponse: 返回线路详情响应。
    """

    available_trunks = list_trunks(connection, current_user["id"], is_admin_user(current_user))
    trunk = next((item for item in available_trunks if item["id"] == trunk_id), None)
    if trunk is None:
        raise HTTPException(status_code=404, detail="线路不存在")
    return ApiResponse(data=TrunkItem(**trunk))


@router.post("", response_model=ApiResponse)
def create_trunk_item(
    payload: TrunkCreateRequest,
    connection: Connection = Depends(get_db_connection),
    current_user: dict = Depends(get_current_admin_user),
) -> ApiResponse:
    """创建新的 SIP 线路。

    Args:
        payload: 创建 SIP 线路的请求体模型。
        connection: 通过 FastAPI 依赖注入得到的 PostgreSQL 连接对象。

    Returns:
        ApiResponse: 返回创建后的线路详情响应。
    """

    _ = current_user
    try:
        trunk = create_trunk(connection, payload)
    except UniqueViolation as exc:
        connection.rollback()
        raise HTTPException(status_code=409, detail="线路编码已存在") from exc
    except ValueError as exc:
        connection.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ApiResponse(message="created", data=TrunkItem(**trunk))


@router.put("/{trunk_id}", response_model=ApiResponse)
def update_trunk_item(
    trunk_id: int,
    payload: TrunkUpdateRequest,
    connection: Connection = Depends(get_db_connection),
    current_user: dict = Depends(get_current_admin_user),
) -> ApiResponse:
    """更新指定 SIP 线路的基础信息。

    Args:
        trunk_id: 需要更新的线路主键。
        payload: 更新 SIP 线路的请求体模型。
        connection: 通过 FastAPI 依赖注入得到的 PostgreSQL 连接对象。

    Returns:
        ApiResponse: 返回更新后的线路详情响应。
    """

    _ = current_user
    try:
        trunk = update_trunk(connection, trunk_id, payload)
    except ValueError as exc:
        connection.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if trunk is None:
        raise HTTPException(status_code=404, detail="线路不存在")
    return ApiResponse(message="updated", data=TrunkItem(**trunk))


@router.patch("/{trunk_id}/status", response_model=ApiResponse)
def update_trunk_status_item(
    trunk_id: int,
    payload: TrunkStatusUpdateRequest,
    connection: Connection = Depends(get_db_connection),
    current_user: dict = Depends(get_current_admin_user),
) -> ApiResponse:
    """更新指定 SIP 线路状态。

    Args:
        trunk_id: 需要更新状态的线路主键。
        payload: 更新线路状态的请求体模型。
        connection: 通过 FastAPI 依赖注入得到的 PostgreSQL 连接对象。

    Returns:
        ApiResponse: 返回更新后的线路详情响应。
    """

    _ = current_user
    trunk = update_trunk_status(connection, trunk_id, payload)
    if trunk is None:
        raise HTTPException(status_code=404, detail="线路不存在")
    return ApiResponse(message="updated", data=TrunkItem(**trunk))


@router.post("/{trunk_id}/probe", response_model=ApiResponse)
def probe_trunk_item(
    trunk_id: int,
    connection: Connection = Depends(get_db_connection),
    current_user: dict = Depends(get_current_admin_user),
) -> ApiResponse:
    """检测指定线路的连通性和注册准备状态。

    Args:
        trunk_id: 需要检测的线路主键。
        connection: 通过 FastAPI 依赖注入得到的 PostgreSQL 连接对象。
        current_user: 当前登录管理员用户信息。

    Returns:
        ApiResponse: 返回线路检测结果响应。
    """

    _ = current_user
    probe_result = probe_trunk(connection, trunk_id)
    if probe_result is None:
        raise HTTPException(status_code=404, detail="线路不存在")
    return ApiResponse(message="probed", data=probe_result)


@router.delete("/{trunk_id}", response_model=ApiResponse)
def delete_trunk_item(
    trunk_id: int,
    connection: Connection = Depends(get_db_connection),
    current_user: dict = Depends(get_current_admin_user),
) -> ApiResponse:
    """删除指定线路。

    Args:
        trunk_id: 需要删除的线路主键。
        connection: 通过 FastAPI 依赖注入得到的 PostgreSQL 连接对象。
        current_user: 当前登录管理员用户信息。

    Returns:
        ApiResponse: 返回删除结果响应。
    """

    _ = current_user
    deleted = delete_trunk(connection, trunk_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="线路不存在")
    return ApiResponse(message="deleted")
