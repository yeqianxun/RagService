from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.security import verify_password
from app.models.tenant import Tenant
from app.models.user import User


async def authenticate_user(
    session: AsyncSession,
    tenant_code: str,
    email: str,
    password: str,
) -> User | None:
    """
    认证用户服务函数

    该函数根据租户代码、邮箱和密码验证用户身份。
    首先验证租户是否存在且激活，然后验证用户是否存在且激活，最后验证密码是否正确。

    Args:
        session (AsyncSession): 数据库异步会话
        tenant_code (str): 租户代码
        email (str): 用户邮箱
        password (str): 用户提供的明文密码

    Returns:
        User | None: 认证成功返回用户对象，否则返回None
    """
    tenant_stmt = select(Tenant).where(Tenant.code == tenant_code, Tenant.is_active.is_(True))
    tenant = (await session.execute(tenant_stmt)).scalar_one_or_none()
    if tenant is None:
        return None

    user_stmt = (
        select(User)
        .options(joinedload(User.role))
        .where(
            User.tenant_id == tenant.id,
            User.email == email,
            User.is_active.is_(True),
        )
    )
    user = (await session.execute(user_stmt)).scalar_one_or_none()
    if user is None or not verify_password(password, user.hashed_password):
        return None

    return user
