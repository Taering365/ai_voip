"""S3 兼容对象存储实现。"""

from __future__ import annotations

from typing import BinaryIO

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import BotoCoreError, ClientError

from .base import StorageObject, StorageProvider


class S3CompatibleStorageProvider(StorageProvider):
    """实现基于 S3 兼容接口的对象存储。"""

    def __init__(
        self,
        endpoint_url: str,
        bucket_name: str,
        access_key: str,
        secret_key: str,
        region_name: str = "us-east-1",
        force_path_style: bool = True,
        public_base_url: str | None = None,
    ) -> None:
        """初始化 S3 兼容对象存储提供者。

        参数:
            endpoint_url: 完整的对象存储访问地址。
            bucket_name: 默认使用的桶名称。
            access_key: 对象存储访问账号。
            secret_key: 对象存储访问密码。
            region_name: 对象存储区域名称。
            force_path_style: 是否强制使用路径风格访问。
            public_base_url: 可选的公开访问前缀，用于直接拼接下载地址。
        """

        self.endpoint_url = endpoint_url
        self.bucket_name = bucket_name
        self.public_base_url = public_base_url.rstrip("/") if public_base_url else None
        self.client = boto3.client(
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

    def save(
        self,
        file_stream: BinaryIO,
        target_key: str,
        meta: dict[str, str] | None = None,
    ) -> StorageObject:
        """保存文件到对象存储。

        参数:
            file_stream: 文件二进制流对象。
            target_key: 逻辑存储键，同时会作为对象键使用。
            meta: 文件相关的扩展元数据，可为空。

        返回:
            StorageObject: 返回对象存储结果对象。
        """

        extra_args = {"Metadata": meta or {}}
        self.client.upload_fileobj(file_stream, self.bucket_name, target_key, ExtraArgs=extra_args)
        return StorageObject(
            storage_backend="s3_compatible",
            storage_key=target_key,
            local_path=None,
            object_key=target_key,
            extra_meta=meta or {},
        )

    def delete(self, storage_key: str) -> bool:
        """删除对象存储中的文件。

        参数:
            storage_key: 业务统一使用的逻辑存储键。

        返回:
            bool: 删除请求成功返回 True，失败返回 False。
        """

        try:
            self.client.delete_object(Bucket=self.bucket_name, Key=storage_key)
        except (ClientError, BotoCoreError):
            return False
        return True

    def exists(self, storage_key: str) -> bool:
        """检查对象存储中的文件是否存在。

        参数:
            storage_key: 业务统一使用的逻辑存储键。

        返回:
            bool: 文件存在返回 True，否则返回 False。
        """

        try:
            self.client.head_object(Bucket=self.bucket_name, Key=storage_key)
        except (ClientError, BotoCoreError):
            return False
        return True

    def resolve_path(self, storage_key: str) -> str:
        """解析对象存储中的实际定位路径。

        参数:
            storage_key: 业务统一使用的逻辑存储键。

        返回:
            str: 返回对象键字符串。
        """

        return storage_key

    def build_download_url(self, storage_key: str, expires_in: int) -> str | None:
        """构建对象存储下载地址或签名地址。

        参数:
            storage_key: 业务统一使用的逻辑存储键。
            expires_in: 下载链接有效期秒数。

        返回:
            str | None: 返回公开访问地址或签名地址。
        """

        if self.public_base_url:
            return f"{self.public_base_url}/{storage_key.lstrip('/')}"
        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket_name, "Key": storage_key},
            ExpiresIn=expires_in,
        )
