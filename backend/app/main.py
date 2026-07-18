import asyncio
import platform
import traceback
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.metrics import router as metrics_router
from app.api.router import api_router
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging_config import app_logger
from app.db.init_db import initialize_with_retry
from app.db.session import engine
from app.middlewares import AccessLogMiddleware
from app.monitoring.metrics import MetricsMiddleware, setup_metrics
from app.monitoring.system_collector import system_collector_loop
from app.services.rag_service import get_embedding_model


# Windows 上必须使用 SelectorEventLoop，避免和 asyncpg 兼容性问题
# ProactorEventLoop 在 Windows 上会导致连接重置 (WinError 64/10054)
if platform.system() == "Windows":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def create_safe_background_task(coro, name):
    """
    创建安全的后台任务，确保异常不会被吞掉，而是打印完整堆栈

    Args:
        coro: 协程对象
        name: 任务名称，用于日志
    """
    async def wrapped():
        try:
            await coro
        except asyncio.CancelledError:
            # 任务被取消是正常的，不打印堆栈
            app_logger.info(f"后台任务 '{name}' 已取消")
            raise
        except Exception as e:
            # 捕获所有其他异常，打印完整堆栈，但不重新抛出
            # 避免在 lifespan 清理阶段产生重复日志
            app_logger.error(f"后台任务 '{name}' 异常: {str(e)}")
            app_logger.error("完整堆栈:")
            stack_trace = traceback.format_exc()
            app_logger.error(stack_trace)
    return wrapped()


def create_restartable_background_task(coro_factory, name, restart_delay: float = 1.0):
    """
    创建可自动重启的后台任务，崩溃后会自动重启

    Args:
        coro_factory: 协程工厂函数，每次重启时调用获取新的协程
        name: 任务名称，用于日志
        restart_delay: 重启前的延迟时间（秒）
    """
    async def wrapped():
        app_logger.info(f"后台任务 '{name}' 已启动（自动重启模式）")
        while True:
            try:
                await coro_factory()
            except asyncio.CancelledError:
                # 任务被取消是正常的
                app_logger.info(f"后台任务 '{name}' 已取消")
                raise
            except Exception as e:
                # 捕获异常，打印堆栈，然后延迟重启
                app_logger.error(f"后台任务 '{name}' 异常，将在 {restart_delay} 秒后重启: {str(e)}")
                app_logger.error("完整堆栈:")
                stack_trace = traceback.format_exc()
                app_logger.error(stack_trace)
                try:
                    await asyncio.sleep(restart_delay)
                except asyncio.CancelledError:
                    app_logger.info(f"后台任务 '{name}' 在重启等待期间已取消")
                    raise
    return wrapped()


async def background_initialization():
    """后台初始化任务，不阻塞应用启动"""
    try:
        # 先初始化数据库，带重试机制
        db_success = await initialize_with_retry(max_retries=5, retry_delay=2)
        if db_success:
            app_logger.info("数据库初始化完成")
        else:
            app_logger.error("数据库初始化失败，将在首次请求时尝试")

        # 预加载 Embedding 模型（可选）
        if settings.PRELOAD_EMBEDDING_MODEL:
            try:
                app_logger.info("开始后台加载 Embedding 模型...")
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, get_embedding_model)
                app_logger.info("Embedding 模型加载完成")
            except Exception as e:
                app_logger.warning(f"Embedding 模型预加载失败: {str(e)}")
                app_logger.warning("Embedding 加载堆栈:")
                app_logger.warning(traceback.format_exc())
                app_logger.info("将在首次 RAG 请求时加载模型")
    except Exception as e:
        app_logger.error(f"后台初始化异常: {str(e)}")
        app_logger.error("完整堆栈:")
        app_logger.error(traceback.format_exc())


@asynccontextmanager
async def lifespan(_: FastAPI):
    # 先启动应用，不阻塞初始化
    # 后台任务会在后台运行，且异常会被完整打印

    # 启动后台初始化（安全包装）
    init_task = asyncio.create_task(
        create_safe_background_task(background_initialization(), "系统初始化")
    )

    # 启动后台系统指标采集任务（可自动重启）
    collector_task = asyncio.create_task(
        create_restartable_background_task(
            system_collector_loop, "系统指标采集", restart_delay=1.0
        )
    )

    yield

    # 清理：优雅关闭所有后台任务
    app_logger.info("正在关闭后台任务...")

    # 取消所有任务
    if not init_task.done():
        app_logger.info("正在取消系统初始化任务...")
        init_task.cancel()
    if not collector_task.done():
        app_logger.info("正在取消系统指标采集任务...")
        collector_task.cancel()

    # 等待任务完成，处理取消异常
    try:
        if not init_task.done():
            await init_task
    except asyncio.CancelledError:
        app_logger.info("系统初始化任务已优雅取消")
    except Exception as e:
        app_logger.error(f"系统初始化任务关闭时出错: {str(e)}")

    try:
        if not collector_task.done():
            await collector_task
    except asyncio.CancelledError:
        app_logger.info("系统指标采集任务已优雅取消")
    except Exception as e:
        app_logger.error(f"系统指标采集任务关闭时出错: {str(e)}")

    app_logger.info("所有后台任务已关闭")

    # 释放数据库连接池，避免 Windows 下残留死 TCP 连接
    try:
        app_logger.info("正在释放数据库连接池...")
        await engine.dispose()
        app_logger.info("数据库连接池已成功释放")
    except Exception as e:
        app_logger.error(f"释放数据库连接池时出错: {str(e)}")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        debug=settings.DEBUG,
        lifespan=lifespan,
    )

    # 初始化 Prometheus 指标
    setup_metrics()

    app.add_middleware(MetricsMiddleware)
    app.add_middleware(AccessLogMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_exception_handlers(app)
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)
    app.include_router(metrics_router)

    app_logger.info(
        "Application started | debug=%s | docs=http://localhost:8000/docs",
        settings.DEBUG,
    )
    app_logger.info("后台初始化任务正在进行中...")
    return app


app = create_app()
