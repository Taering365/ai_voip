"""健康检查接口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from psycopg import Connection

from ..dependencies import get_db_connection
from ..schemas.common import ApiResponse
from ..schemas.system import HealthCheckData
from ...services.system_service import get_database_status

router = APIRouter()


@router.get("/health", response_model=ApiResponse)
def health_check(connection: Connection = Depends(get_db_connection)) -> ApiResponse:
    """执行服务与数据库健康检查。

    Args:
        connection: 通过 FastAPI 依赖注入得到的 PostgreSQL 连接对象。

    Returns:
        ApiResponse: 返回服务名称、数据库名和 PostgreSQL 版本等健康信息。
    """

    database_name, version_text = get_database_status(connection)
    return ApiResponse(
        data=HealthCheckData(
            service="ai-voip-backend",
            database=database_name,
            db_version=version_text,
        )
    )
