# 测试文件，逐步导入模块以找出问题所在
print("开始测试导入...")

try:
    print("1. 导入 config...")
    from app.core.config import settings
    print("   config 导入成功")
except Exception as e:
    print(f"   config 导入失败: {e}")

try:
    print("2. 导入 sqlalchemy 模块...")
    from sqlalchemy.ext.asyncio import create_async_engine
    print("   sqlalchemy 导入成功")
except Exception as e:
    print(f"   sqlalchemy 导入失败: {e}")

try:
    print("3. 导入 base 模型...")
    from app.models.base import Base, TimestampMixin, TenantScopedMixin
    print("   base 模型导入成功")
except Exception as e:
    print(f"   base 模型导入失败: {e}")

try:
    print("4. 导入 Tenant 模型...")
    from app.models.tenant import Tenant
    print("   Tenant 模型导入成功")
except Exception as e:
    print(f"   Tenant 模型导入失败: {e}")

try:
    print("5. 导入 Role 模型...")
    from app.models.role import Role
    print("   Role 模型导入成功")
except Exception as e:
    print(f"   Role 模型导入失败: {e}")

try:
    print("6. 导入 User 模型...")
    from app.models.user import User
    print("   User 模型导入成功")
except Exception as e:
    print(f"   User 模型导入失败: {e}")

print("测试完成")