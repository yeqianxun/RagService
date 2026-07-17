from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from fastapi import Request, status
from fastapi.responses import JSONResponse
from functools import wraps
from limits.storage import MemoryStorage, RedisStorage
from app.core.config import settings
import redis
import logging

logger = logging.getLogger(__name__)


def create_limiter():
    """
    创建限流器实例
    根据配置选择使用内存存储或 Redis 存储
    """
    try:
        # 尝试使用 Redis 存储
        redis_client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            password=settings.REDIS_PASSWORD,
            decode_responses=False,
        )
        # 测试 Redis 连接
        redis_client.ping()
        # 构建 Redis storage URI
        password_part = f":{settings.REDIS_PASSWORD}@" if settings.REDIS_PASSWORD else ""
        storage_uri = f"redis://{password_part}{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}"
        logger.info("Using Redis for rate limiting storage")
    except Exception as e:
        # Redis 不可用时降级到内存存储
        logger.warning(f"Failed to connect to Redis for rate limiting: {e}, falling back to memory storage")
        storage_uri = "memory://"

    return Limiter(
        key_func=get_remote_address,
        storage_uri=storage_uri,
        default_limits=["100 per minute"],
        enabled=True,
        headers_enabled=True,
    )


# 创建全局限流器实例
limiter = create_limiter()


def setup_rate_limiter(app):
    """
    设置 FastAPI 应用的限流中间件和错误处理
    """
    # 添加限流中间件
    app.add_middleware(SlowAPIMiddleware)

    # 注册限流错误处理
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # 注册自定义限流错误处理（可选）
    @app.exception_handler(RateLimitExceeded)
    async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "success": False,
                "message": "Too many requests, please try again later",
                "retry_after": exc.headers.get("Retry-After", 60),
                "error_code": "RATE_LIMIT_EXCEEDED"
            },
            headers=exc.headers
        )

    # 存储限流器实例到 app 状态中
    app.state.limiter = limiter
    logger.info("Rate limiter setup completed")
    return app


# 常用的限流装饰器快捷方式
def limit(limit_value: str, key_func=None, per_method=True, error_message=None):
    """
    自定义限流装饰器
    :param limit_value: 限流表达式，如 "10 per minute", "5 per second"
    :param key_func: 自定义的 key 函数，默认使用 IP 地址
    :param per_method: 是否按 HTTP 方法分别限流
    :param error_message: 自定义的错误消息
    """
    return limiter.limit(
        limit_value,
        key_func=key_func,
        per_method=per_method,
        error_message=error_message
    )


# 预设的限流策略
LIMIT_LOGIN = "5 per minute"
LIMIT_FILE_UPLOAD = "10 per hour"
LIMIT_USER_CREATE = "5 per hour"
