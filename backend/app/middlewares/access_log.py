"""
访问日志中间件

记录每个 HTTP 请求的详细信息，包括：
- 请求方法、路径、查询参数
- 响应状态码
- 处理耗时
- 客户端 IP
"""
import re
import time
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from app.core.logging_config import access_logger


# 默认不需要记录访问日志的路径模式
DEFAULT_SKIP_PATTERNS: list[str] = [
    r"^/health$",
    r"^/docs",
    r"^/redoc",
    r"^/openapi.json",
    r"^/metrics$",
]


class AccessLogMiddleware(BaseHTTPMiddleware):
    """HTTP 访问日志中间件"""

    def __init__(
        self,
        app: ASGIApp,
        skip_patterns: list[str] | None = None,
    ) -> None:
        super().__init__(app)
        self._skip_patterns = [
            re.compile(p) for p in (skip_patterns or DEFAULT_SKIP_PATTERNS)
        ]

    def _should_skip(self, path: str) -> bool:
        """判断指定路径是否需要跳过日志记录"""
        return any(pattern.search(path) for pattern in self._skip_patterns)

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        # 跳过不需要记录的路径
        if self._should_skip(request.url.path):
            return await call_next(request)

        start_time = time.perf_counter()

        # 获取客户端 IP
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            client_ip = forwarded.split(",")[0].strip()
        else:
            client_ip = request.client.host if request.client else "unknown"

        response = await call_next(request)

        # 计算耗时（毫秒）
        duration_ms = (time.perf_counter() - start_time) * 1000

        # 构造日志内容
        log_line = (
            f"{client_ip:15s} "
            f'"{request.method} {request.url.path} HTTP/{request.scope.get("http_version", "1.1")}" '
            f"{response.status_code} "
            f"{duration_ms:.1f}ms"
        )

        # 添加查询参数（如果有）
        if request.query_params:
            log_line += f" ?{request.query_params}"

        # 添加 User-Agent（截断到 120 字符）
        user_agent = request.headers.get("User-Agent", "-")
        if len(user_agent) > 120:
            user_agent = user_agent[:117] + "..."
        log_line += f' | {user_agent}'

        access_logger.info(log_line)

        # 在响应头中添加处理耗时（方便调试）
        response.headers["X-Process-Time-Ms"] = f"{duration_ms:.1f}"

        return response
