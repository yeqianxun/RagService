from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )
    APP_NAME: str = "FastAPI Multi-Tenant System"
    APP_VERSION: str = "1.0.0"
    API_V1_PREFIX: str = "/api/v1"
    DEBUG: bool = True

    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 120

    DATABASE_URL: str = "mysql+asyncmy://root:Qq124094@localhost:3306/multi_tenant_system"
    CORS_ORIGINS: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:3000",
        ]
    )
    UPLOAD_DIR: str = "./uploads"
    LOG_DIR: str = "./logs"

    # Redis 配置
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None
    REDIS_TTL_SECONDS: int = 86400  # 24 hours

    DEFAULT_TENANT_NAME: str = "Platform Tenant"
    DEFAULT_TENANT_CODE: str = "platform"
    DEFAULT_ADMIN_EMAIL: str = "admin@example.com"
    DEFAULT_ADMIN_PASSWORD: str = "Admin@123456"
    DEFAULT_ADMIN_FULL_NAME: str = "Platform Admin"

    # Milvus 配置
    MILVUS_HOST: str = "localhost"
    MILVUS_PORT: int = 19530
    MILVUS_COLLECTION_NAME: str = "document_chunks"

    # Embedding 配置
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"

    # 文档切分配置
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 200

    # 检索配置
    TOP_K_RETRIEVAL: int = 5

    # RAG 文本清洗配置
    RAG_CLEAN_REMOVE_LINKS: bool = True
    RAG_MIN_SEGMENT_LEN: int = 8


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
