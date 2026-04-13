"""任务与会话接口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from psycopg import Connection
from psycopg.errors import UniqueViolation

from ...permissions import is_admin_user
from ...services.task_service import (
    create_call_task,
    delete_call_task,
    get_call_task_by_id,
    list_call_task_runs,
    list_call_sessions,
    list_call_tasks,
    update_call_task,
    update_call_task_status,
)
from ..dependencies import get_current_user, get_db_connection
from ..schemas.common import ApiResponse
from ..schemas.task import (
    CallSessionItem,
    CallTaskCreateRequest,
    CallTaskItem,
    CallTaskRunItem,
    CallTaskStatusUpdateRequest,
    CallTaskUpdateRequest,
)

router = APIRouter()


@router.get("", response_model=ApiResponse)
def get_call_task_list(
    connection: Connection = Depends(get_db_connection),
    current_user: dict = Depends(get_current_user),
) -> ApiResponse:
    """获取外呼任务列表。"""

    _ = current_user
    data = [CallTaskItem(**item) for item in list_call_tasks(connection, current_user["id"], is_admin_user(current_user))]
    return ApiResponse(data=data)


@router.post("", response_model=ApiResponse)
def create_call_task_item(
    payload: CallTaskCreateRequest,
    connection: Connection = Depends(get_db_connection),
    current_user: dict = Depends(get_current_user),
) -> ApiResponse:
    """创建外呼任务。"""

    _ = current_user
    try:
        payload.created_by = current_user["id"]
        item = create_call_task(connection, payload)
    except UniqueViolation as exc:
        connection.rollback()
        raise HTTPException(status_code=409, detail="任务编码已存在") from exc
    return ApiResponse(message="created", data=CallTaskItem(**item))


@router.get("/{task_id}", response_model=ApiResponse)
def get_call_task_detail(
    task_id: int,
    connection: Connection = Depends(get_db_connection),
    current_user: dict = Depends(get_current_user),
) -> ApiResponse:
    """获取外呼任务详情。"""

    _ = current_user
    item = get_call_task_by_id(connection, task_id)
    if item is None or (not is_admin_user(current_user) and item["created_by"] != current_user["id"]):
        raise HTTPException(status_code=404, detail="任务不存在")
    return ApiResponse(data=CallTaskItem(**item))


@router.put("/{task_id}", response_model=ApiResponse)
def update_call_task_item(
    task_id: int,
    payload: CallTaskUpdateRequest,
    connection: Connection = Depends(get_db_connection),
    current_user: dict = Depends(get_current_user),
) -> ApiResponse:
    """更新外呼任务。"""

    _ = current_user
    current_item = get_call_task_by_id(connection, task_id)
    if current_item is None or (not is_admin_user(current_user) and current_item["created_by"] != current_user["id"]):
        raise HTTPException(status_code=404, detail="任务不存在")
    item = update_call_task(connection, task_id, payload)
    if item is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return ApiResponse(message="updated", data=CallTaskItem(**item))


@router.patch("/{task_id}/status", response_model=ApiResponse)
def update_call_task_status_item(
    task_id: int,
    payload: CallTaskStatusUpdateRequest,
    connection: Connection = Depends(get_db_connection),
    current_user: dict = Depends(get_current_user),
) -> ApiResponse:
    """更新外呼任务状态。"""

    _ = current_user
    current_item = get_call_task_by_id(connection, task_id)
    if current_item is None or (not is_admin_user(current_user) and current_item["created_by"] != current_user["id"]):
        raise HTTPException(status_code=404, detail="任务不存在")
    item = update_call_task_status(connection, task_id, payload)
    if item is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return ApiResponse(message="updated", data=CallTaskItem(**item))


@router.delete("/{task_id}", response_model=ApiResponse)
def delete_call_task_item(
    task_id: int,
    connection: Connection = Depends(get_db_connection),
    current_user: dict = Depends(get_current_user),
) -> ApiResponse:
    """删除外呼任务。"""

    _ = current_user
    current_item = get_call_task_by_id(connection, task_id)
    if current_item is None or (not is_admin_user(current_user) and current_item["created_by"] != current_user["id"]):
        raise HTTPException(status_code=404, detail="任务不存在")
    deleted = delete_call_task(connection, task_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="任务不存在")
    return ApiResponse(message="deleted")


@router.get("/{task_id}/sessions", response_model=ApiResponse)
def get_call_task_session_list(
    task_id: int,
    connection: Connection = Depends(get_db_connection),
    current_user: dict = Depends(get_current_user),
) -> ApiResponse:
    """获取指定任务下的通话会话列表。"""

    _ = current_user
    current_item = get_call_task_by_id(connection, task_id)
    if current_item is None or (not is_admin_user(current_user) and current_item["created_by"] != current_user["id"]):
        raise HTTPException(status_code=404, detail="任务不存在")
    data = [
        CallSessionItem(**item)
        for item in list_call_sessions(connection, task_id, current_user["id"], is_admin_user(current_user))
    ]
    return ApiResponse(data=data)


@router.get("/{task_id}/runs", response_model=ApiResponse)
def get_call_task_run_list(
    task_id: int,
    connection: Connection = Depends(get_db_connection),
    current_user: dict = Depends(get_current_user),
) -> ApiResponse:
    """获取指定任务下的执行批次列表。"""

    _ = current_user
    current_item = get_call_task_by_id(connection, task_id)
    if current_item is None or (not is_admin_user(current_user) and current_item["created_by"] != current_user["id"]):
        raise HTTPException(status_code=404, detail="任务不存在")
    data = [CallTaskRunItem(**item) for item in list_call_task_runs(connection, task_id)]
    return ApiResponse(data=data)
