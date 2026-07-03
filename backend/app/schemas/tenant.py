from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class TenantCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    code: str = Field(..., min_length=2, max_length=50, pattern=r"^[a-z][a-z0-9_-]+$")
    admin_email: str = Field(..., min_length=6, max_length=255)
    admin_password: str = Field(..., min_length=8, max_length=128)
    admin_full_name: str = Field(..., min_length=2, max_length=100)


class TenantRead(ORMModel):
    id: int
    name: str
    code: str
    is_active: bool


class TenantSummary(BaseModel):
    id: int
    name: str
    code: str
