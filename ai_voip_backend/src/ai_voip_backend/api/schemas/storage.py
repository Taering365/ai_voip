"""存储配置响应模型。"""

from __future__ import annotations

from pydantic import BaseModel


class StorageProfileItem(BaseModel):
    """描述存储配置列表中的单条数据。"""

    id: int
    profile_code: str
    profile_name: str
    storage_backend: str
    is_default: bool
    root_dir: str | None
    endpoint: str | None
    bucket_name: str | None
    access_key: str | None
    secret_key: str | None
    region_name: str | None
    extra_config: dict


class StorageProbeResponse(BaseModel):
    """描述存储检测结果。"""

    status: str
    message: str
    details: dict
