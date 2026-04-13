"""JWT 鉴权工具。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os

import jwt
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .config import JwtConfig, build_token_cipher_key


def create_access_token(
    jwt_config: JwtConfig,
    user_id: int,
    username: str,
    role_codes: list[str],
) -> str:
    """创建访问令牌。

    Args:
        jwt_config: JWT 签发配置对象。
        user_id: 当前登录用户主键。
        username: 当前登录用户名。
        role_codes: 当前登录用户拥有的角色编码列表。

    Returns:
        str: 返回签发好的 JWT 访问令牌字符串。
    """

    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "username": username,
        "role_codes": role_codes,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=jwt_config.expire_minutes)).timestamp()),
    }
    return jwt.encode(payload, jwt_config.secret, algorithm=jwt_config.algorithm)


def encrypt_access_token(jwt_config: JwtConfig, plain_token: str) -> str:
    """对已签名的 JWT 明文令牌进行 AES-GCM 加密。

    Args:
        jwt_config: JWT 签发配置对象。
        plain_token: 已签名但尚未对外发放的 JWT 明文令牌。

    Returns:
        str: 返回以十六进制字符串表示的密文令牌。
    """

    aesgcm = AESGCM(build_token_cipher_key(jwt_config))
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, plain_token.encode("utf-8"), None)
    return (nonce + ciphertext).hex()


def decrypt_access_token(jwt_config: JwtConfig, encrypted_token: str) -> str:
    """对前端回传的密文令牌进行解密。

    Args:
        jwt_config: JWT 签发配置对象。
        encrypted_token: 前端原样回传的十六进制密文令牌字符串。

    Returns:
        str: 返回解密得到的 JWT 明文令牌。
    """

    token_bytes = bytes.fromhex(encrypted_token)
    nonce = token_bytes[:12]
    ciphertext = token_bytes[12:]
    aesgcm = AESGCM(build_token_cipher_key(jwt_config))
    plain_token = aesgcm.decrypt(nonce, ciphertext, None)
    return plain_token.decode("utf-8")


def decode_access_token(jwt_config: JwtConfig, token: str) -> dict:
    """解密并校验访问令牌。

    Args:
        jwt_config: JWT 签发配置对象。
        token: 客户端传入的加密访问令牌字符串。

    Returns:
        dict: 返回解密并验签后的令牌载荷字典。
    """

    plain_token = decrypt_access_token(jwt_config, token)
    return jwt.decode(plain_token, jwt_config.secret, algorithms=[jwt_config.algorithm])
