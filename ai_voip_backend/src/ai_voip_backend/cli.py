"""命令行入口。"""

from __future__ import annotations

import argparse
from pathlib import Path

from .bootstrap import bootstrap_admin_user
from .config import load_postgres_config
from .db import check_db_connection, describe_config, execute_sql_file
from .schema import build_schema_bundle, get_sql_files


def build_parser() -> argparse.ArgumentParser:
    """构建命令行参数解析器。

    Returns:
        argparse.ArgumentParser: 返回当前项目使用的命令行解析器实例。
    """

    parser = argparse.ArgumentParser(
        prog="ai-voip-backend",
        description="开源智能外呼平台后端辅助工具。",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list-sql", help="列出当前 PostgreSQL SQL 文件。")
    list_parser.add_argument(
        "--base-dir",
        default=None,
        help="SQL 根目录，默认使用项目内置 sql/pgsql 目录。",
    )

    bundle_parser = subparsers.add_parser("bundle-sql", help="合并输出 PostgreSQL SQL 文件。")
    bundle_parser.add_argument(
        "--base-dir",
        default=None,
        help="SQL 根目录，默认使用项目内置 sql/pgsql 目录。",
    )
    bundle_parser.add_argument(
        "--output",
        default=None,
        help="输出文件路径，不传时直接打印到标准输出。",
    )

    subparsers.add_parser("show-db-config", help="显示当前 PostgreSQL 配置。")
    subparsers.add_parser("check-db", help="检查当前 PostgreSQL 连通性。")

    apply_parser = subparsers.add_parser("apply-sql", help="执行 PostgreSQL 初始化 SQL。")
    apply_parser.add_argument(
        "--sql-file",
        default=None,
        help="要执行的 SQL 文件路径，默认执行 build/init_pgsql.sql。",
    )

    bootstrap_parser = subparsers.add_parser("bootstrap-admin", help="创建或更新超级管理员。")
    bootstrap_parser.add_argument("--username", required=True, help="超级管理员用户名。")
    bootstrap_parser.add_argument("--password", required=True, help="超级管理员密码。")
    bootstrap_parser.add_argument(
        "--display-name",
        default="系统管理员",
        help="超级管理员显示名称。",
    )

    return parser


def resolve_base_dir(base_dir: str | None) -> Path:
    """解析 SQL 根目录。

    Args:
        base_dir: 用户传入的 SQL 根目录，允许为空。

    Returns:
        Path: 返回最终确定的 SQL 目录绝对路径。
    """

    if base_dir:
        return Path(base_dir).expanduser().resolve()
    return Path(__file__).resolve().parents[2] / "sql" / "pgsql"


def handle_list_sql(base_dir: Path) -> int:
    """执行列出 SQL 文件命令。

    Args:
        base_dir: SQL 根目录路径。

    Returns:
        int: 命令执行完成后的退出码，0 表示成功。
    """

    for file_path in get_sql_files(base_dir):
        print(file_path)
    return 0


def handle_bundle_sql(base_dir: Path, output: str | None) -> int:
    """执行合并 SQL 文件命令。

    Args:
        base_dir: SQL 根目录路径。
        output: 输出文件路径，为空时打印到标准输出。

    Returns:
        int: 命令执行完成后的退出码，0 表示成功。
    """

    content = build_schema_bundle(base_dir)
    if output:
        output_path = Path(output).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content, encoding="utf-8")
    else:
        print(content)
    return 0


def resolve_sql_output(project_root: Path, sql_file: str | None) -> Path:
    """解析要执行的 SQL 文件路径。

    Args:
        project_root: 当前后端项目根目录。
        sql_file: 用户手动指定的 SQL 文件路径，可为空。

    Returns:
        Path: 返回最终需要执行的 SQL 文件绝对路径。
    """

    if sql_file:
        return Path(sql_file).expanduser().resolve()
    return project_root / "build" / "init_pgsql.sql"


def handle_show_db_config(project_root: Path) -> int:
    """输出当前 PostgreSQL 配置摘要。

    Args:
        project_root: 当前后端项目根目录。

    Returns:
        int: 命令执行完成后的退出码，0 表示成功。
    """

    config = load_postgres_config(project_root)
    print(describe_config(config))
    return 0


def handle_check_db(project_root: Path) -> int:
    """检测当前 PostgreSQL 是否可连通。

    Args:
        project_root: 当前后端项目根目录。

    Returns:
        int: 命令执行完成后的退出码，0 表示成功。
    """

    config = load_postgres_config(project_root)
    database_name, version_text = check_db_connection(config)
    print(f"database={database_name}")
    print(version_text)
    return 0


def handle_apply_sql(project_root: Path, sql_file: str | None) -> int:
    """执行初始化 SQL 文件到 PostgreSQL。

    Args:
        project_root: 当前后端项目根目录。
        sql_file: 用户指定的 SQL 文件路径，可为空。

    Returns:
        int: 命令执行完成后的退出码，0 表示成功。
    """

    config = load_postgres_config(project_root)
    resolved_sql_file = resolve_sql_output(project_root, sql_file)
    if not resolved_sql_file.exists():
        raise FileNotFoundError(f"SQL 文件不存在: {resolved_sql_file}")
    execute_sql_file(config, str(resolved_sql_file))
    print(f"已执行 SQL: {resolved_sql_file}")
    return 0


def handle_bootstrap_admin(
    project_root: Path,
    username: str,
    password: str,
    display_name: str,
) -> int:
    """创建或更新超级管理员账号。

    Args:
        project_root: 当前后端项目根目录。
        username: 超级管理员用户名。
        password: 超级管理员密码。
        display_name: 超级管理员显示名称。

    Returns:
        int: 命令执行完成后的退出码，0 表示成功。
    """

    config = load_postgres_config(project_root)
    bootstrap_admin_user(config, username, password, display_name)
    print(f"已初始化超级管理员: {username}")
    return 0


def main() -> int:
    """运行项目命令行入口。

    Returns:
        int: 返回命令执行结果的退出码。
    """

    parser = build_parser()
    args = parser.parse_args()
    project_root = Path(__file__).resolve().parents[2]
    base_dir = resolve_base_dir(getattr(args, "base_dir", None))

    if args.command == "list-sql":
        return handle_list_sql(base_dir)
    if args.command == "bundle-sql":
        return handle_bundle_sql(base_dir, args.output)
    if args.command == "show-db-config":
        return handle_show_db_config(project_root)
    if args.command == "check-db":
        return handle_check_db(project_root)
    if args.command == "apply-sql":
        return handle_apply_sql(project_root, args.sql_file)
    if args.command == "bootstrap-admin":
        return handle_bootstrap_admin(project_root, args.username, args.password, args.display_name)

    parser.error(f"不支持的命令: {args.command}")
    return 2
