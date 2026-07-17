from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import verify_password
from app.models.role import Role
from app.models.user import User


async def authenticate_user(
    session: AsyncSession,
    email: str,
    password: str,
) -> User | None:
    """
    认证用户服务函数

    该函数根据邮箱和密码验证用户身份。
    首先验证用户是否存在且激活，最后验证密码是否正确。

    Args:
        session (AsyncSession): 数据库异步会话
        email (str): 用户邮箱
        password (str): 用户提供的明文密码

    Returns:
        User | None: 认证成功返回用户对象，否则返回None
    """
    user_stmt = (
        select(User)
        .where(
            User.email == email,
            User.is_active.is_(True),
        )
    )
    user = (await session.execute(user_stmt)).scalars().first()
    if user is None or not verify_password(password, user.hashed_password):
        return None

    # Load role and permissions eagerly
    role_stmt = (
        select(Role)
        .options(selectinload(Role.permissions))
        .where(Role.id == user.role_id)
    )
    role_result = await session.execute(role_stmt)
    user.role = role_result.scalars().first()

    return user
