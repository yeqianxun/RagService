import asyncio
import platform
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.metrics import router as metrics_router
from app.api.router import api_router
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging_config import app_logger
from app.db.init_db import initialize_database
from app.middlewares import AccessLogMiddleware
from app.monitoring.metrics import MetricsMiddleware, setup_metrics
from app.monitoring.system_collector import system_collector_loop

# Windows 上 psycopg 异步模式需要使用 SelectorEventLoop
if platform.system() == "Windows":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


@asynccontextmanager
async def lifespan(_: FastAPI):
    await initialize_database()
    # 启动后台系统指标采集任务
    collector_task = asyncio.create_task(system_collector_loop())
    yield
    collector_task.cancel()
    try:
        await collector_task
    except asyncio.CancelledError:
        pass


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
    return app


app = create_app()
