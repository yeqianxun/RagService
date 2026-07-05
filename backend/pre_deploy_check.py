#!/usr/bin/env python3
"""
部署前环境检查脚本
用于验证系统是否满足部署要求
"""

import sys
import os
import subprocess
from pathlib import Path


def check_python_version():
    """检查 Python 版本"""
    print("检查 Python 版本...")
    major, minor, *_ = sys.version_info
    if major < 3 or (major == 3 and minor < 9):
        print(f"❌ 错误: 需要 Python 3.9+, 当前版本: {major}.{minor}")
        return False
    print(f"✅ Python 版本: {major}.{minor} 满足要求")
    return True


def check_dependencies():
    """检查 Python 依赖"""
    print("\n检查 Python 依赖...")
    required_packages = [
        "fastapi",
        "sqlalchemy",
        "asyncpg",
        "psycopg",
        "pgvector",
        "uvicorn",
        "gunicorn",
        "pydantic_settings",
        "python_jose",
        "passlib",
        "python_multipart",
        "email_validator"
    ]
    
    missing_packages = []
    for package in required_packages:
        try:
            # 尝试导入包
            __import__(package.replace("-", "_"))
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print(f"❌ 缺少依赖包: {', '.join(missing_packages)}")
        print("请运行: pip install -r requirements.txt")
        return False
    
    print("✅ 所有依赖包均已安装")
    return True


def check_database_connection():
    """检查数据库连接"""
    print("\n检查数据库连接...")
    try:
        import os
        from sqlalchemy import create_engine, text
        from sqlalchemy.ext.asyncio import create_async_engine
        
        # 从环境变量或 .env 文件获取数据库 URL
        from app.core.config import settings
        
        # 尝试连接数据库
        engine = create_async_engine(settings.DATABASE_URL)
        
        import asyncio
        async def test_connection():
            async with engine.connect() as conn:
                result = await conn.execute(text("SELECT 1"))
                return result.fetchone()[0]
        
        # 运行异步测试
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(test_connection())
        loop.close()
        
        if result == 1:
            print("✅ 数据库连接正常")
            return True
        else:
            print("❌ 数据库连接测试失败")
            return False
            
    except Exception as e:
        print(f"❌ 数据库连接失败: {e}")
        print("请确保:")
        print("- PostgreSQL 服务正在运行")
        print("- pgvector 扩展已安装并启用")
        print("- DATABASE_URL 配置正确")
        print("- .env 文件已正确配置")
        return False


def check_env_file():
    """检查 .env 文件"""
    print("\n检查 .env 文件...")
    env_file = Path(".env")
    if not env_file.exists():
        print("⚠️  .env 文件不存在，将使用默认配置")
        print("建议: cp .env.example .env 并根据需要编辑配置")
        return True
    
    print("✅ .env 文件存在")
    return True


def check_required_dirs():
    """检查必需的目录"""
    print("\n检查必需的目录...")
    required_dirs = ["uploads"]
    
    for dir_name in required_dirs:
        dir_path = Path(dir_name)
        if not dir_path.exists():
            print(f"⚠️  目录 {dir_name} 不存在，将尝试创建")
            try:
                dir_path.mkdir(parents=True, exist_ok=True)
                print(f"✅ 目录 {dir_name} 已创建")
            except Exception as e:
                print(f"❌ 无法创建目录 {dir_name}: {e}")
                return False
        else:
            print(f"✅ 目录 {dir_name} 存在")
    
    return True


def main():
    """主检查函数"""
    print("🚀 开始部署前环境检查...\n")
    
    checks = [
        ("Python 版本", check_python_version),
        ("Python 依赖", check_dependencies),
        ("环境文件", check_env_file),
        ("必需目录", check_required_dirs),
        ("数据库连接", check_database_connection),
    ]
    
    results = []
    for name, check_func in checks:
        print(f"\n🔍 执行检查: {name}")
        result = check_func()
        results.append((name, result))
    
    print("\n" + "="*50)
    print("📋 检查结果汇总:")
    
    all_passed = True
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"- {name}: {status}")
        if not result:
            all_passed = False
    
    print("="*50)
    
    if all_passed:
        print("🎉 所有检查通过! 环境已准备好进行部署。")
        return 0
    else:
        print("💥 部署环境检查失败，请解决上述问题后再试。")
        return 1


if __name__ == "__main__":
    sys.exit(main())