from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    APP_NAME: str = "FastAPI Rag + Agent System"
    APP_VERSION: str = "1.0.0"
    API_V1_PREFIX: str = "/api/v1"
    DEBUG: bool = True

    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 120

    DATABASE_URL: str = "postgresql+psycopg://postgres:password@localhost:5432/rag_service"
    CORS_ORIGINS: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:3000",
        ]
    )
    UPLOAD_DIR: str = "./uploads"

    DEFAULT_TENANT_NAME: str = "Platform Tenant"
    DEFAULT_TENANT_CODE: str = "platform"
    DEFAULT_ADMIN_EMAIL: str = "admin@example.com"
    DEFAULT_ADMIN_PASSWORD: str = "Admin@123456"
    DEFAULT_ADMIN_FULL_NAME: str = "Platform Admin"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
