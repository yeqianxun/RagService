from collections.abc import Callable

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.core.exceptions import AppException, AppErrorCode
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.user import User


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_db),
) -> User:
    """
    获取当前用户依赖注入函数

    该函数通过JWT令牌解析用户信息，并从数据库中获取对应的用户对象，
    同时验证用户是否存在、是否激活等状态。

    Args:
        token (str): 通过OAuth2密码流方案获取的JWT访问令牌
        session (AsyncSession): 数据库异步会话依赖

    Returns:
        User: 当前认证的用户对象

    Raises:
        AppException: 当认证信息无效、用户不存在或用户被禁用时抛出相应异常
    """
    try:
        payload = decode_access_token(token)
        user_email = payload["sub"]
    except (KeyError, ValueError) as exc:
        raise AppException.from_error(AppErrorCode.INVALID_TOKEN) from exc

    stmt = (
        select(User)
        .options(joinedload(User.role))
        .where(User.email == user_email)
    )
    result = await session.execute(stmt)
    user = result.scalars().first()
    if user is None:
        raise AppException.from_error(AppErrorCode.USER_NOT_FOUND)
    if not user.is_active:
        raise AppException.from_error(AppErrorCode.USER_DISABLED)
    # Load role and permissions eagerly to avoid lazy-loading in async context
    role_stmt = (
        select(Role)
        .options(selectinload(Role.permissions))
        .where(Role.id == user.role_id)
    )
    role_result = await session.execute(role_stmt)
    role = role_result.scalars().first()
    # Attach role to user via the relationship attribute
    # Using the relationship setter to avoid SQLAlchemy tracking issues
    user.role = role
    return user


async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """
    获取当前活跃用户依赖注入函数

    该函数作为依赖注入，返回已通过认证的活跃用户对象。
    此函数确保了用户已经通过 get_current_user 函数验证。

    Args:
        current_user (User): 通过 get_current_user 依赖注入获取的当前用户对象

    Returns:
        User: 当前活跃用户对象
    """
    return current_user


def require_permissions(*required_permissions: str) -> Callable[[User], User]:
    """
    权限检查依赖注入装饰器函数

    该函数用于检查当前用户是否拥有指定的权限，超级管理员拥有所有权限。
    可以传入多个权限标识符，用户必须拥有所有指定权限才能通过检查。

    Args:
        *required_permissions (str): 需要检查的一个或多个权限标识符

    Returns:
        Callable[[User], User]: 返回一个依赖注入函数，用于检查用户权限
    """
    async def checker(current_user: User = Depends(get_current_active_user)) -> User:
        """
        实际的权限检查函数

        Args:
            current_user (User): 当前活跃用户对象

        Returns:
            User: 通过权限检查的用户对象

        Raises:
            AppException: 当用户缺少必要权限时抛出403异常
        """
        if current_user.is_superuser:
            return current_user

        user_permissions = {
            p.code for p in current_user.role.permissions
        } if current_user.role else set()

        if not set(required_permissions).issubset(user_permissions):
            raise AppException.from_error(AppErrorCode.PERMISSION_DENIED)
        return current_user

    return checker


# 延迟导入避免循环依赖
from app.models.role import Role  # noqa: E402
