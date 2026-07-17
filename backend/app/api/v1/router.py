from fastapi import APIRouter

from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.tenants import router as tenant_router
from app.api.v1.endpoints.users import router as user_router
from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.permissions import router as permission_router
from app.api.v1.endpoints.rag import router as rag_router


router = APIRouter()
router.include_router(auth_router, prefix="/auth", tags=["auth"])
router.include_router(tenant_router, prefix="/tenants", tags=["tenants"])
router.include_router(user_router, prefix="/users", tags=["users"])
router.include_router(health_router, prefix="/health", tags=["health"])
router.include_router(permission_router, prefix="/permissions", tags=["permissions"])
router.include_router(rag_router, prefix="/rag", tags=["RAG"])
