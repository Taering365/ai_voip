"""登录鉴权接口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from psycopg import Connection

from ...auth import create_access_token, encrypt_access_token
from ...config import JwtConfig
from ...services.auth_service import authenticate_user
from ...services.captcha_service import generate_captcha, verify_captcha
from ..dependencies import get_db_connection, get_jwt_config
from ..schemas.auth import CurrentUserData, LoginRequest, LoginResponseData
from ..schemas.common import ApiResponse
from ..schemas.user import CaptchaResponseData

router = APIRouter()


@router.get("/captcha", response_model=ApiResponse)
def get_login_captcha() -> ApiResponse:
    """生成登录验证码图片与会话键。

    Returns:
        ApiResponse: 返回包含验证码图片 base64 内容的响应结构。
    """

    return ApiResponse(data=CaptchaResponseData(**generate_captcha()))


@router.post("/login", response_model=ApiResponse)
def login(
    payload: LoginRequest,
    connection: Connection = Depends(get_db_connection),
    jwt_config: JwtConfig = Depends(get_jwt_config),
) -> ApiResponse:
    """执行用户名密码登录并返回访问令牌。

    Args:
        payload: 登录请求体模型。
        connection: 通过 FastAPI 依赖注入得到的 PostgreSQL 连接对象。
        jwt_config: 通过 FastAPI 依赖注入得到的 JWT 配置对象。

    Returns:
        ApiResponse: 返回包含访问令牌和当前用户信息的响应结构。
    """

    if not verify_captcha(payload.captcha_key, payload.captcha_code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="验证码错误或已过期",
        )

    user = authenticate_user(connection, payload.username, payload.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )

    access_token = create_access_token(
        jwt_config=jwt_config,
        user_id=user["id"],
        username=user["username"],
        role_codes=user["role_codes"],
    )
    encrypted_access_token = encrypt_access_token(jwt_config, access_token)
    return ApiResponse(
        message="login_success",
        data=LoginResponseData(
            access_token=encrypted_access_token,
            token_type="Bearer",
            expires_in=jwt_config.expire_minutes * 60,
            user=CurrentUserData(**user).model_dump(),
        ),
    )
