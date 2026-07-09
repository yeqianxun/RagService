from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user, require_permissions
from app.core.response import success_response
from app.db.session import get_db
from app.models.user import User
from app.schemas.permission import (
    PermissionCreate,
    PermissionRead,
    PermissionUpdate,
    RolePermissionUpdate,
)
from app.services.permission_service import (
    create_permission,
    delete_permission,
    get_modules,
    get_permission,
    get_role_permissions,
    list_permissions,
    set_role_permissions,
    update_permission,
)
from app.services.user_service import get_user_detail

router = APIRouter()


@router.get("")
async def list_permissions_endpoint(
    module: str | None = Query(None, description="按模块筛选"),
    _: User = Depends(require_permissions("permission:read")),
    session: AsyncSession = Depends(get_db),
):
    """获取权限列表"""
    permissions = await list_permissions(session, module=module)
    data = [PermissionRead.model_validate(p, from_attributes=True) for p in permissions]
    return success_response(data=data, message="获取权限列表成功")


@router.get("/modules")
async def list_modules_endpoint(
    _: User = Depends(require_permissions("permission:read")),
    session: AsyncSession = Depends(get_db),
):
    """获取权限模块列表"""
    modules = await get_modules(session)
    return success_response(data=modules, message="获取模块列表成功")


@router.post("")
async def create_permission_endpoint(
    payload: PermissionCreate,
    _: User = Depends(require_permissions("permission:create")),
    session: AsyncSession = Depends(get_db),
):
    """创建权限（仅超级管理员）"""
    permission = await create_permission(session, payload)
    return success_response(
        data=PermissionRead.model_validate(permission, from_attributes=True),
        message="创建权限成功",
    )


@router.get("/{permission_id}")
async def get_permission_endpoint(
    permission_id: int,
    _: User = Depends(require_permissions("permission:read")),
    session: AsyncSession = Depends(get_db),
):
    """获取权限详情"""
    permission = await get_permission(session, permission_id)
    return success_response(
        data=PermissionRead.model_validate(permission, from_attributes=True),
        message="获取权限详情成功",
    )


@router.put("/{permission_id}")
async def update_permission_endpoint(
    permission_id: int,
    payload: PermissionUpdate,
    _: User = Depends(require_permissions("permission:update")),
    session: AsyncSession = Depends(get_db),
):
    """更新权限"""
    permission = await update_permission(session, permission_id, payload)
    return success_response(
        data=PermissionRead.model_validate(permission, from_attributes=True),
        message="更新权限成功",
    )


@router.delete("/{permission_id}")
async def delete_permission_endpoint(
    permission_id: int,
    _: User = Depends(require_permissions("permission:delete")),
    session: AsyncSession = Depends(get_db),
):
    """删除权限"""
    await delete_permission(session, permission_id)
    return success_response(message="删除权限成功")


@router.get("/roles/{role_id}")
async def get_role_permissions_endpoint(
    role_id: int,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db),
):
    """获取角色已分配的权限"""
    user_detail = await get_user_detail(session, current_user.tenant_id, current_user.id)
    if not current_user.is_superuser:
        # 普通用户只能查看自己租户下的角色
        from app.models.role import Role
        role = await session.get(Role, role_id)
        if role is None or role.tenant_id != current_user.tenant_id:
            from app.core.exceptions import AppException, AppErrorCode
            raise AppException.from_error(AppErrorCode.ROLE_NOT_FOUND)

    permissions = await get_role_permissions(session, role_id)
    data = [PermissionRead.model_validate(p, from_attributes=True) for p in permissions]
    return success_response(data=data, message="获取角色权限成功")


@router.put("/roles/{role_id}")
async def set_role_permissions_endpoint(
    role_id: int,
    payload: RolePermissionUpdate,
    current_user: User = Depends(require_permissions("permission:assign")),
    session: AsyncSession = Depends(get_db),
):
    """设置角色的权限（全量替换）"""
    if not current_user.is_superuser:
        # 普通管理员只能操作自己租户下的角色
        from app.models.role import Role
        role = await session.get(Role, role_id)
        if role is None or role.tenant_id != current_user.tenant_id:
            from app.core.exceptions import AppException, AppErrorCode
            raise AppException.from_error(AppErrorCode.ROLE_NOT_FOUND)

    permissions = await set_role_permissions(session, role_id, payload.permission_ids)
    data = [PermissionRead.model_validate(p, from_attributes=True) for p in permissions]
    return success_response(data=data, message="设置角色权限成功")
