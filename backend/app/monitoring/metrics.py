"""
Prometheus 指标定义和采集中间件

提供：
- HTTP 请求指标（耗时、状态码、路径）
- 系统资源指标委托给 system_collector 定期更新
- FastAPI 中间件自动记录请求指标
"""
import time

from prometheus_client import Counter, Gauge, Histogram, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging_config import app_logger

# ── HTTP 请求指标 ──────────────────────────────────────────────

HTTP_REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    labelnames=["method", "path", "status"],
)

HTTP_REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    labelnames=["method", "path"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

HTTP_IN_FLIGHT = Gauge(
    "http_requests_in_flight",
    "Current in-flight HTTP requests",
    labelnames=["method"],
)

# ── 系统资源指标（由 system_collector 定时更新）───────────────

# CPU
CPU_USAGE_PERCENT = Gauge("system_cpu_usage_percent", "CPU usage percentage")
CPU_COUNT = Gauge("system_cpu_count", "Number of CPU cores")

# 内存
MEMORY_TOTAL_BYTES = Gauge("system_memory_total_bytes", "Total physical memory")
MEMORY_USED_BYTES = Gauge("system_memory_used_bytes", "Used physical memory")
MEMORY_PERCENT = Gauge("system_memory_usage_percent", "Memory usage percentage")

# 磁盘
DISK_TOTAL_BYTES = Gauge(
    "system_disk_total_bytes", "Total disk space", labelnames=["mount"]
)
DISK_USED_BYTES = Gauge(
    "system_disk_used_bytes", "Used disk space", labelnames=["mount"]
)
DISK_PERCENT = Gauge(
    "system_disk_usage_percent", "Disk usage percentage", labelnames=["mount"]
)

# 网络
NETWORK_BYTES_SENT = Gauge(
    "system_network_bytes_sent_total",
    "Total network bytes sent",
    labelnames=["interface"],
)
NETWORK_BYTES_RECV = Gauge(
    "system_network_bytes_received_total",
    "Total network bytes received",
    labelnames=["interface"],
)

# 进程
PROCESS_CPU_PERCENT = Gauge("process_cpu_percent", "Process CPU usage percentage")
PROCESS_MEMORY_BYTES = Gauge("process_memory_bytes", "Process memory usage in bytes")
PROCESS_OPEN_FDS = Gauge("process_open_fds", "Process open file descriptors")
PROCESS_THREADS = Gauge("process_threads", "Process thread count")
PROCESS_UPTIME_SECONDS = Gauge(
    "process_uptime_seconds", "Process uptime in seconds"
)


# ── 静态信息 ───────────────────────────────────────────────────

BUILD_INFO = Gauge(
    "build_info",
    "Build information",
    labelnames=["version", "python_version"],
)


def init_build_info() -> None:
    """记录应用和 Python 版本信息（固定值为 1）"""
    import sys

    from app.core.config import settings

    BUILD_INFO.labels(
        version=settings.APP_VERSION,
        python_version=sys.version.split()[0],
    ).set(1)


# ── Prometheus 指标端点 ──────────────────────────────────────


async def metrics_endpoint() -> Response:
    """返回 Prometheus 格式的所有指标"""
    from prometheus_client import generate_latest

    return Response(
        content=generate_latest(),
        media_type="text/plain; charset=utf-8",
        headers={"Cache-Control": "no-cache"},
    )


# ── 请求耗时统计中间件 ────────────────────────────────────────

SKIP_METRICS_PATHS = {"/metrics", "/health"}


class MetricsMiddleware(BaseHTTPMiddleware):
    """自动记录 HTTP 请求指标"""

    async def dispatch(self, request: Request, call_next):
        method = request.method
        path = request.url.path

        if path in SKIP_METRICS_PATHS:
            return await call_next(request)

        HTTP_IN_FLIGHT.labels(method=method).inc()
        start = time.perf_counter()
        response = None

        try:
            response = await call_next(request)
            return response
        finally:
            duration = time.perf_counter() - start
            status_code = response.status_code if response is not None else 500
            HTTP_REQUEST_COUNT.labels(
                method=method, path=path, status=status_code
            ).inc()
            HTTP_REQUEST_DURATION.labels(method=method, path=path).observe(duration)
            HTTP_IN_FLIGHT.labels(method=method).dec()


# ── 初始化 ─────────────────────────────────────────────────────


def setup_metrics() -> None:
    """初始化 Prometheus 指标"""
    init_build_info()
    app_logger.info("Prometheus metrics initialized")
