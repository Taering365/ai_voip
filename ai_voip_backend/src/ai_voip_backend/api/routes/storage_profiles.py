"""存储配置接口。"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from psycopg import Connection
from psycopg.errors import UniqueViolation
from pydantic import BaseModel, Field

from ...services.storage_service import (
    create_storage_profile,
    delete_storage_profile,
    get_default_storage_profile,
    get_storage_profile_by_id,
    list_storage_profiles,
    probe_storage_profile,
    set_default_storage_profile,
    update_storage_profile,
)
from ..dependencies import get_current_admin_user, get_db_connection, get_project_root
from ..schemas.common import ApiResponse
from ..schemas.storage import StorageProbeResponse, StorageProfileItem


class StorageProfileRequest(BaseModel):
    """定义存储配置创建与更新请求体。"""

    profile_code: str = Field(default="", max_length=64)
    profile_name: str = Field(min_length=1, max_length=128)
    storage_backend: str = Field(min_length=1, max_length=32)
    is_default: bool = False
    root_dir: str | None = None
    endpoint: str | None = None
    bucket_name: str | None = None
    access_key: str | None = None
    secret_key: str | None = None
    region_name: str | None = None
    extra_config: dict = Field(default_factory=dict)


router = APIRouter()


@router.get("/profiles", response_model=ApiResponse)
def get_storage_profiles(
    connection: Connection = Depends(get_db_connection),
    current_user: dict = Depends(get_current_admin_user),
) -> ApiResponse:
    """获取全部存储配置列表。"""

    _ = current_user
    profiles = [StorageProfileItem(**item) for item in list_storage_profiles(connection)]
    return ApiResponse(data=profiles)


@router.get("/profiles/default", response_model=ApiResponse)
def get_default_profile(
    connection: Connection = Depends(get_db_connection),
    current_user: dict = Depends(get_current_admin_user),
) -> ApiResponse:
    """获取默认存储配置。"""

    _ = current_user
    profile = get_default_storage_profile(connection)
    if profile is None:
        raise HTTPException(status_code=404, detail="未找到默认存储配置")
    return ApiResponse(data=StorageProfileItem(**profile))


@router.post("/profiles", response_model=ApiResponse)
def create_storage_profile_item(
    payload: StorageProfileRequest,
    connection: Connection = Depends(get_db_connection),
    current_user: dict = Depends(get_current_admin_user),
) -> ApiResponse:
    """创建存储配置。"""

    _ = current_user
    try:
        profile = create_storage_profile(connection, payload.model_dump(mode="python"))
    except UniqueViolation as exc:
        connection.rollback()
        raise HTTPException(status_code=409, detail="存储配置编码已存在") from exc
    return ApiResponse(message="created", data=StorageProfileItem(**profile))


@router.post("/profiles/probe", response_model=ApiResponse)
def probe_storage_profile_item(
    payload: StorageProfileRequest,
    connection: Connection = Depends(get_db_connection),
    current_user: dict = Depends(get_current_admin_user),
    project_root: Path = Depends(get_project_root),
) -> ApiResponse:
    """检测存储配置是否可用。"""

    _ = (connection, current_user)
    result = probe_storage_profile(payload.model_dump(mode="python"), project_root)
    return ApiResponse(message="probed", data=StorageProbeResponse(**result))


@router.get("/profiles/{profile_id}", response_model=ApiResponse)
def get_storage_profile_detail(
    profile_id: int,
    connection: Connection = Depends(get_db_connection),
    current_user: dict = Depends(get_current_admin_user),
) -> ApiResponse:
    """获取存储配置详情。"""

    _ = current_user
    profile = get_storage_profile_by_id(connection, profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="存储配置不存在")
    return ApiResponse(data=StorageProfileItem(**profile))


@router.put("/profiles/{profile_id}", response_model=ApiResponse)
def update_storage_profile_item(
    profile_id: int,
    payload: StorageProfileRequest,
    connection: Connection = Depends(get_db_connection),
    current_user: dict = Depends(get_current_admin_user),
) -> ApiResponse:
    """更新存储配置。"""

    _ = current_user
    profile = update_storage_profile(connection, profile_id, payload.model_dump(mode="python"))
    if profile is None:
        raise HTTPException(status_code=404, detail="存储配置不存在")
    return ApiResponse(message="updated", data=StorageProfileItem(**profile))


@router.post("/profiles/{profile_id}/default", response_model=ApiResponse)
def set_default_profile_item(
    profile_id: int,
    connection: Connection = Depends(get_db_connection),
    current_user: dict = Depends(get_current_admin_user),
) -> ApiResponse:
    """设置默认存储配置。"""

    _ = current_user
    profile = set_default_storage_profile(connection, profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="存储配置不存在")
    return ApiResponse(message="updated", data=StorageProfileItem(**profile))


@router.delete("/profiles/{profile_id}", response_model=ApiResponse)
def delete_storage_profile_item(
    profile_id: int,
    connection: Connection = Depends(get_db_connection),
    current_user: dict = Depends(get_current_admin_user),
) -> ApiResponse:
    """删除存储配置。"""

    _ = current_user
    deleted = delete_storage_profile(connection, profile_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="存储配置不存在")
    return ApiResponse(message="deleted")
