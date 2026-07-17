from pydantic import BaseModel, EmailStr, Field

from app.schemas.common import ORMModel


class UserCreate(BaseModel):
    username: str = Field(..., min_length=2, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str = Field(..., min_length=2, max_length=100)
    role_id: int


class UserRead(ORMModel):
    id: int
    username: str
    email: EmailStr
    full_name: str | None = None
    is_active: bool
    is_superuser: bool


class UserProfile(UserRead):
    pass
