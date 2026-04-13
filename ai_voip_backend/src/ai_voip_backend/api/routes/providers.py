"""语音接口配置接口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from psycopg import Connection
from psycopg.errors import UniqueViolation

from ...services.provider_service import (
    create_speech_provider,
    delete_speech_provider,
    get_speech_provider_by_id,
    list_speech_providers,
    update_speech_provider,
    validate_speech_provider_health,
)
from ..dependencies import get_current_admin_user, get_db_connection
from ..schemas.common import ApiResponse
from ..schemas.provider import SpeechProviderCreateRequest, SpeechProviderItem, SpeechProviderUpdateRequest

router = APIRouter()


@router.get("", response_model=ApiResponse)
def get_provider_list(
    connection: Connection = Depends(get_db_connection),
    current_user: dict = Depends(get_current_admin_user),
) -> ApiResponse:
    """获取语音接口配置列表。"""

    _ = current_user
    data = [SpeechProviderItem(**item) for item in list_speech_providers(connection)]
    return ApiResponse(data=data)


@router.post("", response_model=ApiResponse)
def create_provider_item(
    payload: SpeechProviderCreateRequest,
    connection: Connection = Depends(get_db_connection),
    current_user: dict = Depends(get_current_admin_user),
) -> ApiResponse:
    """创建语音接口配置。"""

    _ = current_user
    try:
        item = create_speech_provider(connection, payload)
    except UniqueViolation as exc:
        connection.rollback()
        raise HTTPException(status_code=409, detail="接口编码已存在") from exc
    return ApiResponse(message="created", data=SpeechProviderItem(**item))


@router.get("/{provider_id}", response_model=ApiResponse)
def get_provider_detail(
    provider_id: int,
    connection: Connection = Depends(get_db_connection),
    current_user: dict = Depends(get_current_admin_user),
) -> ApiResponse:
    """获取语音接口配置详情。"""

    _ = current_user
    item = get_speech_provider_by_id(connection, provider_id)
    if item is None:
        raise HTTPException(status_code=404, detail="接口配置不存在")
    return ApiResponse(data=SpeechProviderItem(**item))


@router.post("/{provider_id}/health-check", response_model=ApiResponse)
def check_provider_health(
    provider_id: int,
    connection: Connection = Depends(get_db_connection),
    current_user: dict = Depends(get_current_admin_user),
) -> ApiResponse:
    """检测指定语音接口的连通状态。"""

    _ = current_user
    item = get_speech_provider_by_id(connection, provider_id)
    if item is None:
        raise HTTPException(status_code=404, detail="接口配置不存在")
    result = validate_speech_provider_health(item)
    return ApiResponse(message="checked", data=result)


@router.put("/{provider_id}", response_model=ApiResponse)
def update_provider_item(
    provider_id: int,
    payload: SpeechProviderUpdateRequest,
    connection: Connection = Depends(get_db_connection),
    current_user: dict = Depends(get_current_admin_user),
) -> ApiResponse:
    """更新语音接口配置。"""

    _ = current_user
    item = update_speech_provider(connection, provider_id, payload)
    if item is None:
        raise HTTPException(status_code=404, detail="接口配置不存在")
    return ApiResponse(message="updated", data=SpeechProviderItem(**item))


@router.delete("/{provider_id}", response_model=ApiResponse)
def delete_provider_item(
    provider_id: int,
    connection: Connection = Depends(get_db_connection),
    current_user: dict = Depends(get_current_admin_user),
) -> ApiResponse:
    """删除语音接口配置。"""

    _ = current_user
    deleted = delete_speech_provider(connection, provider_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="接口配置不存在")
    return ApiResponse(message="deleted")
