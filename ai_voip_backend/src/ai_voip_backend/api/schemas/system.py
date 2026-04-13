"""系统配置响应模型。"""

from __future__ import annotations

from pydantic import BaseModel


class HealthCheckData(BaseModel):
    """描述健康检查结果。

    Attributes:
        service: 当前服务名称。
        database: 当前连接的数据库名。
        db_version: PostgreSQL 版本字符串。
    """

    service: str
    database: str
    db_version: str


class ConfigItem(BaseModel):
    """描述单条系统配置。

    Attributes:
        config_key: 系统配置键名。
        config_value: 系统配置对应的 JSON 值。
        description: 系统配置说明。
    """

    config_key: str
    config_value: object
    description: str | None
