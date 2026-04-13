"""项目日志配置。"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


class MaxLevelFilter(logging.Filter):
    """限制日志处理器只接收不高于指定级别的日志。"""

    def __init__(self, max_level: int) -> None:
        """初始化日志级别过滤器。

        Args:
            max_level: 允许通过处理器的最高日志级别。
        """

        super().__init__()
        self.max_level = max_level

    def filter(self, record: logging.LogRecord) -> bool:
        """判断日志记录是否允许通过当前过滤器。

        Args:
            record: 当前待处理的日志记录对象。

        Returns:
            bool: 日志级别不高于限制时返回 True，否则返回 False。
        """

        return record.levelno <= self.max_level


def setup_logging(project_root: Path) -> None:
    """初始化项目日志配置。

    Args:
        project_root: 后端项目根目录，用于定位日志输出目录。

    Returns:
        None: 该函数只负责初始化日志系统，不返回业务结果。
    """

    log_dir = project_root / "log"
    log_dir.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    info_handler = RotatingFileHandler(
        log_dir / "info.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=10,
        encoding="utf-8",
    )
    info_handler.setLevel(logging.INFO)
    info_handler.setFormatter(formatter)
    info_handler.addFilter(MaxLevelFilter(logging.INFO))

    error_handler = RotatingFileHandler(
        log_dir / "error.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=10,
        encoding="utf-8",
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    if root_logger.handlers:
        root_logger.handlers.clear()

    root_logger.addHandler(info_handler)
    root_logger.addHandler(error_handler)

    logging.getLogger("uvicorn.access").handlers.clear()
    logging.getLogger("uvicorn.error").propagate = True
    logging.getLogger("uvicorn.access").propagate = True
    logging.getLogger("httpx").setLevel(logging.WARNING)
