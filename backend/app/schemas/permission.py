from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class PermissionCreate(BaseModel):
    code: str = Field(..., min_length=2, max_length=100, pattern=r"^[a-z]+:[a-z]+$")
    name: str = Field(..., min_length=2, max_length=100)
    description: str | None = Field(None, max_length=500)
    module: str = Field(..., min_length=2, max_length=50)


class PermissionUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=100)
    description: str | None = Field(None, max_length=500)
    module: str | None = Field(None, min_length=2, max_length=50)


class PermissionRead(ORMModel):
    id: int
    code: str
    name: str
    description: str | None = None
    module: str


class PermissionSummary(BaseModel):
    id: int
    code: str
    name: str


class RolePermissionUpdate(BaseModel):
    """更新角色权限的请求"""
    permission_ids: list[int] = Field(..., min_length=0)
