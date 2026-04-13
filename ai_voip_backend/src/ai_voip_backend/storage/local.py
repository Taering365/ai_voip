"""本地磁盘存储实现。"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import BinaryIO

from .base import StorageObject, StorageProvider


class LocalStorageProvider(StorageProvider):
    """实现基于本地磁盘的文件存储。"""

    def __init__(self, root_dir: str, public_base_url: str | None = None) -> None:
        """初始化本地存储提供者。

        参数:
            root_dir: 本地存储根目录，所有文件都会落到该目录下。
            public_base_url: 当前本地存储对外可访问的基础地址，可为空。
        """

        self.root_dir = Path(root_dir).expanduser().resolve()
        self.public_base_url = public_base_url.rstrip("/") if public_base_url else None
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def save(
        self,
        file_stream: BinaryIO,
        target_key: str,
        meta: dict[str, str] | None = None,
    ) -> StorageObject:
        """将输入文件流保存到本地磁盘。

        Args:
            file_stream: 文件二进制流对象。
            target_key: 逻辑存储键，也会作为相对路径使用。
            meta: 文件相关的扩展元数据，可为空。

        Returns:
            StorageObject: 返回本地存储结果对象。
        """

        destination = self.root_dir / target_key
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("wb") as output:
            shutil.copyfileobj(file_stream, output)
        return StorageObject(
            storage_backend="local",
            storage_key=target_key,
            local_path=str(destination),
            extra_meta=meta or {},
        )

    def delete(self, storage_key: str) -> bool:
        """删除本地磁盘中的目标文件。

        Args:
            storage_key: 业务统一使用的逻辑存储键。

        Returns:
            bool: 删除成功返回 True，不存在返回 False。
        """

        path = self.root_dir / storage_key
        if not path.exists():
            return False
        path.unlink()
        return True

    def exists(self, storage_key: str) -> bool:
        """检查本地磁盘中目标文件是否存在。

        Args:
            storage_key: 业务统一使用的逻辑存储键。

        Returns:
            bool: 文件存在返回 True，否则返回 False。
        """

        return (self.root_dir / storage_key).exists()

    def resolve_path(self, storage_key: str) -> str:
        """解析本地文件的绝对路径。

        Args:
            storage_key: 业务统一使用的逻辑存储键。

        Returns:
            str: 返回本地文件的绝对路径字符串。
        """

        return str((self.root_dir / storage_key).resolve())

    def build_download_url(self, storage_key: str, expires_in: int) -> str | None:
        """构建下载地址。

        参数:
            storage_key: 业务统一使用的逻辑存储键。
            expires_in: 下载链接有效期秒数，本地存储当前不做签名控制，仅用于接口兼容。

        返回:
            str | None: 若已配置对外访问前缀，则返回拼接后的下载地址，否则返回 None。
        """

        _ = expires_in
        if not self.public_base_url:
            return None
        return f"{self.public_base_url}/{storage_key.lstrip('/')}"
