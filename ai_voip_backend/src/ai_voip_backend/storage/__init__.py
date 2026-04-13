"""存储后端抽象导出。"""

from .base import StorageObject, StorageProvider
from .local import LocalStorageProvider
from .s3_placeholder import S3CompatibleStorageProvider

__all__ = [
    "LocalStorageProvider",
    "S3CompatibleStorageProvider",
    "StorageObject",
    "StorageProvider",
]
