from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException, AppErrorCode
from app.core.security import get_password_hash
from app.db.init_db import DEFAULT_ADMIN_PERMISSIONS
from app.models.role import Role
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.tenant import TenantCreate


async def create_tenant(session: AsyncSession, payload: TenantCreate) -> Tenant:
    """
    创建租户服务函数

    该函数创建一个新的租户，并为其创建默认的管理员角色和管理员用户。
    在创建之前会检查租户名称或编码是否已存在。

    Args:
        session (AsyncSession): 数据库异步会话
        payload (TenantCreate): 包含新租户信息的创建请求数据

    Returns:
        Tenant: 新创建的租户对象

    Raises:
        AppException: 当租户名称或编码已存在时抛出400异常
    """
    tenant_exists = await session.execute(
        select(Tenant).where((Tenant.code == payload.code) | (Tenant.name == payload.name))
    )
    if tenant_exists.scalar_one_or_none():
        raise AppException.from_error(AppErrorCode.TENANT_EXISTS)

    tenant = Tenant(name=payload.name, code=payload.code)
    session.add(tenant)
    await session.flush()

    admin_role = Role(
        tenant_id=tenant.id,
        name="admin",
        description="Tenant administrator",
        permissions=DEFAULT_ADMIN_PERMISSIONS,
    )
    session.add(admin_role)
    await session.flush()

    admin_user = User(
        tenant_id=tenant.id,
        role_id=admin_role.id,
        username="admin",
        email=payload.admin_email,
        full_name=payload.admin_full_name,
        hashed_password=get_password_hash(payload.admin_password),
        is_active=True,
        is_superuser=False,
    )
    session.add(admin_user)
    await session.commit()
    await session.refresh(tenant)
    return tenant


async def list_tenants(session: AsyncSession) -> list[Tenant]:
    """
    列出所有租户服务函数

    该函数返回数据库中所有的租户列表，按ID升序排列。

    Args:
        session (AsyncSession): 数据库异步会话

    Returns:
        list[Tenant]: 租户对象列表
    """
    result = await session.execute(select(Tenant).order_by(Tenant.id.asc()))
    return list(result.scalars().all())
