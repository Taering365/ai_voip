"""统一存储接口抽象。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import BinaryIO


@dataclass(slots=True)
class StorageObject:
    """描述一次文件保存后的存储结果。

    Attributes:
        storage_backend: 当前对象所属存储后端类型，如 local 或 s3_compatible。
        storage_key: 业务统一使用的逻辑存储键。
        local_path: 本地落盘后的绝对路径，非本地存储时可为空。
        object_key: 第三方对象存储键，非对象存储时可为空。
        extra_meta: 额外元数据，便于后续扩展自定义字段。
    """

    storage_backend: str
    storage_key: str
    local_path: str | None = None
    object_key: str | None = None
    extra_meta: dict[str, str] = field(default_factory=dict)


class StorageProvider(ABC):
    """定义统一存储后端接口。"""

    @abstractmethod
    def save(
        self,
        file_stream: BinaryIO,
        target_key: str,
        meta: dict[str, str] | None = None,
    ) -> StorageObject:
        """保存输入文件流到当前存储后端。

        Args:
            file_stream: 文件二进制流对象。
            target_key: 业务传入的逻辑存储键。
            meta: 文件相关的扩展元数据，可为空。

        Returns:
            StorageObject: 返回保存后的统一存储结果对象。
        """

    @abstractmethod
    def delete(self, storage_key: str) -> bool:
        """删除指定逻辑键对应的文件对象。

        Args:
            storage_key: 业务统一使用的逻辑存储键。

        Returns:
            bool: 删除成功返回 True，不存在或失败返回 False。
        """

    @abstractmethod
    def exists(self, storage_key: str) -> bool:
        """检查指定逻辑键对应的文件是否存在。

        Args:
            storage_key: 业务统一使用的逻辑存储键。

        Returns:
            bool: 文件存在返回 True，否则返回 False。
        """

    @abstractmethod
    def resolve_path(self, storage_key: str) -> str:
        """解析逻辑存储键对应的实际访问路径。

        Args:
            storage_key: 业务统一使用的逻辑存储键。

        Returns:
            str: 返回本地路径或对象键等实际定位值。
        """

    @abstractmethod
    def build_download_url(self, storage_key: str, expires_in: int) -> str | None:
        """构建下载地址或签名地址。

        Args:
            storage_key: 业务统一使用的逻辑存储键。
            expires_in: 下载链接有效期秒数。

        Returns:
            str | None: 当前后端支持外链时返回链接，否则返回 None。
        """
