from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import get_password_hash
from app.db.session import AsyncSessionLocal, engine
from app.models.base import Base
from app.models.permission import Permission
from app.models.role import Role
from app.models.tenant import Tenant
from app.models.user import User


# 系统预定义权限全集（code -> {name, module, description}）
BUILT_IN_PERMISSIONS: dict[str, dict[str, str]] = {
    # 租户管理
    "tenant:read": {
        "name": "查看租户",
        "module": "tenant",
        "description": "查看租户基本信息",
    },
    # 用户管理
    "user:read": {
        "name": "查看用户",
        "module": "user",
        "description": "查看用户列表和详情",
    },
    "user:create": {
        "name": "创建用户",
        "module": "user",
        "description": "在当前租户下创建新用户",
    },
    "user:upload": {
        "name": "上传文件",
        "module": "user",
        "description": "上传文件到租户存储",
    },
    # 权限管理
    "permission:read": {
        "name": "查看权限",
        "module": "permission",
        "description": "查看权限列表和详情",
    },
    "permission:create": {
        "name": "创建权限",
        "module": "permission",
        "description": "创建新的权限定义",
    },
    "permission:update": {
        "name": "更新权限",
        "module": "permission",
        "description": "更新权限的名称、描述等信息",
    },
    "permission:delete": {
        "name": "删除权限",
        "module": "permission",
        "description": "删除已有的权限定义",
    },
    "permission:assign": {
        "name": "分配权限",
        "module": "permission",
        "description": "给角色分配或移除权限",
    },
    # RAG 管理
    "rag:read": {
        "name": "查看 RAG 数据",
        "module": "rag",
        "description": "查看文件列表、查询历史等 RAG 相关数据",
    },
    "rag:upload": {
        "name": "上传 RAG 文件",
        "module": "rag",
        "description": "上传文件到 RAG 知识库",
    },
    "rag:delete": {
        "name": "删除 RAG 文件",
        "module": "rag",
        "description": "从 RAG 知识库删除文件",
    },
    "rag:query": {
        "name": "RAG 查询",
        "module": "rag",
        "description": "使用 RAG 功能进行查询问答",
    },
}

# 默认租户管理员权限（不包含 tenant:create 等敏感权限）
DEFAULT_ADMIN_PERMISSION_CODES = [
    "tenant:read",
    "user:read",
    "user:create",
    "user:upload",
    "permission:read",
    "permission:assign",
    "rag:read",
    "rag:upload",
    "rag:delete",
    "rag:query",
]

# 平台超级管理员拥有全部权限
SUPER_ADMIN_PERMISSION_CODES = list(BUILT_IN_PERMISSIONS.keys())


async def seed_permissions(session: AsyncSession) -> dict[str, Permission]:
    """种子权限表，返回 {code: Permission} 映射"""
    result = await session.execute(select(Permission))
    existing = {p.code: p for p in result.scalars().all()}

    for code, meta in BUILT_IN_PERMISSIONS.items():
        if code in existing:
            # 更新已有权限的元数据
            perm = existing[code]
            perm.name = meta["name"]
            perm.module = meta["module"]
            perm.description = meta.get("description")
        else:
            perm = Permission(
                code=code,
                name=meta["name"],
                module=meta["module"],
                description=meta.get("description"),
            )
            session.add(perm)
            existing[code] = perm

    await session.flush()
    return existing


async def seed_default_data(session: AsyncSession) -> None:
    """
    初始化默认数据

    创建默认租户、所有预定义权限、管理员角色和超级管理员用户。
    """
    # 1. 创建或获取默认租户
    tenant_stmt = select(Tenant).where(Tenant.code == settings.DEFAULT_TENANT_CODE)
    tenant = (await session.execute(tenant_stmt)).scalar_one_or_none()

    if tenant is None:
        tenant = Tenant(name=settings.DEFAULT_TENANT_NAME, code=settings.DEFAULT_TENANT_CODE)
        session.add(tenant)
        await session.flush()

    # 2. 种子权限表
    permissions_map = await seed_permissions(session)

    # 3. 创建默认管理员角色（如果不存在）
    role_stmt = select(Role).where(
        Role.tenant_id == tenant.id,
        Role.name == "admin",
    )
    role = (await session.execute(role_stmt)).scalar_one_or_none()

    if role is None:
        # 权限在 flush 前通过构造函数 setting 分配，避免异步懒加载
        role = Role(
            tenant_id=tenant.id,
            name="admin",
            description="System administrator",
            permissions=[permissions_map[code] for code in DEFAULT_ADMIN_PERMISSION_CODES],
        )
        session.add(role)
        await session.flush()

    # 4. 创建超级管理员用户（如果不存在）
    user_stmt = select(User).where(
        User.tenant_id == tenant.id,
        User.email == settings.DEFAULT_ADMIN_EMAIL,
    )
    admin_user = (await session.execute(user_stmt)).scalar_one_or_none()

    if admin_user is None:
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
    初始化数据库

    创建所有数据库表，然后插入默认数据。
    """
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        await seed_default_data(session)
