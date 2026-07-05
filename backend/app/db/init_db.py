from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import get_password_hash
from app.db.session import AsyncSessionLocal, engine
from app.models.base import Base
from app.models.role import Role
from app.models.tenant import Tenant
from app.models.user import User


DEFAULT_ADMIN_PERMISSIONS = [
    "tenant:read",
    "tenant:create",
    "user:read",
    "user:create",
    "user:upload",
]


async def seed_default_data(session: AsyncSession) -> None:
    """
    初始化默认数据的服务函数

    该函数检查是否存在默认租户，如果不存在则创建默认租户、管理员角色和超级管理员用户。
    这个函数通常在应用启动时调用，用于确保系统中有基本的初始数据。

    Args:
        session (AsyncSession): 数据库异步会话
    """
    tenant_stmt = select(Tenant).where(Tenant.code == settings.DEFAULT_TENANT_CODE)
    tenant = (await session.execute(tenant_stmt)).scalar_one_or_none()
    if tenant:
        return

    tenant = Tenant(name=settings.DEFAULT_TENANT_NAME, code=settings.DEFAULT_TENANT_CODE)
    session.add(tenant)
    await session.flush()

    role = Role(
        tenant_id=tenant.id,
        name="admin",
        description="System administrator",
        permissions=DEFAULT_ADMIN_PERMISSIONS,
    )
    session.add(role)
    await session.flush()

    admin_user = User(
        tenant_id=tenant.id,
        role_id=role.id,
        username="admin",
        email=settings.DEFAULT_ADMIN_EMAIL,
        full_name=settings.DEFAULT_ADMIN_FULL_NAME,
        hashed_password=get_password_hash(settings.DEFAULT_ADMIN_PASSWORD),
        is_active=True,
        is_superuser=True,
    )
    session.add(admin_user)
    await session.commit()


async def initialize_database() -> None:
    """
    初始化数据库的服务函数

    该函数创建所有数据库表（如果不存在），然后插入默认数据。
    这个函数通常在应用启动时通过lifespan事件调用。

    """
    async with engine.begin() as connection:
        # 启用 pgvector 扩展
        await connection.execute(text('CREATE EXTENSION IF NOT EXISTS vector'))
        await connection.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        await seed_default_data(session)
