"""运行态接口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from psycopg import Connection

from ...errors import AppError
from ...permissions import is_admin_user
from ...services.runtime_service import (
    create_call_session_for_dispatch,
    execute_script_step,
    get_call_session_by_id,
    fetch_pending_dispatches,
    progress_call_session,
    queue_task_dispatches,
    simulate_script,
)
from ...services.script_service import get_script_by_id, get_script_version_by_id
from ...services.task_service import get_call_task_by_id
from ..dependencies import get_current_user, get_db_connection
from ..schemas.common import ApiResponse
from ..schemas.runtime import (
    ScriptSimulationRequest,
    ScriptStepRequest,
    ScriptStepResponse,
    TaskDispatchFetchResponse,
    TaskQueueResponse,
    TaskSessionCreateRequest,
    TaskSessionProgressRequest,
)
from ..schemas.task import CallSessionItem

router = APIRouter()


@router.post("/scripts/{script_version_id}/step", response_model=ApiResponse)
def execute_script_step_item(
    script_version_id: int,
    payload: ScriptStepRequest,
    connection: Connection = Depends(get_db_connection),
    current_user: dict = Depends(get_current_user),
) -> ApiResponse:
    """执行话术单步推进。"""

    _ = current_user
    version = get_script_version_by_id(connection, script_version_id)
    if version is None:
        raise AppError("script_runtime_invalid", "话术版本不存在", 404)
    script = get_script_by_id(connection, version["script_id"])
    if script is None or (not is_admin_user(current_user) and script["created_by"] != current_user["id"]):
        raise AppError("script_runtime_invalid", "话术版本不存在", 404)
    try:
        result = execute_script_step(connection, script_version_id, payload)
    except ValueError as exc:
        raise AppError("script_runtime_invalid", str(exc), 404) from exc
    return ApiResponse(data=ScriptStepResponse(**result))


@router.post("/scripts/{script_version_id}/simulate", response_model=ApiResponse)
def simulate_script_item(
    script_version_id: int,
    payload: ScriptSimulationRequest,
    connection: Connection = Depends(get_db_connection),
    current_user: dict = Depends(get_current_user),
) -> ApiResponse:
    """模拟执行整个话术流程。"""

    _ = current_user
    version = get_script_version_by_id(connection, script_version_id)
    if version is None:
        raise AppError("script_runtime_invalid", "话术版本不存在", 404)
    script = get_script_by_id(connection, version["script_id"])
    if script is None or (not is_admin_user(current_user) and script["created_by"] != current_user["id"]):
        raise AppError("script_runtime_invalid", "话术版本不存在", 404)
    try:
        result = simulate_script(connection, script_version_id, payload)
    except ValueError as exc:
        raise AppError("script_runtime_invalid", str(exc), 404) from exc
    return ApiResponse(data=result)


@router.post("/tasks/{task_id}/queue", response_model=ApiResponse)
def queue_task_item(
    task_id: int,
    connection: Connection = Depends(get_db_connection),
    current_user: dict = Depends(get_current_user),
) -> ApiResponse:
    """生成任务分发表并进入待调度状态。"""

    _ = current_user
    task = get_call_task_by_id(connection, task_id)
    if task is None or (not is_admin_user(current_user) and task["created_by"] != current_user["id"]):
        raise AppError("task_queue_invalid", "任务不存在", 404)
    try:
        result = queue_task_dispatches(connection, task_id)
    except ValueError as exc:
        raise AppError("task_queue_invalid", str(exc), 404) from exc
    return ApiResponse(message="queued", data=TaskQueueResponse(**result))


@router.get("/tasks/{task_id}/dispatches/pending", response_model=ApiResponse)
def fetch_pending_dispatches_item(
    task_id: int,
    limit: int = Query(default=20, ge=1, le=100),
    connection: Connection = Depends(get_db_connection),
    current_user: dict = Depends(get_current_user),
) -> ApiResponse:
    """拉取任务待调度联系人。"""

    _ = current_user
    task = get_call_task_by_id(connection, task_id)
    if task is None or (not is_admin_user(current_user) and task["created_by"] != current_user["id"]):
        raise AppError("task_dispatch_invalid", "任务不存在", 404)
    try:
        result = fetch_pending_dispatches(connection, task_id, limit)
    except ValueError as exc:
        raise AppError("task_dispatch_invalid", str(exc), 404) from exc
    return ApiResponse(data=TaskDispatchFetchResponse(**result))


@router.post("/tasks/{task_id}/sessions", response_model=ApiResponse)
def create_dispatch_session_item(
    task_id: int,
    payload: TaskSessionCreateRequest,
    connection: Connection = Depends(get_db_connection),
    current_user: dict = Depends(get_current_user),
) -> ApiResponse:
    """为待调度记录创建运行中会话。"""

    _ = current_user
    task = get_call_task_by_id(connection, task_id)
    if task is None or (not is_admin_user(current_user) and task["created_by"] != current_user["id"]):
        raise AppError("task_session_invalid", "任务不存在", 404)
    try:
        session = create_call_session_for_dispatch(connection, task_id, payload)
    except ValueError as exc:
        raise AppError("task_session_invalid", str(exc), 404) from exc
    return ApiResponse(message="created", data=CallSessionItem(**session))


@router.patch("/sessions/{session_id}/progress", response_model=ApiResponse)
def progress_session_item(
    session_id: int,
    payload: TaskSessionProgressRequest,
    connection: Connection = Depends(get_db_connection),
    current_user: dict = Depends(get_current_user),
) -> ApiResponse:
    """推进通话会话状态和事件。"""

    _ = current_user
    current_session = get_call_session_by_id(connection, session_id)
    if current_session is None:
        raise HTTPException(status_code=404, detail="通话会话不存在")
    task = get_call_task_by_id(connection, current_session["task_id"])
    if task is None or (not is_admin_user(current_user) and task["created_by"] != current_user["id"]):
        raise HTTPException(status_code=404, detail="通话会话不存在")
    session = progress_call_session(connection, session_id, payload)
    if session is None:
        raise HTTPException(status_code=404, detail="通话会话不存在")
    return ApiResponse(message="updated", data=CallSessionItem(**session))
