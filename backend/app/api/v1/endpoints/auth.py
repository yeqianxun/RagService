from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user
from app.core.config import settings
from app.core.exceptions import AppException
from app.core.response import success_response
from app.core.security import create_access_token
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import CurrentUserInfo, LoginRequest, TokenData
from app.services.auth_service import authenticate_user


router = APIRouter()


@router.post("/login")
async def login(payload: LoginRequest, session: AsyncSession = Depends(get_db)):
    """
    用户登录接口

    该接口接收租户代码、邮箱和密码进行身份验证，如果验证成功则返回访问令牌和用户信息。

    Args:
        payload (LoginRequest): 包含租户代码、邮箱和密码的登录请求数据
        session (AsyncSession): 数据库异步会话依赖

    Returns:
        JSONResponse: 包含访问令牌、过期时间及用户信息的成功响应

    Raises:
        AppException: 当租户、账号或密码错误时抛出401异常
    """
    user = await authenticate_user(
        session=session,
        tenant_code=payload.tenant_code,
        email=payload.email,
        password=payload.password,
    )
    if user is None:
        raise AppException(status_code=401, code=4012, message="租户、账号或密码错误")

    token = create_access_token(subject=user.email, tenant_id=user.tenant_id)
    data = TokenData(
        access_token=token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=CurrentUserInfo.model_validate(user, from_attributes=True),
    )
    return success_response(data=data, message="登录成功")


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
