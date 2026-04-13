"""质检接口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from psycopg import Connection
from psycopg.errors import UniqueViolation

from ...permissions import is_admin_user
from ...services.qc_service import create_qc_rule, delete_qc_rule, get_qc_rule_by_id, list_qc_results, list_qc_rules, update_qc_rule
from ..dependencies import get_current_admin_user, get_current_user, get_db_connection
from ..schemas.common import ApiResponse
from ..schemas.qc import QcResultItem, QcRuleCreateRequest, QcRuleItem, QcRuleUpdateRequest

router = APIRouter()


@router.get("/rules", response_model=ApiResponse)
def get_qc_rule_list(
    connection: Connection = Depends(get_db_connection),
    current_user: dict = Depends(get_current_admin_user),
) -> ApiResponse:
    """获取质检规则列表。"""

    _ = current_user
    data = [QcRuleItem(**item) for item in list_qc_rules(connection)]
    return ApiResponse(data=data)


@router.post("/rules", response_model=ApiResponse)
def create_qc_rule_item(
    payload: QcRuleCreateRequest,
    connection: Connection = Depends(get_db_connection),
    current_user: dict = Depends(get_current_admin_user),
) -> ApiResponse:
    """创建质检规则。"""

    _ = current_user
    try:
        item = create_qc_rule(connection, payload)
    except UniqueViolation as exc:
        connection.rollback()
        raise HTTPException(status_code=409, detail="质检规则编码已存在") from exc
    return ApiResponse(message="created", data=QcRuleItem(**item))


@router.get("/rules/{rule_id}", response_model=ApiResponse)
def get_qc_rule_detail(
    rule_id: int,
    connection: Connection = Depends(get_db_connection),
    current_user: dict = Depends(get_current_admin_user),
) -> ApiResponse:
    """获取质检规则详情。"""

    _ = current_user
    item = get_qc_rule_by_id(connection, rule_id)
    if item is None:
        raise HTTPException(status_code=404, detail="质检规则不存在")
    return ApiResponse(data=QcRuleItem(**item))


@router.put("/rules/{rule_id}", response_model=ApiResponse)
def update_qc_rule_item(
    rule_id: int,
    payload: QcRuleUpdateRequest,
    connection: Connection = Depends(get_db_connection),
    current_user: dict = Depends(get_current_admin_user),
) -> ApiResponse:
    """更新质检规则。"""

    _ = current_user
    item = update_qc_rule(connection, rule_id, payload)
    if item is None:
        raise HTTPException(status_code=404, detail="质检规则不存在")
    return ApiResponse(message="updated", data=QcRuleItem(**item))


@router.delete("/rules/{rule_id}", response_model=ApiResponse)
def delete_qc_rule_item(
    rule_id: int,
    connection: Connection = Depends(get_db_connection),
    current_user: dict = Depends(get_current_admin_user),
) -> ApiResponse:
    """删除质检规则。"""

    _ = current_user
    deleted = delete_qc_rule(connection, rule_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="质检规则不存在")
    return ApiResponse(message="deleted")


@router.get("/results", response_model=ApiResponse)
def get_qc_result_list(
    connection: Connection = Depends(get_db_connection),
    current_user: dict = Depends(get_current_user),
) -> ApiResponse:
    """获取质检结果列表。"""

    _ = current_user
    data = [QcResultItem(**item) for item in list_qc_results(connection, current_user["id"], is_admin_user(current_user))]
    return ApiResponse(data=data)
