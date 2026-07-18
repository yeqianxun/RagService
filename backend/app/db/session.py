from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy import MetaData

from app.core.config import settings


# 数据库引擎：生产环境禁用 SQL 日志输出，调试环境可选
# 优化连接池配置，避免连接被瞬间打满
engine = create_async_engine(
    settings.DATABASE_URL, 
    echo=False,  # 禁用 SQL 日志输出，避免太多日志
    pool_pre_ping=True,  # 连接前检查连接健康
    pool_recycle=3600,  # 1小时回收一次连接
    pool_size=5,  # 初始连接数
    max_overflow=10,  # 最大额外连接数（总计15）
    pool_timeout=30,  # 获取连接超时时间（秒）
)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
