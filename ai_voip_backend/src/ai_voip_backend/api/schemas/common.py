"""通用响应模型。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ApiResponse(BaseModel):
    """定义统一接口响应结构。

    Attributes:
        success: 标记接口调用是否成功。
        message: 返回给前端的摘要消息。
        data: 返回的业务数据对象。
    """

    success: bool = True
    message: str = "ok"
    data: Any = Field(default=None)


class ApiErrorResponse(BaseModel):
    """定义统一错误响应结构。

    Attributes:
        success: 固定为 False，标记本次接口调用失败。
        message: 返回给前端的错误摘要信息。
        error_code: 业务错误码，便于前端和日志统一识别。
        data: 错误附加数据，通常为字段校验细节或空值。
    """

    success: bool = False
    message: str
    error_code: str
    data: Any = Field(default=None)
