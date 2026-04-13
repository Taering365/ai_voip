"""SQL 文件辅助工具。"""

from __future__ import annotations

from pathlib import Path


def get_sql_files(base_dir: Path) -> list[Path]:
    """获取需要按顺序执行的 SQL 文件列表。

    Args:
        base_dir: PostgreSQL SQL 文件所在目录。

    Returns:
        list[Path]: 返回按文件名字典序排序的 SQL 文件路径列表。
    """

    if not base_dir.exists():
        raise FileNotFoundError(f"SQL 目录不存在: {base_dir}")
    return sorted(path for path in base_dir.glob("*.sql") if path.is_file())


def build_schema_bundle(base_dir: Path) -> str:
    """合并指定目录下的 SQL 文件内容。

    Args:
        base_dir: PostgreSQL SQL 文件所在目录。

    Returns:
        str: 返回包含全部 SQL 文件内容的可执行脚本文本。
    """

    chunks: list[str] = []
    for file_path in get_sql_files(base_dir):
        chunks.append(f"-- >>> {file_path.name}\n")
        chunks.append(file_path.read_text(encoding="utf-8").rstrip())
        chunks.append("\n\n")
    return "".join(chunks).rstrip() + "\n"
