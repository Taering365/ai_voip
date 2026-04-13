"""用户管理请求与响应模型。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class UserCreateRequest(BaseModel):
    """定义创建用户请求体。

    Attributes:
        username: 登录用户名。
        password: 登录密码明文。
        display_name: 用户显示名称。
        mobile: 用户手机号。
        email: 用户邮箱。
        status: 用户状态。
        role_codes: 用户角色编码列表。
    """

    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=6, max_length=255)
    display_name: str = Field(min_length=1, max_length=128)
    mobile: str | None = None
    email: str | None = None
    status: str = Field(default="active")
    role_codes: list[str] = Field(default_factory=lambda: ["agent_user"])


class UserUpdateRequest(BaseModel):
    """定义更新用户请求体。

    Attributes:
        display_name: 用户显示名称。
        mobile: 用户手机号。
        email: 用户邮箱。
        status: 用户状态。
        role_codes: 用户角色编码列表。
        password: 用户新密码，可为空。
    """

    display_name: str = Field(min_length=1, max_length=128)
    mobile: str | None = None
    email: str | None = None
    status: str = Field(default="active")
    role_codes: list[str] = Field(default_factory=lambda: ["agent_user"])
    password: str | None = Field(default=None, min_length=6, max_length=255)


class UserItem(BaseModel):
    """定义用户响应模型。

    Attributes:
        id: 用户主键。
        username: 用户登录名。
        display_name: 用户显示名称。
        mobile: 用户手机号。
        email: 用户邮箱。
        status: 用户状态。
        role_codes: 用户角色编码列表。
        created_at: 创建时间。
        updated_at: 更新时间。
    """

    id: int
    username: str
    display_name: str
    mobile: str | None
    email: str | None
    status: str
    role_codes: list[str]
    created_at: str
    updated_at: str


class UserTrunkAssignmentRequest(BaseModel):
    """定义用户线路分配请求体。

    Attributes:
        trunk_ids: 需要分配给当前用户的线路主键列表。
    """

    trunk_ids: list[int] = Field(default_factory=list)


class CaptchaResponseData(BaseModel):
    """定义验证码响应模型。

    Attributes:
        captcha_key: 验证码会话键。
        image_base64: 图片二进制的 base64 字符串。
        image_mime_type: 图片 MIME 类型。
        expires_in: 验证码剩余有效秒数。
    """

    captcha_key: str
    image_base64: str
    image_mime_type: str
    expires_in: int
