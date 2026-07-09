from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.core.exceptions import AppException, AppErrorCode
from app.models.permission import Permission
from app.models.role import Role
from app.schemas.permission import PermissionCreate, PermissionUpdate


async def create_permission(session: AsyncSession, payload: PermissionCreate) -> Permission:
    """创建权限"""
    exists = await session.execute(
        select(Permission).where(Permission.code == payload.code)
    )
    if exists.scalar_one_or_none():
        raise AppException(400, f"权限编码 '{payload.code}' 已存在", code=4003)

    permission = Permission(
        code=payload.code,
        name=payload.name,
        description=payload.description,
        module=payload.module,
    )
    session.add(permission)
    await session.commit()
    await session.refresh(permission)
    return permission


async def list_permissions(
    session: AsyncSession,
    module: str | None = None,
) -> list[Permission]:
    """列出权限，可按模块筛选"""
    stmt = select(Permission).order_by(Permission.module.asc(), Permission.code.asc())
    if module:
        stmt = stmt.where(Permission.module == module)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_permission(session: AsyncSession, permission_id: int) -> Permission:
    """获取单个权限详情"""
    permission = await session.get(Permission, permission_id)
    if permission is None:
        raise AppException.from_error(AppErrorCode.PERMISSION_NOT_FOUND)
    return permission


async def update_permission(
    session: AsyncSession, permission_id: int, payload: PermissionUpdate
) -> Permission:
    """更新权限"""
    permission = await get_permission(session, permission_id)
    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(permission, field, value)
    await session.commit()
    await session.refresh(permission)
    return permission


async def delete_permission(session: AsyncSession, permission_id: int) -> None:
    """删除权限"""
    permission = await get_permission(session, permission_id)
    await session.delete(permission)
    await session.commit()


async def get_role_permissions(session: AsyncSession, role_id: int) -> list[Permission]:
    """获取角色已分配的权限"""
    stmt = (
        select(Role)
        .options(selectinload(Role.permissions))
        .where(Role.id == role_id)
    )
    result = await session.execute(stmt)
    role = result.unique().scalar_one_or_none()
    if role is None:
        raise AppException.from_error(AppErrorCode.ROLE_NOT_FOUND)
    return list(role.permissions)


async def set_role_permissions(
    session: AsyncSession, role_id: int, permission_ids: list[int]
) -> list[Permission]:
    """批量设置角色的权限（全量替换）"""
    role = await session.get(Role, role_id)
    if role is None:
        raise AppException.from_error(AppErrorCode.ROLE_NOT_FOUND)

    # 验证所有 permission_id 有效
    if permission_ids:
        perms_stmt = select(Permission).where(Permission.id.in_(permission_ids))
        perms_result = await session.execute(perms_stmt)
        valid_permissions = list(perms_result.scalars().all())
        if len(valid_permissions) != len(permission_ids):
            raise AppException(400, "部分权限ID不存在", code=4004)
        role.permissions = valid_permissions
    else:
        role.permissions = []

    await session.commit()

    # 重新加载以返回完整数据
    result_stmt = (
        select(Role)
        .options(selectinload(Role.permissions))
        .where(Role.id == role_id)
    )
    updated_result = await session.execute(result_stmt)
    updated_role = updated_result.unique().scalar_one()
    return list(updated_role.permissions)


async def get_modules(session: AsyncSession) -> list[str]:
    """获取所有权限模块列表"""
    stmt = select(Permission.module).distinct().order_by(Permission.module.asc())
    result = await session.execute(stmt)
    return list(result.scalars().all())
