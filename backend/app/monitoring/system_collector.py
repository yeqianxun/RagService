"""
系统资源采集器

定时采集 CPU、内存、磁盘、网络、进程等指标，
直接更新模块级 Gauge 指标的值（这些 Gauge 已在默认 registry 中注册），
Prometheus 抓取 /metrics 时会直接读取当前值。
"""
import asyncio
import os
import time

import psutil

from app.core.logging_config import app_logger
from app.monitoring.metrics import (
    CPU_COUNT,
    CPU_USAGE_PERCENT,
    DISK_PERCENT,
    DISK_TOTAL_BYTES,
    DISK_USED_BYTES,
    MEMORY_PERCENT,
    MEMORY_TOTAL_BYTES,
    MEMORY_USED_BYTES,
    NETWORK_BYTES_RECV,
    NETWORK_BYTES_SENT,
    PROCESS_CPU_PERCENT,
    PROCESS_MEMORY_BYTES,
    PROCESS_OPEN_FDS,
    PROCESS_THREADS,
    PROCESS_UPTIME_SECONDS,
)

# 采集间隔（秒）
_COLLECT_INTERVAL = 5


async def collect_system_metrics() -> None:
    """采集一次系统指标并更新 Gauge"""
    try:
        _collect_cpu()
        _collect_memory()
        _collect_disk()
        _collect_network()
        _collect_process()
    except Exception:
        app_logger.exception("System metrics collection failed")


def _collect_cpu() -> None:
    CPU_COUNT.set(psutil.cpu_count(logical=True))
    CPU_USAGE_PERCENT.set(psutil.cpu_percent(interval=None))


def _collect_memory() -> None:
    mem = psutil.virtual_memory()
    MEMORY_TOTAL_BYTES.set(mem.total)
    MEMORY_USED_BYTES.set(mem.used)
    MEMORY_PERCENT.set(mem.percent)


def _collect_disk() -> None:
    for part in psutil.disk_partitions():
        if os.name == "nt" and ("cdrom" in part.opts or part.fstype == ""):
            continue
        try:
            usage = psutil.disk_usage(part.mountpoint)
            DISK_TOTAL_BYTES.labels(mount=part.mountpoint).set(usage.total)
            DISK_USED_BYTES.labels(mount=part.mountpoint).set(usage.used)
            DISK_PERCENT.labels(mount=part.mountpoint).set(usage.percent)
        except PermissionError:
            continue


def _collect_network() -> None:
    net = psutil.net_io_counters(pernic=True)
    for iface, stats in net.items():
        NETWORK_BYTES_SENT.labels(interface=iface).set(stats.bytes_sent)
        NETWORK_BYTES_RECV.labels(interface=iface).set(stats.bytes_recv)


def _collect_process() -> None:
    proc = psutil.Process()
    with proc.oneshot():
        PROCESS_CPU_PERCENT.set(proc.cpu_percent(interval=None))
        PROCESS_MEMORY_BYTES.set(proc.memory_info().rss)
        try:
            PROCESS_OPEN_FDS.set(proc.num_fds())
        except AttributeError:
            PROCESS_OPEN_FDS.set(0)
        PROCESS_THREADS.set(proc.num_threads())
        PROCESS_UPTIME_SECONDS.set(time.time() - proc.create_time())


# ── 后台采集任务 ────────────────────────────────────────────


async def system_collector_loop() -> None:
    """后台循环：每隔 _COLLECT_INTERVAL 秒采集一次系统指标"""
    while True:
        await collect_system_metrics()
        await asyncio.sleep(_COLLECT_INTERVAL)
