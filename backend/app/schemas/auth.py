from pydantic import BaseModel, EmailStr, Field

from app.schemas.common import ORMModel
from app.schemas.permission import PermissionSummary


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=128)


class TokenPayload(BaseModel):
    sub: str
    exp: int


class RoleInfo(ORMModel):
    id: int
    name: str
    permissions: list[PermissionSummary]


class CurrentUserInfo(ORMModel):
    id: int
    username: str
    email: EmailStr
    full_name: str | None = None
    is_active: bool
    is_superuser: bool
    role: RoleInfo


class TokenData(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: CurrentUserInfo


class OAuth2TokenResponse(BaseModel):
    """OAuth2 标准 token 响应格式"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int
