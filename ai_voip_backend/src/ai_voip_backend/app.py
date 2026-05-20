"""FastAPI 应用入口。"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from psycopg.errors import IntegrityError

from .api.router import api_router
from .api.dependencies import get_project_root
from .errors import (
    AppError,
    app_error_handler,
    generic_exception_handler,
    http_exception_handler,
    integrity_exception_handler,
    validation_exception_handler,
)
from .config import load_postgres_config, load_sip_runtime_config
from .logging_setup import setup_logging
from .middleware import RequestLogMiddleware
from .services.storage_service import DEFAULT_LOCAL_ROOT_DIR
from .services.task_runtime_scheduler import TaskRuntimeScheduler


def build_cors_origins() -> list[str]:
    """构造允许访问后端接口的前端来源列表。

    Returns:
        list[str]: 返回本地开发环境下允许跨域访问的前端来源地址列表。
    """

    return [
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://0.0.0.0:5173",
        "http://127.0.0.1:3900",
        "http://localhost:3900",
        "http://0.0.0.0:3900",
    ]


def create_app() -> FastAPI:
    """创建 FastAPI 应用实例。

    Returns:
        FastAPI: 返回注册好路由与基础元信息的应用对象。
    """

    setup_logging(get_project_root())
    app = FastAPI(
        title="AI VoIP Backend",
        version="0.1.0",
        description="开源智能外呼平台后端接口。",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=build_cors_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestLogMiddleware)
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(IntegrityError, integrity_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)
    app.include_router(api_router, prefix="/api/v1")
    register_local_media_mount(app)
    register_runtime_scheduler(app)
    return app


def register_local_media_mount(app: FastAPI) -> None:
    """为本地存储目录注册静态文件访问入口。

    参数:
        app: 当前 FastAPI 应用实例。

    返回:
        None: 注册完成后不返回业务数据。
    """

    project_root = get_project_root()
    local_root_dir = (project_root / Path(DEFAULT_LOCAL_ROOT_DIR)).resolve()
    local_root_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/local-media", StaticFiles(directory=str(local_root_dir)), name="local-media")


def register_runtime_scheduler(app: FastAPI) -> None:
    """为当前 FastAPI 应用注册后台任务调度器。

    参数:
        app: 当前 FastAPI 应用实例。

    返回:
        None: 注册完成后不返回业务数据。
    """

    project_root = get_project_root()
    runtime_config = load_sip_runtime_config(project_root)
    if not runtime_config.enabled:
        return
    scheduler = TaskRuntimeScheduler(
        postgres_config=load_postgres_config(project_root),
        runtime_config=runtime_config,
        project_root=project_root,
    )
    app.state.task_runtime_scheduler = scheduler
    app.router.add_event_handler("startup", scheduler.start)
    app.router.add_event_handler("shutdown", scheduler.stop)
