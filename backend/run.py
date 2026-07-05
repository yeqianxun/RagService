"""
应用入口脚本
解决 Windows 上 psycopg 异步模式与 ProactorEventLoop 的兼容性问题
"""
import asyncio
import platform

# Windows 上 psycopg 异步模式需要使用 SelectorEventLoop
# 将 set_event_loop_policy 放在所有导入之前，确保 uvicorn 使用正确的事件循环
if platform.system() == "Windows":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
