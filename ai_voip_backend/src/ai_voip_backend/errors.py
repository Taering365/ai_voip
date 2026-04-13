"""统一错误响应与异常处理。"""

from __future__ import annotations

import logging

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from psycopg.errors import CheckViolation, ForeignKeyViolation, IntegrityError, NotNullViolation, UniqueViolation
from starlette import status

from .api.schemas.common import ApiErrorResponse


logger = logging.getLogger("ai_voip.error")


class AppError(Exception):
    """定义项目内部业务异常。

    Attributes:
        error_code: 业务错误码。
        message: 面向前端的错误信息。
        status_code: HTTP 状态码。
        data: 错误附加数据。
    """

    def __init__(
        self,
        error_code: str,
        message: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        data: object | None = None,
    ) -> None:
        """初始化业务异常对象。

        Args:
            error_code: 业务错误码。
            message: 面向前端的错误信息。
            status_code: HTTP 状态码。
            data: 错误附加数据。
        """

        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.status_code = status_code
        self.data = data


def build_error_response(
    *,
    status_code: int,
    error_code: str,
    message: str,
    data: object | None = None,
) -> JSONResponse:
    """构造统一错误响应。

    Args:
        status_code: HTTP 状态码。
        error_code: 业务错误码。
        message: 面向前端的错误信息。
        data: 错误附加数据。

    Returns:
        JSONResponse: 返回标准化 JSON 错误响应对象。
    """

    response = JSONResponse(
        status_code=status_code,
        content=ApiErrorResponse(
            message=message,
            error_code=error_code,
            data=data,
        ).model_dump(),
    )
    response.headers["X-Error-Code"] = error_code
    return response


async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    """处理项目内部业务异常。"""

    return build_error_response(
        status_code=exc.status_code,
        error_code=exc.error_code,
        message=exc.message,
        data=exc.data,
    )


async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
    """处理 FastAPI HTTP 异常。"""

    error_code = "http_error"
    message = str(exc.detail)
    if exc.status_code == status.HTTP_401_UNAUTHORIZED:
        error_code = "unauthorized"
    elif exc.status_code == status.HTTP_403_FORBIDDEN:
        error_code = "forbidden"
    elif exc.status_code == status.HTTP_404_NOT_FOUND:
        error_code = "not_found"
    elif exc.status_code == status.HTTP_409_CONFLICT:
        error_code = "conflict"
    return build_error_response(
        status_code=exc.status_code,
        error_code=error_code,
        message=message,
    )


async def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    """处理请求参数校验异常。"""

    return build_error_response(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        error_code="validation_error",
        message="请求参数校验失败",
        data=exc.errors(),
    )


async def integrity_exception_handler(_: Request, exc: IntegrityError) -> JSONResponse:
    """处理数据库完整性约束异常。"""

    error_code = "integrity_error"
    message = "数据库约束校验失败"
    if isinstance(exc, UniqueViolation):
        error_code = "db_unique_violation"
        message = "数据唯一约束冲突"
    elif isinstance(exc, ForeignKeyViolation):
        error_code = "db_foreign_key_violation"
        message = "关联数据不存在或无法引用"
    elif isinstance(exc, CheckViolation):
        error_code = "db_check_violation"
        message = "数据检查约束不通过"
    elif isinstance(exc, NotNullViolation):
        error_code = "db_not_null_violation"
        message = "缺少必填字段"
    return build_error_response(
        status_code=status.HTTP_400_BAD_REQUEST,
        error_code=error_code,
        message=message,
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """处理未显式分类的服务器内部异常。"""

    logger.error(
        "Unhandled exception: method=%s path=%s query=%s detail=%r",
        request.method,
        request.url.path,
        request.url.query,
        exc,
        exc_info=True,
    )

    return build_error_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        error_code="internal_server_error",
        message="服务器内部错误",
        data={"detail": repr(exc)},
    )
