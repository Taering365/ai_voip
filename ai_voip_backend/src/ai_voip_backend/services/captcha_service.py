"""登录验证码服务。"""

from __future__ import annotations

import base64
import html
import secrets
import time
from threading import Lock

_captcha_store: dict[str, dict[str, float | str]] = {}
_captcha_lock = Lock()
_captcha_ttl_seconds = 300


def _cleanup_expired_captcha(now_timestamp: float) -> None:
    """清理已过期的验证码缓存记录。

    Args:
        now_timestamp: 当前时间戳，用于与过期时间进行比较。
    """

    expired_keys = [
        captcha_key
        for captcha_key, captcha_item in _captcha_store.items()
        if float(captcha_item["expires_at"]) <= now_timestamp
    ]
    for captcha_key in expired_keys:
        _captcha_store.pop(captcha_key, None)


def _build_captcha_svg(code_text: str) -> str:
    """构造用于前端展示的验证码 SVG 文本。

    Args:
        code_text: 需要绘制到验证码图片上的数字文本。

    Returns:
        str: 返回 SVG 格式的验证码图片文本内容。
    """

    safe_code_text = html.escape(code_text)
    return f"""
<svg xmlns="http://www.w3.org/2000/svg" width="140" height="52" viewBox="0 0 140 52">
  <rect width="140" height="52" rx="12" fill="#f4f8ff"/>
  <rect x="1" y="1" width="138" height="50" rx="11" fill="none" stroke="#d8e7ff"/>
  <path d="M10 37 C28 12 46 46 64 22 S100 12 130 30" stroke="#b8d5ff" stroke-width="3" fill="none" />
  <circle cx="22" cy="15" r="4" fill="#dcecff"/>
  <circle cx="118" cy="40" r="5" fill="#e8f2ff"/>
  <text x="70" y="34" text-anchor="middle" font-size="28" font-weight="700" letter-spacing="8" fill="#2565d0">{safe_code_text}</text>
</svg>
""".strip()


def generate_captcha() -> dict:
    """生成一组新的数字验证码并写入内存缓存。

    Returns:
        dict: 返回验证码键、图片 base64、图片类型和有效期秒数。
    """

    now_timestamp = time.time()
    captcha_code = "".join(secrets.choice("0123456789") for _ in range(4))
    captcha_key = secrets.token_urlsafe(24)
    captcha_svg = _build_captcha_svg(captcha_code)
    captcha_image_base64 = base64.b64encode(captcha_svg.encode("utf-8")).decode("ascii")

    with _captcha_lock:
        _cleanup_expired_captcha(now_timestamp)
        _captcha_store[captcha_key] = {
            "code": captcha_code,
            "expires_at": now_timestamp + _captcha_ttl_seconds,
        }

    return {
        "captcha_key": captcha_key,
        "image_base64": captcha_image_base64,
        "image_mime_type": "image/svg+xml",
        "expires_in": _captcha_ttl_seconds,
    }


def verify_captcha(captcha_key: str, captcha_code: str) -> bool:
    """校验验证码是否正确，并在校验完成后消费该验证码。

    Args:
        captcha_key: 前端持有的验证码键。
        captcha_code: 用户输入的验证码文本。

    Returns:
        bool: 验证码正确且未过期时返回 True，否则返回 False。
    """

    now_timestamp = time.time()
    normalized_code = captcha_code.strip()

    with _captcha_lock:
        _cleanup_expired_captcha(now_timestamp)
        captcha_item = _captcha_store.pop(captcha_key, None)

    if not captcha_item:
        return False

    if float(captcha_item["expires_at"]) <= now_timestamp:
        return False

    return str(captcha_item["code"]) == normalized_code
