"""鉴权请求与响应模型。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    """定义登录请求体。

    Attributes:
        username: 登录用户名。
        password: 登录密码明文。
        captcha_key: 当前验证码会话键。
        captcha_code: 用户输入的验证码数字。
    """

    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=255)
    captcha_key: str = Field(min_length=1, max_length=128)
    captcha_code: str = Field(min_length=1, max_length=16)


class LoginResponseData(BaseModel):
    """定义登录成功后的响应数据。

    Attributes:
        access_token: JWT 访问令牌。
        token_type: 令牌类型，固定为 Bearer。
        expires_in: 令牌有效期秒数。
        user: 当前登录用户信息。
    """

    access_token: str
    token_type: str
    expires_in: int
    user: dict


class CurrentUserData(BaseModel):
    """定义当前登录用户响应数据。

    Attributes:
        id: 当前登录用户主键。
        username: 当前登录用户名。
        display_name: 当前登录用户显示名。
        status: 当前登录用户状态。
        role_codes: 当前登录用户拥有的角色编码列表。
    """

    id: int
    username: str
    display_name: str
    status: str
    role_codes: list[str]
