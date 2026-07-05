from fastapi import APIRouter
from pydantic import BaseModel


router = APIRouter()


class HealthCheck(BaseModel):
    """Health check response model"""
    status: str = "ok"


@router.get("/health", response_model=HealthCheck)
async def health_check():
    """
    Health check endpoint.
    Returns status ok if the application is running.
    """
    return HealthCheck(status="ok")