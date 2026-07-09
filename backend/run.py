"""启动脚本 - 在 Windows 上设置 SelectorEventLoop 以避免 psycopg 兼容性问题"""
import asyncio
import platform

if platform.system() == "Windows":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import uvicorn

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=False)
