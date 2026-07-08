from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user, require_permissions
from app.core.exceptions import AppException, AppErrorCode
from app.core.response import success_response
from app.db.session import get_db
from app.models.user import User
from app.schemas.tenant import TenantCreate, TenantRead
from app.services.tenant_service import create_tenant, list_tenants


router = APIRouter()


@router.get("")
async def get_tenants(
    current_user: User = Depends(require_permissions("tenant:read")),
    session: AsyncSession = Depends(get_db),
):
    """
    获取租户列表接口

    对于超级管理员，返回所有租户列表；对于普通用户，只返回其所属的租户。

    Args:
        current_user (User): 当前用户，需要有 "tenant:read" 权限
        session (AsyncSession): 数据库异步会话依赖

    Returns:
        JSONResponse: 包含租户列表的成功响应
    """
    if current_user.is_superuser:
        tenants = await list_tenants(session)
    else:
        tenants = await list_tenants(session, tenant_id=current_user.tenant_id)
    data = [TenantRead.model_validate(tenant, from_attributes=True) for tenant in tenants]
    return success_response(data=data, message="获取租户列表成功")


@router.post("")
async def create_tenant_endpoint(
    payload: TenantCreate,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db),
):
    """
    创建租户接口（仅超级管理员可用）

    该接口仅允许超级管理员创建新的租户，并为新租户创建默认的管理员角色和管理员用户。

    Args:
        payload (TenantCreate): 包含新租户信息的创建请求数据
        current_user (User): 当前用户，必须是超级管理员
        session (AsyncSession): 数据库异步会话依赖

    Raises:
        AppException: 当当前用户不是超级管理员时抛出403异常

    Returns:
        JSONResponse: 包含新创建租户信息的成功响应
    """
    if not current_user.is_superuser:
        raise AppException.from_error(AppErrorCode.PERMISSION_DENIED)
    tenant = await create_tenant(session, payload)
    return success_response(
        data=TenantRead.model_validate(tenant, from_attributes=True),
        message="创建租户成功",
    )


@router.get("/current")
async def get_current_tenant(current_user: User = Depends(get_current_active_user)):
    """
    获取当前租户信息接口

    该接口返回当前已认证用户所属的租户信息。

    Args:
        current_user (User): 通过依赖注入获取的当前活跃用户对象

    Returns:
        JSONResponse: 包含当前用户所属租户信息的成功响应
    """
    return success_response(
        data=TenantRead.model_validate(current_user.tenant, from_attributes=True),
        message="获取当前租户成功",
    )
