from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.config import settings
from app.core.exceptions import AppException, AppErrorCode
from app.core.security import get_password_hash
from app.models.role import Role
from app.models.user import User
from app.schemas.user import UserCreate


async def create_user(
    session: AsyncSession,
    tenant_id: int,
    payload: UserCreate,
) -> User:
    """
    创建用户服务函数

    该函数在指定租户下创建一个新用户。
    首先验证角色是否存在且属于当前租户，然后检查邮箱或用户名是否已存在，
    最后创建用户并返回包含角色信息的完整用户对象。

    Args:
        session (AsyncSession): 数据库异步会话
        tenant_id (int): 租户ID
        payload (UserCreate): 包含新用户信息的创建请求数据

    Returns:
        User: 新创建的用户对象

    Raises:
        AppException: 当角色不存在或不属于当前租户时抛出404异常
        AppException: 当邮箱或用户名已存在时抛出400异常
    """
    role_stmt = select(Role).where(Role.id == payload.role_id, Role.tenant_id == tenant_id)
    role = (await session.execute(role_stmt)).scalar_one_or_none()
    if role is None:
        raise AppException.from_error(AppErrorCode.ROLE_NOT_FOUND)

    exists_stmt = select(User).where(
        User.tenant_id == tenant_id,
        (User.email == payload.email) | (User.username == payload.username),
    )
    if (await session.execute(exists_stmt)).scalar_one_or_none():
        raise AppException.from_error(AppErrorCode.USER_EXISTS)

    user = User(
        tenant_id=tenant_id,
        role_id=payload.role_id,
        username=payload.username,
        email=payload.email,
        full_name=payload.full_name,
        hashed_password=get_password_hash(payload.password),
        is_active=True,
        is_superuser=False,
    )
    session.add(user)
    await session.commit()

    user_stmt = select(User).options(joinedload(User.role)).where(User.id == user.id)
    return (await session.execute(user_stmt)).scalar_one()


async def list_users(session: AsyncSession, tenant_id: int) -> list[User]:
    """
    列出指定租户下所有用户的服务函数

    该函数返回指定租户下的所有用户列表，按ID升序排列，并预加载用户的角色和租户信息。

    Args:
        session (AsyncSession): 数据库异步会话
        tenant_id (int): 租户ID

    Returns:
        list[User]: 指定租户下的用户对象列表
    """
    stmt = (
        select(User)
        .options(joinedload(User.role), joinedload(User.tenant))
        .where(User.tenant_id == tenant_id)
        .order_by(User.id.asc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_user_detail(session: AsyncSession, tenant_id: int, user_id: int) -> User:
    """
    获取指定用户详情的服务函数

    该函数返回指定租户下特定用户的信息，包括用户的角色和租户信息。
    如果用户不存在，则抛出异常。

    Args:
        session (AsyncSession): 数据库异步会话
        tenant_id (int): 租户ID
        user_id (int): 用户ID

    Returns:
        User: 指定用户的完整对象

    Raises:
        AppException: 当用户不存在时抛出404异常
    """
    stmt = (
        select(User)
        .options(joinedload(User.role), joinedload(User.tenant))
        .where(User.id == user_id, User.tenant_id == tenant_id)
    )
    user = (await session.execute(stmt)).scalar_one_or_none()
    if user is None:
        raise AppException.from_error(AppErrorCode.USER_NOT_EXIST)
    return user


async def save_upload(file: UploadFile, tenant_id: int) -> str:
    """
    保存上传文件的服务函数

    该函数将上传的文件保存到租户隔离的目录中，使用UUID生成唯一文件名以避免冲突。

    Args:
        file (UploadFile): 上传的文件对象
        tenant_id (int): 租户ID，用于创建租户隔离的存储目录

    Returns:
        str: 保存后的文件完整路径
    """
    upload_dir = Path(settings.UPLOAD_DIR) / str(tenant_id)
    upload_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid4().hex}_{file.filename}"
    destination = upload_dir / filename
    content = await file.read()
    destination.write_bytes(content)
    return str(destination)
