"""Prometheus 指标暴露路由"""
from fastapi import APIRouter
from starlette.responses import Response

from app.monitoring.metrics import metrics_endpoint

router = APIRouter()


@router.get("/metrics", include_in_schema=False)
async def get_metrics() -> Response:
    """返回 Prometheus 格式的指标数据"""
    return await metrics_endpoint()
