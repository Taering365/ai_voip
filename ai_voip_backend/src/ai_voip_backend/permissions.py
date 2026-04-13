"""权限判断工具。"""

from __future__ import annotations

ADMIN_ROLE_CODES = {"super_admin", "ops_admin", "enterprise_admin"}


def is_admin_role_codes(role_codes: list[str] | tuple[str, ...]) -> bool:
    """根据角色编码列表判断当前用户是否属于管理员。

    Args:
        role_codes: 当前用户拥有的角色编码列表。

    Returns:
        bool: 角色列表中包含管理员角色时返回 True，否则返回 False。
    """

    return any(role_code in ADMIN_ROLE_CODES for role_code in role_codes)


def is_admin_user(user: dict) -> bool:
    """根据当前用户信息字典判断其是否属于管理员。

    Args:
        user: 当前登录用户信息字典，要求包含 `role_codes` 字段。

    Returns:
        bool: 当前用户拥有管理员角色时返回 True，否则返回 False。
    """

    return is_admin_role_codes(user.get("role_codes", []))
