"""存储配置服务。"""

from __future__ import annotations

import io
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import BotoCoreError, ClientError
from psycopg import Connection

from .common import jsonb_value, soft_delete_by_id
from ..storage import LocalStorageProvider, S3CompatibleStorageProvider, StorageProvider


DEFAULT_LOCAL_ROOT_DIR = "data/recorder"


def create_storage_profile(connection: Connection, payload: dict) -> dict:
    """创建存储配置。

    参数:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        payload: 创建存储配置需要的字段字典。

    返回:
        dict: 返回创建完成后的存储配置字典。
    """

    normalized_payload = normalize_storage_profile_payload(payload)
    params = dict(normalized_payload)
    params["extra_config"] = jsonb_value(params.get("extra_config", {}))
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO storage_profile (
                profile_code, profile_name, storage_backend, is_default,
                root_dir, endpoint, bucket_name, access_key, secret_key,
                region_name, extra_config
            ) VALUES (
                %(profile_code)s, %(profile_name)s, %(storage_backend)s, %(is_default)s,
                %(root_dir)s, %(endpoint)s, %(bucket_name)s, %(access_key)s, %(secret_key)s,
                %(region_name)s, %(extra_config)s
            )
            RETURNING id
            """,
            params,
        )
        profile_id = cursor.fetchone()[0]
    connection.commit()
    if normalized_payload.get("is_default"):
        set_default_storage_profile(connection, profile_id)
    return get_storage_profile_by_id(connection, profile_id)  # type: ignore[return-value]


def get_storage_profile_by_id(connection: Connection, profile_id: int) -> dict | None:
    """根据主键查询存储配置。

    参数:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        profile_id: 存储配置主键。

    返回:
        dict | None: 找到时返回存储配置字典，否则返回 None。
    """

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                id,
                profile_code,
                profile_name,
                storage_backend,
                is_default,
                root_dir,
                endpoint,
                bucket_name,
                access_key,
                secret_key,
                region_name,
                extra_config
            FROM storage_profile
            WHERE deleted_at IS NULL
              AND id = %(profile_id)s
            LIMIT 1
            """,
            {"profile_id": profile_id},
        )
        row = cursor.fetchone()
    if row is None:
        return None
    return _build_storage_profile_item(row)


def update_storage_profile(connection: Connection, profile_id: int, payload: dict) -> dict | None:
    """更新存储配置。

    参数:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        profile_id: 存储配置主键。
        payload: 更新存储配置需要的字段字典。

    返回:
        dict | None: 更新成功时返回存储配置字典，否则返回 None。
    """

    current_profile = get_storage_profile_by_id(connection, profile_id)
    if current_profile is None:
        return None
    normalized_payload = normalize_storage_profile_payload(payload, current_profile)
    params = dict(normalized_payload)
    params["profile_id"] = profile_id
    params["extra_config"] = jsonb_value(params.get("extra_config", {}))
    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE storage_profile
            SET profile_name = %(profile_name)s,
                storage_backend = %(storage_backend)s,
                is_default = %(is_default)s,
                root_dir = %(root_dir)s,
                endpoint = %(endpoint)s,
                bucket_name = %(bucket_name)s,
                access_key = %(access_key)s,
                secret_key = %(secret_key)s,
                region_name = %(region_name)s,
                extra_config = %(extra_config)s,
                updated_at = NOW()
            WHERE id = %(profile_id)s
              AND deleted_at IS NULL
            """,
            params,
        )
        updated = cursor.rowcount > 0
    connection.commit()
    if not updated:
        return None
    if normalized_payload.get("is_default"):
        set_default_storage_profile(connection, profile_id)
    return get_storage_profile_by_id(connection, profile_id)


def set_default_storage_profile(connection: Connection, profile_id: int) -> dict | None:
    """设置默认存储配置。

    参数:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        profile_id: 需要设为默认的存储配置主键。

    返回:
        dict | None: 设置成功时返回默认存储配置字典，否则返回 None。
    """

    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE storage_profile
            SET is_default = FALSE,
                updated_at = NOW()
            WHERE deleted_at IS NULL
            """
        )
        cursor.execute(
            """
            UPDATE storage_profile
            SET is_default = TRUE,
                updated_at = NOW()
            WHERE id = %(profile_id)s
              AND deleted_at IS NULL
            """,
            {"profile_id": profile_id},
        )
        updated = cursor.rowcount > 0
    connection.commit()
    if not updated:
        return None
    return get_storage_profile_by_id(connection, profile_id)


def delete_storage_profile(connection: Connection, profile_id: int) -> bool:
    """软删除存储配置。

    参数:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        profile_id: 存储配置主键。

    返回:
        bool: 删除成功返回 True，否则返回 False。
    """

    return soft_delete_by_id(connection, "storage_profile", profile_id)


def list_storage_profiles(connection: Connection) -> list[dict]:
    """查询全部存储配置列表。

    参数:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。

    返回:
        list[dict]: 返回存储配置字典列表。
    """

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                id,
                profile_code,
                profile_name,
                storage_backend,
                is_default,
                root_dir,
                endpoint,
                bucket_name,
                access_key,
                secret_key,
                region_name,
                extra_config
            FROM storage_profile
            WHERE deleted_at IS NULL
            ORDER BY is_default DESC, id ASC
            """
        )
        rows = cursor.fetchall()
    return [_build_storage_profile_item(row) for row in rows]


def get_default_storage_profile(connection: Connection) -> dict | None:
    """查询默认存储配置。

    参数:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。

    返回:
        dict | None: 找到默认存储配置时返回字典，否则返回 None。
    """

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                id,
                profile_code,
                profile_name,
                storage_backend,
                is_default,
                root_dir,
                endpoint,
                bucket_name,
                access_key,
                secret_key,
                region_name,
                extra_config
            FROM storage_profile
            WHERE deleted_at IS NULL
              AND is_default = TRUE
            ORDER BY id ASC
            LIMIT 1
            """
        )
        row = cursor.fetchone()
    if row is None:
        return None
    return _build_storage_profile_item(row)


def probe_storage_profile(payload: dict, project_root: Path) -> dict:
    """检测存储配置是否可用。

    参数:
        payload: 需要检测的存储配置字段字典。
        project_root: 当前后端项目根目录，用于解析相对本地目录。

    返回:
        dict: 返回检测结果字典，包含状态、消息和关键细节。
    """

    normalized_payload = normalize_storage_profile_payload(payload)
    if normalized_payload["storage_backend"] == "local":
        return probe_local_storage_profile(normalized_payload, project_root)
    if normalized_payload["storage_backend"] == "s3_compatible":
        return probe_s3_storage_profile(normalized_payload)
    raise ValueError("不支持的存储后端")


def probe_local_storage_profile(payload: dict, project_root: Path) -> dict:
    """检测本地存储配置是否可用。

    参数:
        payload: 规范化后的本地存储配置字段字典。
        project_root: 当前后端项目根目录，用于解析相对目录。

    返回:
        dict: 本地检测结果字典。
    """

    root_dir = Path(payload["root_dir"] or DEFAULT_LOCAL_ROOT_DIR)
    if not root_dir.is_absolute():
        root_dir = (project_root / root_dir).resolve()
    root_dir.mkdir(parents=True, exist_ok=True)
    probe_file = root_dir / f".storage_probe_{uuid4().hex}.tmp"
    probe_file.write_text("probe", encoding="utf-8")
    probe_file.unlink(missing_ok=True)
    return {
        "status": "success",
        "message": "本地存储目录可写入",
        "details": {
            "resolved_root_dir": str(root_dir),
        },
    }


def probe_s3_storage_profile(payload: dict) -> dict:
    """检测 S3 兼容存储配置是否可用。

    参数:
        payload: 规范化后的 S3 兼容存储配置字段字典。

    返回:
        dict: S3 检测结果字典。
    """

    endpoint = str(payload.get("endpoint") or "").strip()
    bucket_name = str(payload.get("bucket_name") or "").strip()
    access_key = str(payload.get("access_key") or "").strip()
    secret_key = str(payload.get("secret_key") or "").strip()
    region_name = str(payload.get("region_name") or "").strip() or "us-east-1"
    extra_config = payload.get("extra_config") or {}
    use_ssl = bool(extra_config.get("use_ssl", endpoint.startswith("https://")))
    force_path_style = bool(extra_config.get("force_path_style", True))
    auto_create_bucket = bool(extra_config.get("auto_create_bucket", False))
    endpoint_url = build_s3_endpoint_url(endpoint, use_ssl)

    if not endpoint or not bucket_name or not access_key or not secret_key:
        raise ValueError("S3 兼容存储检测需要填写 Endpoint、Bucket、Access Key 和 Secret Key")

    client = boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        region_name=region_name,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=BotoConfig(
            signature_version="s3v4",
            s3={"addressing_style": "path" if force_path_style else "auto"},
        ),
    )

    try:
        client.list_buckets()
        try:
            client.head_bucket(Bucket=bucket_name)
        except ClientError:
            if not auto_create_bucket:
                raise
            client.create_bucket(Bucket=bucket_name)

        probe_key = f"storage-probe/{uuid4().hex}.txt"
        client.put_object(Bucket=bucket_name, Key=probe_key, Body=io.BytesIO(b"probe"))
        client.delete_object(Bucket=bucket_name, Key=probe_key)
    except (ClientError, BotoCoreError) as exc:
        return {
            "status": "failed",
            "message": f"S3 兼容存储检测失败：{exc}",
            "details": {
                "endpoint_url": endpoint_url,
                "bucket_name": bucket_name,
                "region_name": region_name,
            },
        }

    return {
        "status": "success",
        "message": "S3 兼容存储检测成功",
        "details": {
            "endpoint_url": endpoint_url,
            "bucket_name": bucket_name,
            "region_name": region_name,
            "force_path_style": force_path_style,
        },
    }


def normalize_storage_profile_payload(payload: dict, current_profile: dict | None = None) -> dict:
    """规范化存储配置字段，补齐默认值并兼容旧数据。

    参数:
        payload: 前端提交的原始存储配置字段字典。
        current_profile: 当前数据库已有的存储配置对象，更新时用于继承旧值。

    返回:
        dict: 规范化后的存储配置字段字典。
    """

    current_profile = current_profile or {}
    current_extra_config = current_profile.get("extra_config") or {}
    payload_extra_config = payload.get("extra_config") or {}
    extra_config = {**current_extra_config, **payload_extra_config}
    storage_backend = str(payload.get("storage_backend") or current_profile.get("storage_backend") or "local").strip()
    if storage_backend == "local":
        root_dir = str(payload.get("root_dir") or current_profile.get("root_dir") or DEFAULT_LOCAL_ROOT_DIR).strip()
        endpoint = None
        bucket_name = None
        access_key = None
        secret_key = None
        region_name = None
        extra_config = {
            **extra_config,
            "subdirectories": {
                "recordings": "recordings",
                "tts_cache": "tts_cache",
                "transcripts": "transcripts",
            },
            "public_base_url": normalize_optional_text(extra_config.get("public_base_url")),
        }
    else:
        root_dir = None
        endpoint = normalize_optional_text(payload.get("endpoint") or current_profile.get("endpoint"))
        bucket_name = normalize_optional_text(payload.get("bucket_name") or current_profile.get("bucket_name"))
        access_key = normalize_optional_text(payload.get("access_key") or current_profile.get("access_key"))
        secret_key = normalize_optional_text(payload.get("secret_key") or current_profile.get("secret_key"))
        region_name = normalize_optional_text(payload.get("region_name") or current_profile.get("region_name") or "us-east-1")
        extra_config = {
            **extra_config,
            "use_ssl": bool(extra_config.get("use_ssl", endpoint.startswith("https://") if endpoint else False)),
            "force_path_style": bool(extra_config.get("force_path_style", True)),
            "object_prefix": str(extra_config.get("object_prefix") or "ai-voip").strip(),
            "public_base_url": normalize_optional_text(extra_config.get("public_base_url")),
            "auto_create_bucket": bool(extra_config.get("auto_create_bucket", False)),
        }

    return {
        "profile_code": str(payload.get("profile_code") or current_profile.get("profile_code") or build_storage_profile_code(storage_backend)),
        "profile_name": str(payload.get("profile_name") or current_profile.get("profile_name") or "").strip(),
        "storage_backend": storage_backend,
        "is_default": bool(payload.get("is_default", current_profile.get("is_default", False))),
        "root_dir": root_dir,
        "endpoint": endpoint,
        "bucket_name": bucket_name,
        "access_key": access_key,
        "secret_key": secret_key,
        "region_name": region_name,
        "extra_config": extra_config,
    }


def build_s3_endpoint_url(endpoint: str, use_ssl: bool) -> str:
    """构造 S3 兼容访问地址。

    参数:
        endpoint: 用户填写的 Endpoint，可能不带协议头。
        use_ssl: 是否使用 HTTPS 协议。

    返回:
        str: 带协议头的完整 endpoint_url。
    """

    endpoint_text = endpoint.strip()
    if endpoint_text.startswith("http://") or endpoint_text.startswith("https://"):
        return endpoint_text
    return f"{'https' if use_ssl else 'http'}://{endpoint_text}"


def build_storage_profile_code(storage_backend: str) -> str:
    """生成存储配置编码。

    参数:
        storage_backend: 当前存储后端类型。

    返回:
        str: 自动生成的唯一配置编码。
    """

    return f"{storage_backend}_{uuid4().hex[:24]}"


def build_storage_provider(storage_profile: dict, project_root: Path) -> StorageProvider:
    """根据存储配置构建实际可用的存储提供者。

    参数:
        storage_profile: 当前选中的存储配置对象。
        project_root: 当前后端项目根目录，用于解析相对本地路径。

    返回:
        StorageProvider: 可直接执行保存、删除、检查的存储提供者实例。
    """

    storage_backend = str(storage_profile.get("storage_backend") or "local")
    if storage_backend == "local":
        root_dir = Path(str(storage_profile.get("root_dir") or DEFAULT_LOCAL_ROOT_DIR))
        if not root_dir.is_absolute():
            root_dir = (project_root / root_dir).resolve()
        extra_config = storage_profile.get("extra_config") or {}
        return LocalStorageProvider(
            str(root_dir),
            public_base_url=normalize_optional_text(extra_config.get("public_base_url")),
        )

    extra_config = storage_profile.get("extra_config") or {}
    endpoint_url = build_s3_endpoint_url(
        str(storage_profile.get("endpoint") or ""),
        bool(extra_config.get("use_ssl", False)),
    )
    return S3CompatibleStorageProvider(
        endpoint_url=endpoint_url,
        bucket_name=str(storage_profile.get("bucket_name") or ""),
        access_key=str(storage_profile.get("access_key") or ""),
        secret_key=str(storage_profile.get("secret_key") or ""),
        region_name=str(storage_profile.get("region_name") or "us-east-1"),
        force_path_style=bool(extra_config.get("force_path_style", True)),
        public_base_url=normalize_optional_text(extra_config.get("public_base_url")),
    )


def resolve_storage_target_key(storage_profile: dict, category: str, filename: str) -> str:
    """根据存储配置和业务分类构造统一存储键。

    参数:
        storage_profile: 当前选中的存储配置对象。
        category: 业务分类，例如 recordings、tts_cache、transcripts。
        filename: 最终写入的文件名。

    返回:
        str: 统一的逻辑存储键。
    """

    extra_config = storage_profile.get("extra_config") or {}
    subdirectories = extra_config.get("subdirectories") or {}
    category_dir = str(subdirectories.get(category) or category).strip("/")
    prefix = str(extra_config.get("object_prefix") or "").strip("/")
    current_time = datetime.now()
    date_part = Path("assets") / category_dir / f"{current_time:%Y}" / f"{current_time:%m}" / f"{current_time:%d}"
    if prefix:
        return str(Path(prefix) / date_part / filename).replace("\\", "/")
    return str(date_part / filename).replace("\\", "/")


def normalize_optional_text(value: object | None) -> str | None:
    """统一清洗可选文本字段。

    参数:
        value: 原始文本值，可能为 None、空串或其它可转字符串对象。

    返回:
        str | None: 去空格后的文本；为空时返回 None。
    """

    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _build_storage_profile_item(row: tuple) -> dict:
    """将数据库查询结果组装为存储配置字典。

    参数:
        row: 数据库返回的单行元组数据。

    返回:
        dict: 返回适合接口直接响应的存储配置字典。
    """

    extra_config = row[11] or {}
    return {
        "id": row[0],
        "profile_code": row[1],
        "profile_name": row[2],
        "storage_backend": row[3],
        "is_default": row[4],
        "root_dir": row[5],
        "endpoint": row[6],
        "bucket_name": row[7],
        "access_key": row[8],
        "secret_key": row[9],
        "region_name": row[10],
        "extra_config": extra_config,
    }
