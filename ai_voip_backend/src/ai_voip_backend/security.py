"""安全相关工具。"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os


def hash_password(password: str, iterations: int = 600_000) -> str:
    """使用 PBKDF2-HMAC-SHA256 对密码进行加密。

    Args:
        password: 用户输入的原始密码明文。
        iterations: PBKDF2 迭代次数，默认使用较高轮数提升安全性。

    Returns:
        str: 返回包含算法、迭代次数、盐值和摘要的可存储字符串。
    """

    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    salt_text = base64.b64encode(salt).decode("ascii")
    digest_text = base64.b64encode(digest).decode("ascii")
    return f"pbkdf2_sha256${iterations}${salt_text}${digest_text}"


def verify_password(password: str, password_hash: str) -> bool:
    """校验原始密码与已保存哈希是否匹配。

    Args:
        password: 用户输入的原始密码明文。
        password_hash: 数据库中保存的密码哈希串。

    Returns:
        bool: 匹配返回 True，不匹配或格式异常返回 False。
    """

    try:
        algorithm, iterations_text, salt_text, digest_text = password_hash.split("$", 3)
    except ValueError:
        return False

    if algorithm != "pbkdf2_sha256":
        return False

    iterations = int(iterations_text)
    salt = base64.b64decode(salt_text.encode("ascii"))
    expected_digest = base64.b64decode(digest_text.encode("ascii"))
    actual_digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(expected_digest, actual_digest)
