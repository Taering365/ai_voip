"""请求日志中间件。"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from uuid import uuid4

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from .api.dependencies import get_project_root
from .auth import decode_access_token
from .config import load_jwt_config


class RequestLogMiddleware(BaseHTTPMiddleware):
    """记录请求访问日志和异常日志。"""

    def __init__(self, app) -> None:
        """初始化请求日志中间件。

        Args:
            app: FastAPI 或 Starlette 应用实例。
        """

        super().__init__(app)
        self.logger = logging.getLogger("ai_voip.request")
        self.project_root: Path = get_project_root()
        self.jwt_config = load_jwt_config(self.project_root)

    async def dispatch(self, request: Request, call_next) -> Response:
        """拦截请求并记录访问日志。

        Args:
            request: 当前 HTTP 请求对象。
            call_next: 下游处理函数。

        Returns:
            Response: 返回下游生成的 HTTP 响应对象。
        """

        request_id = str(uuid4())
        started_at = time.perf_counter()
        user_identity = self._extract_user_identity(request)
        try:
            response = await call_next(request)
        except Exception as exc:  # noqa: BLE001
            duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
            self.logger.error(
                "request_id=%s user=%s method=%s path=%s query=%s status=%s error_code=%s duration_ms=%s client_ip=%s exception=%r",
                request_id,
                user_identity,
                request.method,
                request.url.path,
                request.url.query,
                500,
                "unhandled_exception",
                duration_ms,
                request.client.host if request.client else "-",
                exc,
                exc_info=True,
            )
            raise
        duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
        error_code = response.headers.get("X-Error-Code", "")
        log_message = (
            "request_id=%s user=%s method=%s path=%s query=%s status=%s error_code=%s duration_ms=%s client_ip=%s"
        )
        log_args = (
            request_id,
            user_identity,
            request.method,
            request.url.path,
            request.url.query,
            response.status_code,
            error_code or "-",
            duration_ms,
            request.client.host if request.client else "-",
        )

        if response.status_code >= 400:
            self.logger.error(log_message, *log_args)
        else:
            self.logger.info(log_message, *log_args)
        response.headers["X-Request-Id"] = request_id
        return response

    def _extract_user_identity(self, request: Request) -> str:
        """从请求头中解析当前请求用户标识。

        Args:
            request: 当前 HTTP 请求对象。

        Returns:
            str: 返回用户名、匿名标记或无效令牌标记。
        """

        authorization = request.headers.get("Authorization", "").strip()
        if not authorization.startswith("Bearer "):
            return "anonymous"

        token = authorization.removeprefix("Bearer ").strip()
        if not token:
            return "anonymous"

        try:
            payload = decode_access_token(self.jwt_config, token)
        except Exception:  # noqa: BLE001
            return "invalid_token"
        return str(payload.get("username") or payload.get("sub") or "unknown")
