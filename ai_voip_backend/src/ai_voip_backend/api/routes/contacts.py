"""名单与联系人接口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from psycopg import Connection
from psycopg.errors import UniqueViolation

from ...permissions import is_admin_user
from ...services.contact_service import (
    create_contact_batch,
    create_contact_record,
    delete_contact_batch,
    delete_contact_record,
    get_contact_batch_by_id,
    get_contact_record_by_id,
    import_contact_records,
    list_contact_batches,
    list_contact_records,
)
from ..dependencies import get_current_user, get_db_connection
from ..schemas.common import ApiResponse
from ..schemas.contact import (
    ContactBatchCreateRequest,
    ContactBatchItem,
    ContactRecordCreateRequest,
    ContactRecordImportRequest,
    ContactRecordItem,
)

router = APIRouter()


def _validate_batch_permission(batch_item: dict | None, current_user: dict) -> dict:
    """校验当前用户是否有权访问指定批次。

    参数:
        batch_item: 已查询到的批次详情对象，不存在时可能为 None。
        current_user: 当前登录用户对象，包含用户主键和角色信息。

    返回:
        dict: 已通过权限校验的批次详情对象。
    """

    if batch_item is None:
        raise HTTPException(status_code=404, detail="批次不存在")
    if not is_admin_user(current_user) and batch_item["created_by"] != current_user["id"]:
        raise HTTPException(status_code=404, detail="批次不存在")
    return batch_item


@router.get("/batches", response_model=ApiResponse)
def get_contact_batch_list(
    connection: Connection = Depends(get_db_connection),
    current_user: dict = Depends(get_current_user),
) -> ApiResponse:
    """获取名单批次列表。"""

    _ = current_user
    data = [
        ContactBatchItem(**item)
        for item in list_contact_batches(connection, current_user["id"], is_admin_user(current_user))
    ]
    return ApiResponse(data=data)


@router.post("/batches", response_model=ApiResponse)
def create_contact_batch_item(
    payload: ContactBatchCreateRequest,
    connection: Connection = Depends(get_db_connection),
    current_user: dict = Depends(get_current_user),
) -> ApiResponse:
    """创建名单批次。"""

    _ = current_user
    try:
        payload.created_by = current_user["id"]
        item = create_contact_batch(connection, payload)
    except UniqueViolation as exc:
        connection.rollback()
        raise HTTPException(status_code=409, detail="批次创建失败，请重试") from exc
    return ApiResponse(message="created", data=ContactBatchItem(**item))


@router.get("/batches/{batch_id}", response_model=ApiResponse)
def get_contact_batch_detail(
    batch_id: int,
    connection: Connection = Depends(get_db_connection),
    current_user: dict = Depends(get_current_user),
) -> ApiResponse:
    """获取名单批次详情。"""

    _ = current_user
    item = _validate_batch_permission(get_contact_batch_by_id(connection, batch_id), current_user)
    return ApiResponse(data=ContactBatchItem(**item))


@router.delete("/batches/{batch_id}", response_model=ApiResponse)
def delete_contact_batch_item(
    batch_id: int,
    connection: Connection = Depends(get_db_connection),
    current_user: dict = Depends(get_current_user),
) -> ApiResponse:
    """删除名单批次。"""

    _ = current_user
    _validate_batch_permission(get_contact_batch_by_id(connection, batch_id), current_user)
    deleted = delete_contact_batch(connection, batch_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="批次不存在")
    return ApiResponse(message="deleted")


@router.get("/records", response_model=ApiResponse)
def get_contact_record_list(
    batch_id: int | None = Query(default=None),
    connection: Connection = Depends(get_db_connection),
    current_user: dict = Depends(get_current_user),
) -> ApiResponse:
    """获取联系人列表。"""

    _ = current_user
    data = [
        ContactRecordItem(**item)
        for item in list_contact_records(connection, batch_id, current_user["id"], is_admin_user(current_user))
    ]
    return ApiResponse(data=data)


@router.post("/records", response_model=ApiResponse)
def create_contact_record_item(
    payload: ContactRecordCreateRequest,
    connection: Connection = Depends(get_db_connection),
    current_user: dict = Depends(get_current_user),
) -> ApiResponse:
    """创建联系人。"""

    _ = current_user
    try:
        payload.created_by = current_user["id"]
        _validate_batch_permission(get_contact_batch_by_id(connection, payload.batch_id), current_user)
        item = create_contact_record(connection, payload)
    except UniqueViolation as exc:
        connection.rollback()
        raise HTTPException(status_code=409, detail="联系人创建失败，请重试") from exc
    return ApiResponse(message="created", data=ContactRecordItem(**item))


@router.post("/records/import", response_model=ApiResponse)
def import_contact_record_items(
    payload: ContactRecordImportRequest,
    connection: Connection = Depends(get_db_connection),
    current_user: dict = Depends(get_current_user),
) -> ApiResponse:
    """批量导入联系人。"""

    _ = current_user
    if not payload.records:
        raise HTTPException(status_code=422, detail="导入联系人不能为空")
    try:
        payload.created_by = current_user["id"]
        _validate_batch_permission(get_contact_batch_by_id(connection, payload.batch_id), current_user)
        result = import_contact_records(connection, payload)
    except UniqueViolation as exc:
        connection.rollback()
        raise HTTPException(status_code=409, detail="联系人导入失败，请检查文件内容后重试") from exc
    return ApiResponse(message="imported", data=result)


@router.get("/records/{record_id}", response_model=ApiResponse)
def get_contact_record_detail(
    record_id: int,
    connection: Connection = Depends(get_db_connection),
    current_user: dict = Depends(get_current_user),
) -> ApiResponse:
    """获取联系人详情。"""

    _ = current_user
    item = get_contact_record_by_id(connection, record_id)
    if item is None or (not is_admin_user(current_user) and item.get("created_by") != current_user["id"]):
        raise HTTPException(status_code=404, detail="联系人不存在")
    return ApiResponse(data=ContactRecordItem(**item))


@router.delete("/records/{record_id}", response_model=ApiResponse)
def delete_contact_record_item(
    record_id: int,
    connection: Connection = Depends(get_db_connection),
    current_user: dict = Depends(get_current_user),
) -> ApiResponse:
    """删除联系人。"""

    _ = current_user
    item = get_contact_record_by_id(connection, record_id)
    if item is None or (not is_admin_user(current_user) and item.get("created_by") != current_user["id"]):
        raise HTTPException(status_code=404, detail="联系人不存在")
    deleted = delete_contact_record(connection, record_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="联系人不存在")
    return ApiResponse(message="deleted")
