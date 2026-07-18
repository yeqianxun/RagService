import asyncio
from sqlalchemy.ext.asyncio import create_async_engine

DATABASE_URL = "postgresql+asyncpg://postgresql:Qq124094@127.0.0.1:5432/db"
engine = create_async_engine(DATABASE_URL, pool_pre_ping=True)

async def test_conn():
    async with engine.begin() as conn:
        print("连接成功")
        await conn.execute("SELECT 1")
    await engine.dispose()

asyncio.run(test_conn())