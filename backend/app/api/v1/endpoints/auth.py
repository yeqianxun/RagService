from fastapi import APIRouter, Depends, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user
from app.core.config import settings
from app.core.exceptions import AppException, AppErrorCode
from app.core.response import success_response
from app.core.security import create_access_token
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import (
    CurrentUserInfo,
    LoginRequest,
    OAuth2TokenResponse,
    TokenData,
)
from app.services.auth_service import authenticate_user


router = APIRouter()


@router.post("/login")
async def login(request: Request, payload: LoginRequest, session: AsyncSession = Depends(get_db)):
    """
    用户登录接口

    该接口接收邮箱和密码进行身份验证，如果验证成功则返回访问令牌和用户信息。

    Args:
        payload (LoginRequest): 包含邮箱和密码的登录请求数据
        session (AsyncSession): 数据库异步会话依赖

    Returns:
        JSONResponse: 包含访问令牌、过期时间及用户信息的成功响应

    Raises:
        AppException: 当账号或密码错误时抛出401异常
    """
    user = await authenticate_user(
        session=session,
        email=str(payload.email),
        password=payload.password,
    )
    if user is None:
        raise AppException.from_error(AppErrorCode.INVALID_CREDENTIALS)

    token = create_access_token(subject=user.email, is_superuser=user.is_superuser)
    data = TokenData(
        access_token=token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=CurrentUserInfo.model_validate(user, from_attributes=True),
    )
    return success_response(data=data, message="登录成功")


@router.post("/token", include_in_schema=False)
async def oauth2_token(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: AsyncSession = Depends(get_db),
):
    """
    OAuth2 token 端点（兼容 Swagger Authorize 弹窗）

    该端点接收 application/x-www-form-urlencoded 格式的请求，
    username 字段为邮箱，password 字段为登录密码。

    此端点不显示在 Swagger 文档中，仅用于 Authorize 弹窗的自动认证流程。
    """
    user = await authenticate_user(
        session=session,
        email=form_data.username.strip(),
        password=form_data.password,
    )
    if user is None:
        raise AppException.from_error(AppErrorCode.INVALID_CREDENTIALS)

    token = create_access_token(subject=user.email, is_superuser=user.is_superuser)
    return OAuth2TokenResponse(
        access_token=token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.get("/me")
async def read_current_user(current_user: User = Depends(get_current_active_user)):
    """
    获取当前用户信息接口

    该接口返回当前已认证用户的详细信息。

    Args:
        current_user (User): 通过依赖注入获取的当前活跃用户对象

    Returns:
        JSONResponse: 包含当前用户信息的成功响应
    """
    return success_response(
        data=CurrentUserInfo.model_validate(current_user, from_attributes=True),
        message="获取当前用户成功",
    )
