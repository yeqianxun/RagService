"""
访问日志中间件

记录每个 HTTP 请求的详细信息，包括：
- 请求方法、路径、查询参数
- 响应状态码
- 处理耗时
- 客户端 IP
- 请求头信息
- 请求体摘要
"""
import re
import time
import json
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

# 需要记录的关键请求头
KEY_HEADERS = [
    "User-Agent",
    "Content-Type",
    "Accept",
    "X-Request-ID",
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

        # 获取关键请求头信息
        headers_info = {}
        for header in KEY_HEADERS:
            if header in request.headers:
                value = request.headers[header]
                headers_info[header] = value

        # 获取请求体内容类型（避免直接消费请求体）
        content_type = request.headers.get("Content-Type", "")
        content_length = request.headers.get("Content-Length")

        request_body_info = ""
        if content_type:
            if any(x in content_type.lower() for x in ["multipart/form-data", "octet-stream"]):
                request_body_info = "<binary>"
            elif content_length and int(content_length) > 1024 * 10:
                request_body_info = f"<large-{content_length}b>"
            else:
                request_body_info = f"<{content_type}>"

        response = await call_next(request)

        # 计算耗时（毫秒）
        duration_ms = (time.perf_counter() - start_time) * 1000

        # 构造详细的日志内容
        log_parts = []

        # 基础信息
        log_parts.append(f"{client_ip:15s}")
        log_parts.append(f'"{request.method} {request.url.path} HTTP/{request.scope.get("http_version", "1.1")}"')
        log_parts.append(f"{response.status_code}")
        log_parts.append(f"{duration_ms:.1f}ms")

        # 查询参数
        if request.query_params:
            log_parts.append(f"?{request.query_params}")

        # 请求头信息
        if headers_info:
            headers_str = " | ".join([f"{k}={v}" for k, v in headers_info.items()])
            log_parts.append(f"[{headers_str}]")

        # 请求体信息
        if request_body_info:
            log_parts.append(f"body={request_body_info}")

        # 合并并记录
        log_line = " ".join(log_parts)
        access_logger.info(log_line)

        # 在响应头中添加处理耗时（方便调试）
        response.headers["X-Process-Time-Ms"] = f"{duration_ms:.1f}"

        return response
