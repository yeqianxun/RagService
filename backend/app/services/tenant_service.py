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
        username=payload.admin_username,
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


async def list_tenants(session: AsyncSession, tenant_id: int | None = None) -> list[Tenant]:
    """
    列出租户服务函数

    该函数返回租户列表，按ID升序排列。如果指定了tenant_id，则只返回该租户；
    否则返回所有租户（仅限超级管理员使用）。

    Args:
        session (AsyncSession): 数据库异步会话
        tenant_id (int | None): 可选的租户ID过滤

    Returns:
        list[Tenant]: 租户对象列表
    """
    stmt = select(Tenant).order_by(Tenant.id.asc())
    if tenant_id is not None:
        stmt = stmt.where(Tenant.id == tenant_id)
    result = await session.execute(stmt)
    return list(result.scalars().all())
