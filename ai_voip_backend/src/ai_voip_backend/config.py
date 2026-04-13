"""项目配置加载。"""

from __future__ import annotations

import os
import hashlib
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class PostgresConfig:
    """封装 PostgreSQL 连接配置。

    Attributes:
        host: PostgreSQL 服务地址。
        port: PostgreSQL 服务端口。
        user: PostgreSQL 登录用户名。
        password: PostgreSQL 登录密码。
        database: PostgreSQL 数据库名称。
        sslmode: PostgreSQL SSL 模式。
    """

    host: str
    port: int
    user: str
    password: str
    database: str
    sslmode: str = "prefer"


@dataclass(slots=True)
class JwtConfig:
    """封装 JWT 签发配置。

    Attributes:
        secret: JWT 签名密钥。
        algorithm: JWT 签名算法。
        expire_minutes: JWT 默认有效时长，单位分钟。
    """

    secret: str
    algorithm: str = "HS256"
    expire_minutes: int = 1440
    token_encryption_key: str = "<CHANGE_ME>"


@dataclass(slots=True)
class SipRuntimeConfig:
    """封装 SIP 运行时执行器配置。

    Attributes:
        enabled: 是否启用基于 uSIP 的 SIP 外呼执行器。
        transport: 当前执行器默认使用的 SIP 传输协议。
        local_port: 本地 SIP 监听端口，0 表示由系统自动分配。
        poll_interval_seconds: 任务调度器轮询数据库的时间间隔，单位秒。
        max_parallel_calls: 当前进程允许并发处理的最大真实通话数。
        audio_cache_dir: 运行时用于缓存 TTS 音频和下载音频的本地目录。
    """

    enabled: bool = False
    transport: str = "udp"
    local_port: int = 0
    poll_interval_seconds: int = 5
    max_parallel_calls: int = 8
    audio_cache_dir: str = "data/runtime_audio"


def parse_env_file(env_file: Path) -> dict[str, str]:
    """解析简单的 .env 文件内容。

    Args:
        env_file: 需要读取的 .env 文件路径。

    Returns:
        dict[str, str]: 返回解析后的键值对字典，不存在时返回空字典。
    """

    if not env_file.exists():
        return {}

    values: dict[str, str] = {}
    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def load_env_overrides(project_root: Path) -> dict[str, str]:
    """按优先级读取本地环境文件覆盖项。

    Args:
        project_root: 当前后端项目根目录。

    Returns:
        dict[str, str]: 返回合并后的环境变量覆盖字典。
    """

    merged: dict[str, str] = {}
    for filename in (".env", ".env.local"):
        merged.update(parse_env_file(project_root / filename))
    return merged


def get_setting(env_key: str, default: str, project_root: Path) -> str:
    """获取环境配置值。

    Args:
        env_key: 环境变量名称。
        default: 当环境中不存在时使用的默认值。
        project_root: 当前后端项目根目录。

    Returns:
        str: 返回最终配置值。
    """

    if env_key in os.environ:
        return os.environ[env_key]
    overrides = load_env_overrides(project_root)
    return overrides.get(env_key, default)


def load_postgres_config(project_root: Path | None = None) -> PostgresConfig:
    """加载 PostgreSQL 连接配置。

    Args:
        project_root: 当前后端项目根目录，未传时自动从代码位置推导。

    Returns:
        PostgresConfig: 返回可用于数据库连接的配置对象。
    """

    resolved_root = project_root or Path(__file__).resolve().parents[2]
    return PostgresConfig(
        host=get_setting("AIVOIP_PG_HOST", "127.0.0.1", resolved_root),
        port=int(get_setting("AIVOIP_PG_PORT", "5432", resolved_root)),
        user=get_setting("AIVOIP_PG_USER", "postgres", resolved_root),
        password=get_setting("AIVOIP_PG_PASSWORD", "<CHANGE_ME>", resolved_root),
        database=get_setting("AIVOIP_PG_DATABASE", "ai_voip", resolved_root),
        sslmode=get_setting("AIVOIP_PG_SSLMODE", "prefer", resolved_root),
    )


def load_jwt_config(project_root: Path | None = None) -> JwtConfig:
    """加载 JWT 鉴权配置。

    Args:
        project_root: 当前后端项目根目录，未传时自动从代码位置推导。

    Returns:
        JwtConfig: 返回 JWT 配置对象。
    """

    resolved_root = project_root or Path(__file__).resolve().parents[2]
    return JwtConfig(
        secret=get_setting("AIVOIP_JWT_SECRET", "<CHANGE_ME_TO_AT_LEAST_32_CHARS>", resolved_root),
        expire_minutes=int(get_setting("AIVOIP_JWT_EXPIRE_MINUTES", "1440", resolved_root)),
        token_encryption_key=get_setting(
            "AIVOIP_TOKEN_ENCRYPTION_KEY",
            "<CHANGE_ME_TO_AT_LEAST_32_CHARS>",
            resolved_root,
        ),
    )


def load_sip_runtime_config(project_root: Path | None = None) -> SipRuntimeConfig:
    """加载 SIP 运行时执行器配置。

    Args:
        project_root: 当前后端项目根目录，未传时自动从代码位置推导。

    Returns:
        SipRuntimeConfig: 返回 SIP 运行时配置对象。
    """

    resolved_root = project_root or Path(__file__).resolve().parents[2]
    return SipRuntimeConfig(
        enabled=get_setting("AIVOIP_SIP_RUNTIME_ENABLED", "0", resolved_root).strip() in {"1", "true", "TRUE", "yes"},
        transport=get_setting("AIVOIP_SIP_RUNTIME_TRANSPORT", "udp", resolved_root).strip().lower(),
        local_port=int(get_setting("AIVOIP_SIP_RUNTIME_LOCAL_PORT", "0", resolved_root)),
        poll_interval_seconds=max(1, int(get_setting("AIVOIP_SIP_RUNTIME_POLL_INTERVAL", "5", resolved_root))),
        max_parallel_calls=max(1, int(get_setting("AIVOIP_SIP_RUNTIME_MAX_PARALLEL", "8", resolved_root))),
        audio_cache_dir=get_setting("AIVOIP_SIP_RUNTIME_AUDIO_CACHE_DIR", "data/runtime_audio", resolved_root),
    )


def build_token_cipher_key(jwt_config: JwtConfig) -> bytes:
    """根据配置生成用于 AES-GCM 的固定长度密钥。

    Args:
        jwt_config: JWT 与令牌加密配置对象。

    Returns:
        bytes: 返回长度固定为 32 字节的 AES-GCM 密钥。
    """

    raw_key = jwt_config.token_encryption_key
    if not raw_key or raw_key == "<CHANGE_ME>":
        raw_key = jwt_config.secret
    return hashlib.sha256(raw_key.encode("utf-8")).digest()
